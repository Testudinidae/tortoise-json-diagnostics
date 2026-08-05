from abc import ABC, abstractmethod
from collections.abc import Sequence

from json_source_map.types import TSourceMap
from jsonschema import Validator, ValidationError

from ..errors import JsonValidationError
from ..formatters import TextSpan, ErrorMessageFormatter, get_global_message_formatter
from ..types import ErrorTarget
from ..typing import StrPath


class IErrorHandler(ABC):
    @abstractmethod
    def handle(self, validator: Validator, validation_errors: Sequence[ValidationError], source_map: TSourceMap, json_text: str, file_path: StrPath | None, /) -> tuple[Sequence[JsonValidationError], Sequence[ValidationError]]:
        ...


class DefaultValidationHandler(IErrorHandler):
    def handle(self, validator: Validator, validation_errors: Sequence[ValidationError], source_map: TSourceMap, json_text: str, file_path: StrPath | None, /) -> tuple[Sequence[JsonValidationError], Sequence[ValidationError]]:
        errors: list[JsonValidationError] = []

        for validation_error in validation_errors:
            json_path: tuple[str | int, ...] = tuple(validation_error.absolute_path)
            span: TextSpan | None = TextSpan.from_json_path(json_path, source_map)

            formatter: ErrorMessageFormatter = get_global_message_formatter()
            message: str = formatter.format(validation_error.message, json_text, file_path, span)
            target = ErrorTarget(json_path, span.start if span is not None else None)

            error = JsonValidationError(message, validator, [validation_error], target)

            errors.append(error)

        return errors, []
