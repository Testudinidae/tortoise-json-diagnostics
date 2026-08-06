import json
from pathlib import Path

from jsonschema import Draft202012Validator

from tortoise_json_diagnostics import DiagnosticJsonParser
from tortoise_json_diagnostics.handlers import AdditionalPropertiesHandler


def main() -> None:
    base_dir = Path(__file__).parent
    schema_path = base_dir / "schemas" / "user_manifest.json"
    bad_data_path = base_dir / "data" / "bad_user.json"

    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    validator = Draft202012Validator(schema, resolver=None)

    parser = DiagnosticJsonParser(validator, handlers=[AdditionalPropertiesHandler()])

    data = parser.parse_file(bad_data_path)  # type: ignore[reportUnusedVariable]


if __name__ == "__main__":
    main()
