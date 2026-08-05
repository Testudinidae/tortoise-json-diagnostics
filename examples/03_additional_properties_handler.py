from jsonschema import Draft202012Validator
from tortoise_json_diagnostics import DiagnosticJsonParser

schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer", "minimum": 0}
    },
    "additionalProperties": False
}

validator = Draft202012Validator(schema)

json_text = """
{
    "nmae": "foo",
    "age": 5,
    "unknown_field": false
}
""".strip()

from tortoise_json_diagnostics.handlers import AdditionalPropertiesHandler

parser = DiagnosticJsonParser(validator, handlers=[AdditionalPropertiesHandler()])

data = parser.parse_text(json_text, path="input.json")
