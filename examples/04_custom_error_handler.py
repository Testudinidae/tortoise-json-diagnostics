from jsonschema import Draft202012Validator
from tortoise_json_diagnostics import DiagnosticJsonParser

schema = {
    "type": "object",
    "required": ["name", "age"],
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer", "minimum": 0}
    }
}

validator = Draft202012Validator(schema)

json_text = """
{
    "name": 123,
    "age": -5
}
""".strip()

from collections.abc import Sequence
from jsonschema import Validator, ValidationError
from tortoise_json_diagnostics import JsonDiagnosticError, SourceDocument
from tortoise_json_diagnostics import IValidationHandler, SingleValidationError, get_global_message_formatter

class CustomTypeMismatchHandler(IValidationHandler):
    def handle(self, validator: Validator, validation_errors: Sequence[ValidationError], /, source_document: SourceDocument) -> tuple[Sequence[JsonDiagnosticError], Sequence[ValidationError]]:
        handled: list[JsonDiagnosticError] = []
        unhandled: list[ValidationError] = []

        for error in validation_errors:
            if error.validator == "type":
                json_path = tuple(error.absolute_path)
                span = source_document.get_span(json_path)
                location = span.start if span else None

                formatter = get_global_message_formatter()
                message = formatter.format(f"[Type Mismatch] {error.message}", source_document, span)

                error = SingleValidationError(message, json_path, location, validator, error)

                handled.append(error)
            else:
                unhandled.append(error)

        return handled, unhandled

parser = DiagnosticJsonParser(validator, handlers=[CustomTypeMismatchHandler()])

data = parser.parse_text(json_text, path="input.json")
