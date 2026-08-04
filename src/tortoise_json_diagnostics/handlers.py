
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from json_source_map.types import Entry, TSourceMap
from jsonschema import Validator, ValidationError

from .errors import JsonValidationError
from .formatters import TextSpan, LocationFormatter, TextSpansFormatter, get_global_location_formatter, get_global_spans_formatter
from .types import StrPath


def get_json_pointer(path: Sequence[str | int], /) -> str:
    if not path:
        return ""

    escaped_parts: list[str] = []
    for path_element in path:
        element_string: str = str(path_element).replace("~", "~0").replace("/", "~1")
        escaped_parts.append(element_string)

    return "/" + "/".join(escaped_parts)


class IErrorHandler(ABC):
    @abstractmethod
    def handle(self, validator: Validator, validation_errors: Sequence[ValidationError], source_map: TSourceMap, json_text: str, file_path: StrPath | None, /) -> tuple[Sequence[JsonValidationError], Sequence[ValidationError]]:
        ...


class DefaultValidationHandler(IErrorHandler):
    def handle(self, validator: Validator, validation_errors: Sequence[ValidationError], source_map: TSourceMap, json_text: str, file_path: StrPath | None, /) -> tuple[Sequence[JsonValidationError], Sequence[ValidationError]]:
        errors: list[JsonValidationError] = []

        for validation_error in validation_errors:
            json_pointer: str = get_json_pointer(validation_error.absolute_path)
            entry: Entry | None = source_map.get(json_pointer)
            span: TextSpan | None = TextSpan.from_entry_value(entry) if entry else None

            location_formatter: LocationFormatter = get_global_location_formatter()
            location_info: str = location_formatter.format(file_path, span)

            spans_formatter: TextSpansFormatter[Any] = get_global_spans_formatter()
            code_snippet: str = spans_formatter.format(json_text, [span]) if span else ""

            message = f"{validation_error.message}\n{location_info}\n{code_snippet}"

            error = JsonValidationError(message, validator, [validation_error])

            errors.append(error)

        return errors, []
