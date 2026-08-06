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

from tortoise_json_diagnostics import StrPath, TextSpan
from tortoise_json_diagnostics import LocationFormatter, set_global_location_formatter
from tortoise_json_diagnostics import DefaultSpansFormatter, set_global_spans_formatter

class CompactLocationFormatter(LocationFormatter):
    def format(self, file_path: StrPath | None, span: TextSpan | None, /) -> str:
        if not file_path:
            return ""
        if not span:
            return str(file_path)
        return f"{file_path}:{span.end.line + 1}:{span.end.column + 1}"

set_global_location_formatter(CompactLocationFormatter())
set_global_spans_formatter(DefaultSpansFormatter(lines_before=0, lines_after=0))

parser = DiagnosticJsonParser(validator)

data = parser.parse_text(json_text, path="input.json")
