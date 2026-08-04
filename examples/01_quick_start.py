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

parser = DiagnosticJsonParser(validator)

json_text = '{"name": 123, "age": -5}'
data = parser.parse_text(json_text, path="input.json")
