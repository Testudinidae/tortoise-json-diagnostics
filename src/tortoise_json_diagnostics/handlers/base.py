from abc import ABC, abstractmethod
from collections.abc import Sequence

from jsonschema import Validator, ValidationError

from ..errors import JsonDiagnosticError, SingleValidationError
from ..formatters import TextSpan, ErrorMessageFormatter, get_global_message_formatter
from ..types import SourceDocument, Location


class IValidationHandler(ABC):
    @abstractmethod
    def handle(self, validator: Validator, validation_errors: Sequence[ValidationError], /, source_document: SourceDocument) -> tuple[Sequence[JsonDiagnosticError], Sequence[ValidationError]]:
        ...


class DefaultValidationHandler(IValidationHandler):
    def handle(self, validator: Validator, validation_errors: Sequence[ValidationError], /, source_document: SourceDocument) -> tuple[Sequence[SingleValidationError], Sequence[ValidationError]]:
        errors: list[SingleValidationError] = []

        for validation_error in validation_errors:
            json_path: tuple[str | int, ...] = tuple(validation_error.absolute_path)
            span: TextSpan | None = source_document.get_span(json_path)

            formatter: ErrorMessageFormatter = get_global_message_formatter()
            message: str = formatter.format(validation_error.message, source_document, span)
            location: Location | None = span.start if span else None

            error = SingleValidationError(message, json_path, location, validator, validation_error)

            errors.append(error)

        return errors, []
