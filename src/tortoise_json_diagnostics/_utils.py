from collections.abc import Sequence


def get_json_pointer(path: Sequence[str | int], /) -> str:
    if not path:
        return ""

    escaped_parts: list[str] = []
    for path_element in path:
        element_string: str = str(path_element).replace("~", "~0").replace("/", "~1")
        escaped_parts.append(element_string)

    return "/" + "/".join(escaped_parts)
