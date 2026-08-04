import json
from pathlib import Path
from collections import defaultdict
from collections.abc import Sequence

from json_source_map import calculate
from json_source_map.types import TSourceMap, Entry
from jsonschema import Validator, ValidationError

from .errors import JsonValidationError, TJsonValidationError
from .formatters import TextSpan, LocationFormatter, get_global_location_formatter
from .handlers import IErrorHandler, DefaultValidationHandler, get_json_pointer
from .types import Json, StrPath


def _get_error_position(source_map: TSourceMap, error: JsonValidationError) -> tuple[int, int]:
    first_validation_error: ValidationError | None = error.validation_errors[0] if error.validation_errors else None
    if not first_validation_error or not first_validation_error.absolute_path:
        return (0, 0)
    json_pointer: str = get_json_pointer(first_validation_error.absolute_path)
    entry: Entry | None = source_map.get(json_pointer)
    if entry and entry.value_start:
        return (entry.value_start.line, entry.value_start.column)
    return (0, 0)


def _group_exceptions_by_json_path(
    errors: Sequence[JsonValidationError],
    /,
    source_map: TSourceMap,
    file_path: StrPath | None,
    *,
    depth: int = 0,
) -> ExceptionGroup[TJsonValidationError] | None:
    if not errors:
        return None

    sorted_errors: list[JsonValidationError] = sorted(errors, key=lambda error: _get_error_position(source_map, error))

    leaf_errors: list[JsonValidationError] = []
    grouped_errors: dict[str | int, list[JsonValidationError]] = defaultdict(list)

    for error in sorted_errors:
        first_validation_error: ValidationError | None = error.validation_errors[0] if error.validation_errors else None
        path: list[str | int] = list(first_validation_error.absolute_path) if first_validation_error else []

        if len(path) == depth:
            leaf_errors.append(error)
        else:
            current_key: str | int = path[depth]
            grouped_errors[current_key].append(error)

    child_nodes: list[TJsonValidationError] = []
    child_nodes.extend(leaf_errors)

    for sub_errors in grouped_errors.values():
        nested_result: TJsonValidationError | None = _group_exceptions_by_json_path(
            sub_errors,
            source_map,
            file_path,
            depth=depth + 1,
        )
        if nested_result is not None:
            child_nodes.append(nested_result)

    if not child_nodes:
        return None

    if depth == 0:
        location_formatter: LocationFormatter = get_global_location_formatter()
        location_info: str = location_formatter.format(file_path, None)

        label: str = "JSON Validation Error"
        title: str = f"{label}\n{location_info}"
    else:
        parent_error: JsonValidationError | None = errors[0] if errors else None
        first_validation_error: ValidationError | None = parent_error.validation_errors[0] if parent_error and parent_error.validation_errors else None
        current_prefix_path: list[str | int] = (
            list(first_validation_error.absolute_path)[:depth]
            if first_validation_error and len(first_validation_error.absolute_path) >= depth
            else []
        )
        last_key: str | int = current_prefix_path[-1] if current_prefix_path else ""

        json_pointer: str = get_json_pointer(current_prefix_path)
        entry: Entry | None = source_map.get(json_pointer)
        span: TextSpan | None = TextSpan.from_entry_key(entry) if entry else None

        location_formatter: LocationFormatter = get_global_location_formatter()
        location_info: str = location_formatter.format(file_path, span)

        label: str = f"Item [{last_key}]" if isinstance(last_key, int) else f"Property {last_key!r}"
        title: str = f"{label}\n{location_info}"

    return ExceptionGroup(title, child_nodes)


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

        root_exception_group = _group_exceptions_by_json_path(collected_exceptions, source_map, path)

        return raw_data, root_exception_group
