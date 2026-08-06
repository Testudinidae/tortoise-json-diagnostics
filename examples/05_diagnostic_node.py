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
                item_node.attach_error(f"Duplicate id found: {item_id}", ["id"])  # type: ignore[reportUnusedCallResult]

validator = Draft202012Validator(schema)
parser = DiagnosticJsonParser(validator)

node: DiagnosticNode = parser.parse_to_node_text(json_text, "input.json")

validate_duplicate_ids(node)

value = node.value
exception_group = node.to_exception_group()

print(value)

if exception_group:
    raise exception_group
