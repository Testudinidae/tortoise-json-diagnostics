from abc import ABC, abstractmethod
from collections import defaultdict, UserList, UserDict
from collections.abc import Sequence
import json
from pathlib import Path
from typing import Any

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

    def parse_to_node_file(self, path: StrPath, /, encoding: str | None = None) -> DiagnosticNodeBase[Json]:
        text: str = Path(path).read_text(encoding=encoding)
        return self.parse_to_node_text(text, path)

    def parse_to_node_text(self, text: str, /, path: StrPath | None = None) -> DiagnosticNodeBase[Json]:
        raw_data: Json = json.loads(text)
        source_document: SourceDocument = SourceDocument.from_text(text, file_path=path)
        remaining_errors: Sequence[ValidationError] = list(self.validator.iter_errors(raw_data))

        collected_exceptions: list[JsonDiagnosticError] = []
        if remaining_errors:
            collected_exceptions = self._run_handlers(remaining_errors, source_document)

        return create_diagnostic_node(raw_data, collected_exceptions, source_document)

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


def create_diagnostic_node(data: Any, errors: Sequence[JsonDiagnosticError], source_document: SourceDocument, *, path: Sequence[str | int] = ()) -> DiagnosticNodeBase[Any]:
    if isinstance(data, dict):
        return DiagnosticObjectNode(data, errors, source_document, path=path)
    elif isinstance(data, list):
        return DiagnosticArrayNode(data, errors, source_document, path=path)
    else:
        return DiagnosticNode(data, errors, source_document, path=path)


class DiagnosticNodeBase[T](ABC):
    def __init__(self, data: T, /, errors: Sequence[JsonDiagnosticError], source_document: SourceDocument, *, path: Sequence[str | int] = ()) -> None:
        super().__init__()

        self.errors: list[JsonDiagnosticError] = list(errors)
        self.source_document: SourceDocument = source_document
        self._path: tuple[str | int, ...] = tuple(path)

    @property
    def path(self) -> tuple[str | int, ...]:
        return self._path

    @property
    @abstractmethod
    def value(self, /) -> T:
        ...

    def __repr__(self, /) -> str:
        return f"{type(self).__name__}(value={self.value}, errors={self.errors})"

    @abstractmethod
    def collect_all_errors(self, /) -> tuple[JsonDiagnosticError, ...]:
        ...

    def to_exception_group(self, /) -> ExceptionGroup[TJsonDiagnosticError] | None:
        errors: tuple[JsonDiagnosticError, ...] = self.collect_all_errors()
        return group_exceptions(errors, self.source_document)

    def attach_error(self, title: str, relative_path: Sequence[str | int] = (), /, target: SpanTarget = SpanTarget.VALUE) -> JsonDiagnosticError:
        target_path: tuple[str | int, ...] = self.path + tuple(relative_path)
        span: TextSpan | None = self.source_document.get_span(target_path, target=target)

        formatter: ErrorMessageFormatter = get_global_message_formatter()
        message: str = formatter.format(title, self.source_document, span)
        location: Location | None = span.start if span is not None else None

        diagnostic_error = JsonDiagnosticError(message=message, path=self.path, location=location)

        self.errors.append(diagnostic_error)

        return diagnostic_error


class DiagnosticNode[T](DiagnosticNodeBase[T]):
    def __init__(self, data: T, /, errors: Sequence[JsonDiagnosticError], source_document: SourceDocument, *, path: Sequence[str | int] = ()) -> None:
        super().__init__(data, errors, source_document, path=path)
        self._value: T = data

    @property
    def value(self, /) -> T:
        return self._value

    @value.setter
    def value(self, value: T, /) -> None:
        self._value = value

    def collect_all_errors(self, /) -> tuple[JsonDiagnosticError, ...]:
        return tuple(self.errors)


class DiagnosticArrayNode[T](DiagnosticNodeBase[list[T]], UserList[DiagnosticNodeBase[T]]):
    def __init__(self, data: list[T], /, errors: Sequence[JsonDiagnosticError], source_document: SourceDocument, *, path: Sequence[str | int] = ()) -> None:
        current_depth: int = len(path)
        current_errors: list[JsonDiagnosticError] = []
        item_errors_groups: list[list[JsonDiagnosticError]] = [[] for _ in range(len(data))]

        for error in errors:
            if len(error.path) <= current_depth:
                current_errors.append(error)
            else:
                index: str | int = error.path[current_depth]
                if isinstance(index, int) and index < len(data):
                    item_errors_groups[index].append(error)
                else:
                    current_errors.append(error)

        DiagnosticNodeBase.__init__(self, data, current_errors, source_document, path=path)

        nodes: list[DiagnosticNodeBase[list[T]]] = [
            create_diagnostic_node(item, item_errors, source_document, path=(*self.path, i))
            for i, (item, item_errors) in enumerate(zip(data, item_errors_groups))
        ]

        UserList.__init__(self, nodes)

    @property
    def value(self, /) -> list[T]:
        return [item_node.value for item_node in self]

    def collect_all_errors(self, /) -> tuple[JsonDiagnosticError, ...]:
        errors: list[JsonDiagnosticError] = [*self.errors]

        for item_node in self:
            errors.extend(item_node.collect_all_errors())

        return tuple(errors)


class DiagnosticObjectNode[T](DiagnosticNodeBase[dict[str, T]], UserDict[str, DiagnosticNodeBase[T]]):
    def __init__(self, data: dict[str, T], /, errors: Sequence[JsonDiagnosticError], source_document: SourceDocument, *, path: Sequence[str | int] = ()) -> None:
        current_depth: int = len(path)
        current_errors: list[JsonDiagnosticError] = []
        child_errors_map: defaultdict[str, list[JsonDiagnosticError]] = defaultdict(list)

        for error in errors:
            if len(error.path) == current_depth:
                current_errors.append(error)
            elif len(error.path) > current_depth:
                child_key: str | int = error.path[current_depth]

                if isinstance(child_key, str):
                    child_errors_map[child_key].append(error)
                else:
                    current_errors.append(error)

        DiagnosticNodeBase.__init__(self, data, current_errors, source_document, path=path)

        child_nodes: dict[str, DiagnosticNodeBase[T]] = {
            key: create_diagnostic_node(value, child_errors_map[key], source_document, path=(*self.path, key))
            for key, value in data.items()
        }

        UserDict.__init__(self, child_nodes)

    @property
    def value(self, /) -> dict[str, T]:
        return {key: value.value for key, value in self.items()}

    def collect_all_errors(self, /) -> tuple[JsonDiagnosticError, ...]:
        errors: list[JsonDiagnosticError] = list(self.errors)

        for child_node in self.values():
            errors.extend(child_node.collect_all_errors())

        return tuple(errors)
