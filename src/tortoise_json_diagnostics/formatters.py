from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from json_source_map.types import Entry, Location

from .types import StrPath


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


class LocationFormatter(Protocol):
    def format(self, file_path: StrPath | None, span: TextSpan | None, /) -> str:
        ...


class DefaultLocationFormatter(LocationFormatter):
    def format(self, file_path: StrPath | None, span: TextSpan | None, /) -> str:
        parts: list[str] = []
        if file_path:
            parts.append(f'File "{file_path}"')
        if span:
            line_number: int = span.start.line + 1
            column_number: int = span.start.column + 1

            parts.append(f"line {line_number}")
            parts.append(f"column {column_number}")
        return ", ".join(parts)


class TextSpansFormatter[T: TextSpan](Protocol):
    def format(self, text: str, spans: Sequence[T], /) -> str:
        ...


class DefaultSpansFormatter(TextSpansFormatter[TextSpan]):
    def __init__(
        self, /,
        lines_before: int = 2,
        lines_after: int = 1,
        min_tab_size: int = 4
    ):
        super().__init__()
        self.lines_before = lines_before
        self.lines_after = lines_after
        self.min_tab_size = min_tab_size

    def format(self, text: str, spans: Sequence[TextSpan], /) -> str:
        if not spans:
            return ""

        span: TextSpan = spans[-1]

        lines: list[str] = text.splitlines()

        display_start_line_index: int = max(0, span.start.line - self.lines_before)
        display_end_line_index: int = min(len(lines), span.start.line + 1 + self.lines_after)

        gutter_width: int = max(len(str(display_end_line_index)), self.min_tab_size)

        output_lines: list[str] = []

        for line_index in range(display_start_line_index, display_end_line_index):
            line_number: int = line_index + 1
            line_content: str = lines[line_index]
            output_lines.append(f"{line_number:{gutter_width}d} | {line_content}")

            if line_index == span.start.line:
                padding_size: int = gutter_width + 3 + span.start.column
                if span.start.line == span.end.line:
                    highlight_length: int = max(1, span.end.column - span.start.column)
                else:
                    highlight_length: int = max(1, len(line_content) - span.start.column)

                pointer_line: str = f"{' ' * padding_size}{'^' * highlight_length}"
                output_lines.append(pointer_line)

        return "\n".join(output_lines)


_global_location_formatter: LocationFormatter = DefaultLocationFormatter()
_global_spans_formatter: TextSpansFormatter[Any] = DefaultSpansFormatter()


def set_global_location_formatter(formatter: LocationFormatter, /) -> None:
    global _global_location_formatter
    _global_location_formatter = formatter


def get_global_location_formatter() -> LocationFormatter:
    return _global_location_formatter


def set_global_spans_formatter(formatter: TextSpansFormatter[Any], /) -> None:
    global _global_spans_formatter
    _global_spans_formatter = formatter


def get_global_spans_formatter() -> TextSpansFormatter[Any]:
    return _global_spans_formatter
