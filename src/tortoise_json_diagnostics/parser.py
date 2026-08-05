import json
from pathlib import Path
from collections import defaultdict
from collections.abc import Sequence

from json_source_map import calculate
from json_source_map.types import TSourceMap
from jsonschema import Validator, ValidationError

from .errors import JsonValidationError, TJsonValidationError
from .formatters import TextSpan, ErrorGroupFormatter, get_global_nested_group_formatter, LocationFormatter, get_global_location_formatter
from .handlers import IErrorHandler, DefaultValidationHandler
from .typing import Json, StrPath


def _get_node_position(node: TJsonValidationError) -> int:
    if isinstance(node, JsonValidationError):
        return node.target.location.position if node.target and node.target.location else 0

    else:
        if node.exceptions:
            return _get_node_position(node.exceptions[0])
        return 0


def _group_exceptions_by_json_path(
    errors: Sequence[JsonValidationError],
    /,
    source_map: TSourceMap,
    json_text: str,
    file_path: StrPath | None,
    *,
    depth: int = 0,
) -> ExceptionGroup[TJsonValidationError] | None:
    if not errors:
        return None

    sorted_errors: list[JsonValidationError] = sorted(errors, key=lambda error: error.target.location.position if error.target.location else 0)
    leaf_errors: list[JsonValidationError] = []
    grouped_errors: dict[str | int, list[JsonValidationError]] = defaultdict(list)

    for error in sorted_errors:
        if len(error.target.group_path) == depth:
            leaf_errors.append(error)
        else:
            current_key: str | int = error.target.group_path[depth]
            grouped_errors[current_key].append(error)

    child_nodes: list[TJsonValidationError] = []
    child_nodes.extend(leaf_errors)

    for sub_errors in grouped_errors.values():
        nested_result: TJsonValidationError | None = _group_exceptions_by_json_path(
            sub_errors,
            source_map,
            json_text,
            file_path,
            depth=depth + 1,
        )
        if nested_result is not None:
            child_nodes.append(nested_result)

    if not child_nodes:
        return None

    child_nodes.sort(key=_get_node_position)

    if depth == 0:
        location_formatter: LocationFormatter = get_global_location_formatter()
        location_info: str = location_formatter.format(file_path, None)

        label: str = "JSON Validation Error"
        message: str = f"{label}\n{location_info}"
    else:
        parent_error: JsonValidationError | None = errors[0] if errors else None
        first_validation_error: ValidationError | None = parent_error.validation_errors[0] if parent_error and parent_error.validation_errors else None
        current_prefix_path: list[str | int] = (
            list(first_validation_error.absolute_path)[:depth]
            if first_validation_error and len(first_validation_error.absolute_path) >= depth
            else []
        )
        span: TextSpan | None = TextSpan.from_json_path(current_prefix_path, source_map, is_key=True)

        formatter: ErrorGroupFormatter = get_global_nested_group_formatter()
        message: str = formatter.format(current_prefix_path, json_text, file_path, span)

    return ExceptionGroup(message, child_nodes)


class DiagnosticJsonParser:
    def __init__(self, validator: Validator, /, handlers: list[IErrorHandler] | None = None) -> None:
        super().__init__()

        self.validator = validator
        self.handlers: list[IErrorHandler] = []
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

    def try_parse_file(self, path: StrPath, /, encoding: str | None = None) -> tuple[Json, ExceptionGroup[TJsonValidationError] | None]:
        text: str = Path(path).read_text(encoding=encoding)

        return self.try_parse_text(text, path)

    def try_parse_text(self, text: str, /, path: StrPath | None = None) -> tuple[Json, ExceptionGroup[TJsonValidationError] | None]:
        raw_data: Json = json.loads(text)
        remaining_errors: Sequence[ValidationError] = list(self.validator.iter_errors(raw_data))

        if not remaining_errors:
            return raw_data, None

        source_map: TSourceMap = calculate(text)
        collected_exceptions: list[JsonValidationError] = []

        for handler in self.handlers:
            if not remaining_errors:
                break

            sub_errors, remaining_errors = handler.handle(self.validator, remaining_errors, source_map, text, path)
            collected_exceptions.extend(sub_errors)

        root_exception_group = _group_exceptions_by_json_path(collected_exceptions, source_map, text, path)

        return raw_data, root_exception_group
