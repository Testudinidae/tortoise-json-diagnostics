from collections.abc import Sequence
from typing import Any, Protocol

from .typing import StrPath
from .types import SourceDocument, SpanTarget, TextSpan


class ErrorMessageFormatter(Protocol):
    def format(
        self,
        title: str,
        source_document: SourceDocument,
        span: TextSpan | None,
    ) -> str:
        ...


class DefaultMessageFormatter(ErrorMessageFormatter):
    def format(
        self,
        title: str,
        source_document: SourceDocument,
        span: TextSpan | None,
    ) -> str:
        location_formatter: LocationFormatter = get_global_location_formatter()
        location_info: str = location_formatter.format(source_document.file_path, span)

        spans_formatter: TextSpansFormatter[Any] = get_global_spans_formatter()
        code_snippet: str = spans_formatter.format(source_document.text, [span]) if span else ""

        parts: list[str] = [title]
        if location_info:
            parts.append(location_info)
        if code_snippet:
            parts.append(code_snippet)

        return "\n".join(parts)


class ErrorGroupFormatter(Protocol):
    def format(
        self,
        source_document: SourceDocument,
        json_path: Sequence[str | int],
        /,
    ) -> str:
        ...


class DefaultNestedGroupFormatter(ErrorGroupFormatter):
    def format(
        self,
        source_document: SourceDocument,
        json_path: Sequence[str | int],
        /,
    ) -> str:
        last_key: str | int = json_path[-1] if json_path else ""
        title: str = f"Item [{last_key}]" if isinstance(last_key, int) else f"Property {last_key!r}"

        if isinstance(last_key, str):
            span: TextSpan | None = source_document.get_span(json_path, SpanTarget.KEY)
        else:
            span: TextSpan | None = source_document.get_span(json_path, SpanTarget.VALUE)

        location_formatter: LocationFormatter = get_global_location_formatter()
        location_info: str = location_formatter.format(source_document.file_path, span)

        parts: list[str] = [title]
        if location_info:
            parts.append(location_info)

        return "\n".join(parts)


class LocationFormatter(Protocol):
    def format(self, file_path: StrPath | None, span: TextSpan | None, /) -> str:
        ...


class DefaultLocationFormatter(LocationFormatter):
    def format(self, file_path: StrPath | None, span: TextSpan | None, /) -> str:
        parts: list[str] = []
        if file_path:
            parts.append(f'File "{file_path}"')
        if span:
            line_number: int = span.end.line + 1
            column_number: int = span.end.column + 1

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


_global_message_formatter: ErrorMessageFormatter = DefaultMessageFormatter()
_global_nested_group_formatter: ErrorGroupFormatter = DefaultNestedGroupFormatter()
_global_location_formatter: LocationFormatter = DefaultLocationFormatter()
_global_spans_formatter: TextSpansFormatter[Any] = DefaultSpansFormatter()


def set_global_message_formatter(formatter: ErrorMessageFormatter, /) -> None:
    global _global_message_formatter
    _global_message_formatter = formatter


def get_global_message_formatter() -> ErrorMessageFormatter:
    return _global_message_formatter


def set_global_nested_group_formatter(formatter: ErrorGroupFormatter, /) -> None:
    global _global_nested_group_formatter
    _global_nested_group_formatter = formatter


def get_global_nested_group_formatter() -> ErrorGroupFormatter:
    return _global_nested_group_formatter


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
