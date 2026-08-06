import json
from pathlib import Path
from collections import defaultdict
from collections.abc import Sequence, Iterator
from typing import Any, final

from jsonschema import Validator, ValidationError

from .errors import JsonDiagnosticError, TJsonDiagnosticError
from .formatters import ErrorMessageFormatter, get_global_message_formatter,  ErrorGroupFormatter, get_global_nested_group_formatter, LocationFormatter, get_global_location_formatter
from .handlers import IValidationHandler, DefaultValidationHandler
from .types import SourceDocument, SpanTarget, TextSpan, Location
from .typing import Json, StrPath


def _get_node_position(node: TJsonDiagnosticError, /) -> int:
    if isinstance(node, JsonDiagnosticError):
        return node.location.position if node.location else 0

    else:
        if node.exceptions:
            return _get_node_position(node.exceptions[0])
        return 0


def group_exceptions(errors: Sequence[JsonDiagnosticError], /, source_document: SourceDocument, *, depth: int = 0) -> ExceptionGroup[TJsonDiagnosticError] | None:
    if not errors:
        return None

    sorted_errors: list[JsonDiagnosticError] = sorted(errors, key=lambda error: error.location.position if error.location else 0)
    leaf_errors: list[JsonDiagnosticError] = []
    grouped_errors: dict[str | int, list[JsonDiagnosticError]] = defaultdict(list)

    for error in sorted_errors:
        if len(error.path) == depth:
            leaf_errors.append(error)
        else:
            current_key: str | int = error.path[depth]
            grouped_errors[current_key].append(error)

    child_nodes: list[TJsonDiagnosticError] = []
    child_nodes.extend(leaf_errors)

    for sub_errors in grouped_errors.values():
        nested_result: TJsonDiagnosticError | None = group_exceptions(
            sub_errors,
            source_document,
            depth=depth + 1,
        )
        if nested_result is not None:
            child_nodes.append(nested_result)

    if not child_nodes:
        return None

    child_nodes.sort(key=_get_node_position)

    if depth == 0:
        location_formatter: LocationFormatter = get_global_location_formatter()
        location_info: str = location_formatter.format(source_document.file_path, None)

        label: str = "JSON Validation Error"
        message: str = f"{label}\n{location_info}"
    else:
        parent_error: JsonDiagnosticError | None = errors[0] if errors else None
        current_prefix_path: list[str | int] = (
            list(parent_error.path)[:depth]
            if parent_error and len(parent_error.path) >= depth
            else []
        )
        formatter: ErrorGroupFormatter = get_global_nested_group_formatter()
        message: str = formatter.format(source_document, current_prefix_path)

    return ExceptionGroup(message, child_nodes)


class DiagnosticJsonParser:
    def __init__(self, validator: Validator, /, handlers: list[IValidationHandler] | None = None) -> None:
        super().__init__()

        self.validator = validator
        self.handlers: list[IValidationHandler] = []
        self.handlers.extend(handlers if handlers else [])
        self.handlers.append(DefaultValidationHandler())

    def parse_file(self, path: StrPath, /, encoding: str | None = None) -> Json:
        text: str = Path(path).read_text(encoding=encoding)
        return self.parse_text(text, path)

    def parse_text(self, text: str, /, path: StrPath | None = None) -> Json:
        raw_data, error_group = self.try_parse_text(text, path)
        if error_group is not None:
            raise error_group
        return raw_data

    def try_parse_file(self, path: StrPath, /, encoding: str | None = None) -> tuple[Json, ExceptionGroup[TJsonDiagnosticError] | None]:
        text: str = Path(path).read_text(encoding=encoding)

        return self.try_parse_text(text, path)

    def try_parse_text(self, text: str, /, path: StrPath | None = None) -> tuple[Json, ExceptionGroup[TJsonDiagnosticError] | None]:
        raw_data: Json = json.loads(text)
        remaining_errors: Sequence[ValidationError] = list(self.validator.iter_errors(raw_data))

        if not remaining_errors:
            return raw_data, None

        source_document: SourceDocument = SourceDocument.from_text(text, file_path=path)
        collected_exceptions: list[JsonDiagnosticError] = self._run_handlers(remaining_errors, source_document)

        exception_group = group_exceptions(collected_exceptions, source_document)

        return raw_data, exception_group

    def parse_to_node_file(self, path: StrPath, /, encoding: str | None = None) -> DiagnosticNode:
        text: str = Path(path).read_text(encoding=encoding)
        return self.parse_to_node_text(text, path)

    def parse_to_node_text(self, text: str, /, path: StrPath | None = None) -> DiagnosticNode:
        raw_data: Json = json.loads(text)
        source_document: SourceDocument = SourceDocument.from_text(text, file_path=path)
        remaining_errors: Sequence[ValidationError] = list(self.validator.iter_errors(raw_data))

        collected_exceptions: list[JsonDiagnosticError] = []
        if remaining_errors:
            collected_exceptions = self._run_handlers(remaining_errors, source_document)

        return DiagnosticNode(raw_data, collected_exceptions, source_document)

    def _run_handlers(
        self,
        errors: Sequence[ValidationError],
        source_document: SourceDocument,
        /,
    ) -> list[JsonDiagnosticError]:
        remaining_errors: Sequence[ValidationError] = errors
        collected_exceptions: list[JsonDiagnosticError] = []

        for handler in self.handlers:
            if not remaining_errors:
                break
            sub_errors, remaining_errors = handler.handle(self.validator, remaining_errors, source_document)
            collected_exceptions.extend(sub_errors)

        return collected_exceptions


@final
class DiagnosticNode():
    def __init__(self, data: Json, /, errors: Sequence[JsonDiagnosticError], source_document: SourceDocument, *, current_path: tuple[str | int, ...] = ()) -> None:
        self.errors: list[JsonDiagnosticError] = []
        self.source_document: SourceDocument = source_document
        self._contents: dict[str, DiagnosticNode] | list[DiagnosticNode] | None | bool | int | float | str | Any
        self._current_path: tuple[str | int, ...] = current_path

        current_depth: int = len(current_path)
        child_errors_map: defaultdict[str | int, list[JsonDiagnosticError]] = defaultdict(list)

        for error in errors:
            if len(error.path) == current_depth:
                self.errors.append(error)
            elif len(error.path) > current_depth:
                child_key: str | int = error.path[current_depth]
                child_errors_map[child_key].append(error)

        if isinstance(data, dict):
            dictionary_contents: dict[str, DiagnosticNode] = {}
            for key, value in data.items():
                child_path: tuple[str | int, ...] = current_path + (key,)
                dictionary_contents[key] = DiagnosticNode(value, child_errors_map[key], source_document, current_path=child_path)
            self._contents = dictionary_contents
        elif isinstance(data, list):
            list_contents: list[DiagnosticNode] = []
            for index, value in enumerate(data):
                child_path: tuple[str | int, ...] = current_path + (index,)
                list_contents.append(DiagnosticNode(value, child_errors_map[index], source_document, current_path=child_path))
            self._contents = list_contents
        else:
            self._contents = data

    @property
    def path(self) -> tuple[str | int, ...]:
        return self._current_path

    @property
    def value(self, /) -> Any:
        if isinstance(self._contents, dict):
            return {key: value.value if isinstance(value, DiagnosticNode) else value for key, value in self._contents.items()}  # type: ignore[unknown]
        elif isinstance(self._contents, list):
            return [value.value if isinstance(value, DiagnosticNode) else value for value in self._contents]  # type: ignore[unknown]
        else:
            return self._contents

    @value.setter
    def value(self, value: Any, /) -> None:
        self._contents = value

    def __getitem__(self, index: Any, /) -> Any:
        return self._contents[index]  # type: ignore

    def __setitem__(self, index: str | int, value: Any, /) -> None:
        self._contents[index] = value  # type: ignore

    def __delitem__(self, index: str | int, /) -> None:
        del self._contents[index]  # type: ignore

    def __len__(self, /) -> int:
        return len(self._contents)  # type: ignore

    def __iter__(self, /) -> Iterator[Any]:
        return iter(self._contents)  # type: ignore

    def __repr__(self, /) -> str:
        return f"{type(self).__name__}(_contents={self._contents}, errors={self.errors})"

    def collect_all_errors(self, /) -> tuple[JsonDiagnosticError, ...]:
        accumulated_errors: list[JsonDiagnosticError] = list(self.errors)

        if isinstance(self._contents, dict):
            for child_node in self._contents.values():  # type: ignore[unknown]
                if isinstance(child_node, DiagnosticNode):
                    accumulated_errors.extend(child_node.collect_all_errors())

        elif isinstance(self._contents, list):
            for child_node in self._contents:  # type: ignore[unknown]
                if isinstance(child_node, DiagnosticNode):
                    accumulated_errors.extend(child_node.collect_all_errors())

        return tuple(accumulated_errors)

    def to_exception_group(self, /) -> ExceptionGroup[TJsonDiagnosticError] | None:
        all_errors: tuple[JsonDiagnosticError, ...] = self.collect_all_errors()
        return group_exceptions(all_errors, self.source_document)

    def attach_error(self, title: str, reltive_path: Sequence[str | int] = (), /, target: SpanTarget = SpanTarget.VALUE) -> JsonDiagnosticError:
        target_path: tuple[str | int, ...] = self._current_path + tuple(reltive_path)
        span: TextSpan | None = self.source_document.get_span(target_path, target=target)

        formatter: ErrorMessageFormatter = get_global_message_formatter()
        message: str = formatter.format(title, self.source_document, span)
        location: Location | None = span.start if span is not None else None

        diagnostic_error = JsonDiagnosticError(message=message, path=self._current_path, location=location)

        self.errors.append(diagnostic_error)

        return diagnostic_error
