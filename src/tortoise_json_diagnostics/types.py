from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum, auto
from typing import overload, Literal

from json_source_map import calculate
from json_source_map.types import Entry, Location, TSourceMap

from ._utils import get_json_pointer
from .typing import StrPath


class SpanTarget(StrEnum):
    KEY = auto()
    VALUE = auto()
    FULL = auto()


@dataclass(slots=True, frozen=True)
class TextSpan:
    start: Location
    end: Location

    @overload
    @classmethod
    def from_entry(cls, entry: Entry, /, target: Literal[SpanTarget.KEY]) -> TextSpan | None:  ...

    @overload
    @classmethod
    def from_entry(cls, entry: Entry, /, target: Literal[SpanTarget.VALUE] = SpanTarget.VALUE) -> TextSpan:  ...

    @overload
    @classmethod
    def from_entry(cls, entry: Entry, /, target: Literal[SpanTarget.FULL]) -> TextSpan:  ...

    @classmethod
    def from_entry(cls, entry: Entry, /, target: SpanTarget = SpanTarget.VALUE) -> TextSpan | None:
        match target:
            case SpanTarget.KEY:
                if entry.key_start is not None and entry.key_end is not None:
                    return cls(start=entry.key_start, end=entry.key_end)
                return None
            case SpanTarget.VALUE:
                return cls(start=entry.value_start, end=entry.value_end)
            case SpanTarget.FULL:
                if entry.key_start is not None and entry.key_end is not None:
                    return cls(start=entry.key_start, end=entry.value_end)
                return cls(start=entry.value_start, end=entry.value_end)


@dataclass(slots=True, frozen=True)
class SourceDocument:
    text: str
    source_map: TSourceMap
    file_path: StrPath | None = None

    @classmethod
    def from_text(cls, text: str, /, file_path: StrPath | None = None) -> SourceDocument:
        source_map: TSourceMap = calculate(text)
        return cls(text=text, source_map=source_map, file_path=file_path)

    def get_span(self, path: Sequence[str | int], /, target: SpanTarget = SpanTarget.VALUE) -> TextSpan | None:
        json_pointer: str = get_json_pointer(path)

        entry: Entry | None = self.source_map.get(json_pointer)

        return TextSpan.from_entry(entry, target=target) if entry else None
