from jsonschema import Draft202012Validator
from tortoise_json_diagnostics import DiagnosticJsonParser

schema = {
    "type": "object",
    "required": ["name", "age"],
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer", "minimum": 0},
    },
}

validator = Draft202012Validator(schema)

json_text = '{"name": 123, "age": -5}'

from tortoise_json_diagnostics import IErrorHandler, JsonValidationError

class CustomTypeMismatchHandler(IErrorHandler):
    def handle(self, validator, validation_errors, source_map, json_text, file_path, /):
        handled: list[JsonValidationError] = []
        unhandled = []

        for error in validation_errors:
            if error.validator == "type":
                message = f"[Type Mismatch] {error.message}"
                handled.append(JsonValidationError(message, validator, [error]))
            else:
                unhandled.append(error)

        return handled, unhandled

parser = DiagnosticJsonParser(validator, handlers=[CustomTypeMismatchHandler()])

data = parser.parse_text(json_text, path="input.json")
