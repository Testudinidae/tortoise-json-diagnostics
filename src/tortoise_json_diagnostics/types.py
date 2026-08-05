from collections.abc import Sequence
from dataclasses import dataclass

from json_source_map.types import Entry, Location, TSourceMap

from ._utils import get_json_pointer


@dataclass(slots=True, frozen=True)
class TextSpan:
    start: Location
    end: Location

    @classmethod
    def from_entry_key(cls, entry: Entry, /) -> TextSpan | None:
        if entry.key_start is not None and entry.key_end is not None:
            return cls(start=entry.key_start, end=entry.key_end)
        return None

    @classmethod
    def from_entry_value(cls, entry: Entry, /) -> TextSpan:
        return cls(start=entry.value_start, end=entry.value_end)

    @classmethod
    def from_json_pointer(cls, pointer: str, /, source_map: TSourceMap, is_key: bool = False) -> TextSpan | None:
        entry: Entry | None = source_map.get(pointer)
        if is_key:
            span: TextSpan | None = TextSpan.from_entry_key(entry) if entry else None
        else:
            span: TextSpan | None = TextSpan.from_entry_value(entry) if entry else None

        return span

    @classmethod
    def from_json_path(cls, path: Sequence[str | int], /, source_map: TSourceMap, is_key: bool = False) -> TextSpan | None:
        json_pointer: str = get_json_pointer(path)
        return TextSpan.from_json_pointer(json_pointer, source_map, is_key=is_key)


@dataclass(frozen=True, slots=True)
class ErrorTarget():
    group_path: tuple[str | int, ...]
    location: Location | None
