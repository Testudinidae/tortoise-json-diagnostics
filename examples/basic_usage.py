import json
from pathlib import Path

from jsonschema import Draft202012Validator

from tortoise_json_diagnostics import DiagnosticJsonParser


def main() -> None:
    base_dir = Path(__file__).parent
    manifest_schema_path = base_dir / "schemas" / "user_manifest.json"
    bad_data_path = base_dir / "data" / "bad_user.json"

    manifest_schema = json.loads(manifest_schema_path.read_text(encoding="utf-8"))

    validator = Draft202012Validator(manifest_schema, resolver=None)

    parser = DiagnosticJsonParser(validator)

    data = parser.parse_file(bad_data_path)


if __name__ == "__main__":
    main()
