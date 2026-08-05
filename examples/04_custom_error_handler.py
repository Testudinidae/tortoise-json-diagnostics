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

from tortoise_json_diagnostics import IErrorHandler, JsonValidationError, TextSpan, ErrorMessageFormatter, get_global_message_formatter, ErrorTarget

class CustomTypeMismatchHandler(IErrorHandler):
    def handle(self, validator, validation_errors, source_map, json_text, file_path, /):
        handled: list[JsonValidationError] = []
        unhandled = []

        for error in validation_errors:
            if error.validator == "type":
                json_path: tuple[str | int, ...] = tuple(error.absolute_path)
                span: TextSpan | None = TextSpan.from_json_path(json_path, source_map)

                formatter: ErrorMessageFormatter = get_global_message_formatter()
                message: str = formatter.format(f"[Type Mismatch] {error.message}", json_text, file_path, span)
                target = ErrorTarget(json_path, span.start if span is not None else None)

                error = JsonValidationError(message, validator, [error], target)

                handled.append(error)
            else:
                unhandled.append(error)

        return handled, unhandled

parser = DiagnosticJsonParser(validator, handlers=[CustomTypeMismatchHandler()])

data = parser.parse_text(json_text, path="input.json")
