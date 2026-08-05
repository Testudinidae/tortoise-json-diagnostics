# tortoise-json-diagnostics

[![Python Version](https://img.shields.io/badge/python-3.14%2B-blue.svg)](https://www.python.org/downloads/)

A modern, highly customizable Python library for formatting JSON Schema validation errors into clear, human-readable code snippets and nested `ExceptionGroup` trees.


## Key Features

* 🌳 **Nested ExceptionGroup Trees**: Automatically groups flat `jsonschema` validation errors into structured hierarchy matching your JSON schema layout.
* 🧩 **Extensible Handler Pipeline**: Allows custom error handlers to intercept, transform, and prune specific validation errors before fallback processing.
* ⚙️ **Global Formatter Registry**: Easily switch or implement custom location and code snippet formatters (e.g., plain text, rich, ...).
* 🐍 **Modern Python Native**: Built for modern Python with strict typing


## Visual Output

Instead of unreadable raw validation objects, `tortoise-json-diagnostics` formats error groups like this:

```text
  | ExceptionGroup: JSON Validation Error
  | File "input.json" (2 sub-exceptions)
  +-+---------------- 1 ----------------
    | ExceptionGroup: Property 'name'
    | File "input.json", line 2, column 11 (1 sub-exception)
    +-+---------------- 1 ----------------
      | tortoise_json_diagnostics.errors.JsonValidationError: 123 is not of type 'string'
      | File "input.json", line 2, column 16
      |    1 | {
      |    2 |     "name": 123,
      |                    ^^^
      |    3 |     "age": -5
      +------------------------------------
    +---------------- 2 ----------------
    | ExceptionGroup: Property 'age'
    | File "input.json", line 3, column 10 (1 sub-exception)
    +-+---------------- 1 ----------------
      | tortoise_json_diagnostics.errors.JsonValidationError: -5 is less than the minimum of 0
      | File "input.json", line 3, column 14
      |    1 | {
      |    2 |     "name": 123,
      |    3 |     "age": -5
      |                   ^^
      |    4 | }
      +------------------------------------
```

## Installation

Using `uv` (recommended):

```bash
uv add tortoise-json-diagnostics
```

Using `pip`:

```bash
pip install tortoise-json-diagnostics
```

## Quick Start

```python
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

parser = DiagnosticJsonParser(validator)

json_text = """
{
    "name": 123,
    "age": -5
}
""".strip()

data = parser.parse_text(json_text, path="input.json")

```

## Advanced Usage

### Global Formatters

Register custom formatters for file locations or text snippets:

```python
from tortoise_json_diagnostics import LocationFormatter, set_global_location_formatter
from tortoise_json_diagnostics import DefaultSpansFormatter, set_global_spans_formatter

class CompactLocationFormatter(LocationFormatter):
    def format(self, file_path, span, /) -> str:
        if not file_path:
            return ""
        if not span:
            return str(file_path)
        return f"{file_path}:{span.end.line + 1}:{span.end.column + 1}"

set_global_location_formatter(CompactLocationFormatter())
set_global_spans_formatter(DefaultSpansFormatter(lines_before=0, lines_after=0))
```

```text
  | ExceptionGroup: JSON Validation Error
  | input.json (2 sub-exceptions)
  +-+---------------- 1 ----------------
    | ExceptionGroup: Property 'name'
    | input.json:2:11 (1 sub-exception)
    +-+---------------- 1 ----------------
      | tortoise_json_diagnostics.errors.JsonValidationError: 123 is not of type 'string'
      | input.json:2:16
      |    2 |     "name": 123,
      |                    ^^^
      +------------------------------------
    +---------------- 2 ----------------
    | ExceptionGroup: Property 'age'
    | input.json:3:10 (1 sub-exception)
    +-+---------------- 1 ----------------
      | tortoise_json_diagnostics.errors.JsonValidationError: -5 is less than the minimum of 0
      | input.json:3:14
      |    3 |     "age": -5
      |                   ^^
      +------------------------------------
```

---


### Built-in Handlers

The package includes built-in handlers for specific JSON Schema validation cases, such as handling additional properties or required fields:

```python
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

```

```text
  | ExceptionGroup: JSON Validation Error
  | File "input.json" (2 sub-exceptions)
  +-+---------------- 1 ----------------
    | tortoise_json_diagnostics.handlers.additional_properties_handler.AdditionalPropertyError: Additional properties are not allowed ('nmae' was unexpected). Did you mean: 'name'?
    | File "input.json", line 2, column 11
    |    1 | {
    |    2 |     "nmae": "foo",
    |            ^^^^^^
    |    3 |     "age": 5,
    +---------------- 2 ----------------
    | tortoise_json_diagnostics.handlers.additional_properties_handler.AdditionalPropertyError: Additional properties are not allowed ('unknown_field' was unexpected)
    | File "input.json", line 4, column 20
    |    2 |     "nmae": "foo",
    |    3 |     "age": 5,
    |    4 |     "unknown_field": false
    |            ^^^^^^^^^^^^^^^
    |    5 | }
    +------------------------------------
```

---

### Custom Error Handlers

You can intercept specific `ValidationError`s before they hit the default handler by implementing `IErrorHandler`:

```python
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
```

```text
  | ExceptionGroup: JSON Validation Error
  | File "input.json" (2 sub-exceptions)
  +-+---------------- 1 ----------------
    | ExceptionGroup: Property 'name'
    | File "input.json", line 2, column 11 (1 sub-exception)
    +-+---------------- 1 ----------------
      | tortoise_json_diagnostics.errors.JsonValidationError: [Type Mismatch] 123 is not of type 'string'
      | File "input.json", line 2, column 16
      |    1 | {
      |    2 |     "name": 123,
      |                    ^^^
      |    3 |     "age": -5
      +------------------------------------
    +---------------- 2 ----------------
    | ExceptionGroup: Property 'age'
    | File "input.json", line 3, column 10 (1 sub-exception)
    +-+---------------- 1 ----------------
      | tortoise_json_diagnostics.errors.JsonValidationError: -5 is less than the minimum of 0
      | File "input.json", line 3, column 14
      |    1 | {
      |    2 |     "name": 123,
      |    3 |     "age": -5
      |                   ^^
      |    4 | }
      +------------------------------------
```


## License

[MIT License](LICENSE.txt)
