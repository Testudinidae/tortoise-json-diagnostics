# tortoise-json-diagnostics

[![Python Version](https://img.shields.io/badge/python-3.14%2B-blue.svg)](https://www.python.org/downloads/)

A modern, highly customizable Python library for formatting JSON Schema validation errors into clear, human-readable code snippets and nested `ExceptionGroup` trees.

## Overview & Motivation

JSON Schema validation tools provide powerful, localized data checks. They operate on the assumption that errors are simple, self-contained, and isolated—a design property that keeps schema definitions clean and manageable without burdening them with complex, multi-field, or contextual domain logic.

However, in real-world applications, downstream validation failures or business logic errors almost always point back to issues within the original JSON source file.

`tortoise-json-diagnostics` bridges this gap:
* It formats raw `jsonschema` errors into human-readable diagnostics with source code snippets and position tracking.
* It parses JSON into a mutable `DiagnosticNode` AST tree, allowing developers to dynamically inspect code locations, attach or prune custom domain errors on specific nodes, and export the aggregated result as an `ExceptionGroup`.

## Key Features

* 🌳 **Nested ExceptionGroup Trees**: Groups flat `jsonschema` validation errors into structured hierarchies matching your JSON layout.
* 🧩 **DiagnosticNode AST Parsing**: Parses JSON into a fully mutable semantic AST tree with values and errors.
* 🛠️ **Dynamic Error Attachment**: Attach custom domain errors directly to AST nodes and export them via `to_exception_group()`.
* 🧼 **Clean Value Access**: Node `.value` property returns raw Python structures clean of error metadata while remaining fully mutable.
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
    def format(self, file_path: StrPath | None, span: TextSpan | None, /) -> str:
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
from tortoise_json_diagnostics.handlers import AdditionalPropertiesHandler

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

---

### AST Node Parsing & Custom Error Attachment

Parse raw JSON into a `DiagnosticNode` tree to perform contextual domain validation, attach custom errors directly to target nodes, and export everything via `ExceptionGroup`:

```python
from collections import defaultdict
from jsonschema import Draft202012Validator
from tortoise_json_diagnostics import DiagnosticJsonParser, DiagnosticNode

schema = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["id", "name"],
        "properties": {
            "id": {"type": "integer", "minimum": 0},
            "name": {"type": "string"},
        }
    }
}

json_text = """
[
    {
        "id": 1,
        "name": "foo"
    },
    {
        "id": 1,
        "name": "bar"
    }
]
""".strip()

def validate_duplicate_ids(root_node: DiagnosticNode, /) -> None:
    id_to_nodes_map: defaultdict[int, list[DiagnosticNode]] = defaultdict(list)

    for item_node in root_node:
        id_node: DiagnosticNode = item_node["id"]
        item_id: int = id_node.value
        id_to_nodes_map[item_id].append(item_node)

    for item_id, item_nodes in id_to_nodes_map.items():
        if len(item_nodes) > 1:
            for item_node in item_nodes:
                item_node.attach_error(f"Duplicate id found: {item_id}", ["id"])

validator = Draft202012Validator(schema)
parser = DiagnosticJsonParser(validator)

node: DiagnosticNode = parser.parse_to_node_text(json_text, "input.json")

validate_duplicate_ids(node)

value = node.value
exception_group = node.to_exception_group()

if exception_group:
    raise exception_group
```

When raised, `to_exception_group()` produces a structured output pointing directly to the exact file locations of the duplicate entries:
```text
  | ExceptionGroup: JSON Validation Error
  | File "input.json" (2 sub-exceptions)
  +-+---------------- 1 ----------------
    | ExceptionGroup: Item [0]
    | File "input.json", line 5, column 6 (1 sub-exception)
    +-+---------------- 1 ----------------
      | tortoise_json_diagnostics.errors.JsonDiagnosticError: Duplicate id found: 1
      | File "input.json", line 3, column 16
      |    1 | [
      |    2 |     {
      |    3 |         "id": 1,
      |                      ^
      |    4 |         "name": "foo"
      +------------------------------------
    +---------------- 2 ----------------
    | ExceptionGroup: Item [1]
    | File "input.json", line 9, column 6 (1 sub-exception)
    +-+---------------- 1 ----------------
      | tortoise_json_diagnostics.errors.JsonDiagnosticError: Duplicate id found: 1
      | File "input.json", line 7, column 16
      |    5 |     },
      |    6 |     {
      |    7 |         "id": 1,
      |                      ^
      |    8 |         "name": "bar"
      +------------------------------------
```

## License

[MIT License](LICENSE.txt)
