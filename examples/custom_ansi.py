from collections.abc import Sequence
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from tortoise_json_diagnostics import DiagnosticJsonParser, TextSpan, StrPath, LocationFormatter, TextSpansFormatter, set_global_location_formatter, set_global_spans_formatter
from tortoise_json_diagnostics.handlers import AdditionalPropertiesHandler

class AnsiLocationFormatter(LocationFormatter):
    _CYAN = "\033[36m"
    _GRAY = "\033[90m"
    _RESET = "\033[0m"

    def format(self, file_path: StrPath | None, span: TextSpan | None, /) -> str:
        parts: list[str] = []

        if file_path:
            formatted_file_path: str = f'{self._RESET}File {self._GRAY}"{self._RESET}{self._CYAN}{file_path}{self._RESET}{self._GRAY}"{self._RESET}'
            parts.append(formatted_file_path)

        if span:
            line_number: int = span.end.line + 1
            column_number: int = span.end.column + 1

            formatted_line: str = f"{self._RESET}line {self._CYAN}{line_number}{self._RESET}"
            formatted_column: str = f"{self._RESET}column {self._CYAN}{column_number}{self._RESET}"

            parts.append(formatted_line)
            parts.append(formatted_column)

        return f"{self._GRAY}, {self._RESET}".join(parts)


class AnsiSpansFormatter(TextSpansFormatter[TextSpan]):
    _CYAN = "\033[36m"
    _GRAY = "\033[90m"
    _BOLD_RED = "\033[1;31m"
    _RESET = "\033[0m"

    def __init__(
        self, /,
        lines_before: int = 2,
        lines_after: int = 1,
        truncate_threshold: int = 3,
        min_tab_size: int = 4,
    ):
        super().__init__()

        if truncate_threshold < 3:
            raise ValueError("truncate_threshold must be greater than or equal to 3")

        self.lines_before = lines_before
        self.lines_after = lines_after
        self.truncate_threshold = truncate_threshold
        self.min_tab_size = min_tab_size

    def format(self, text: str, spans: Sequence[TextSpan], /) -> str:
        if not spans:
            return ""

        lines = text.splitlines()
        span = spans[-1]

        display_start_line_index = max(0, span.start.line - self.lines_before)
        display_end_line_index = min(len(lines), span.end.line + 1 + self.lines_after)

        gutter_width = max(len(str(display_end_line_index)), self.min_tab_size)

        output_lines: list[str] = []

        span_line_count = span.end.line - span.start.line + 1
        should_truncate = span_line_count > self.truncate_threshold

        visible_head_count = self.truncate_threshold - 2
        truncate_start_line_index = span.start.line + visible_head_count

        ellipsis_padding: str = ""
        if should_truncate:
            hidden_lines = lines[truncate_start_line_index:span.end.line]
            non_empty_indents = [len(line) - len(line.lstrip(" ")) for line in hidden_lines if line.strip()]
            min_indent = min(non_empty_indents) if non_empty_indents else 0
            ellipsis_padding = " " * min_indent

        for line_index in range(display_start_line_index, display_end_line_index):
            line_num = line_index + 1
            raw_line = lines[line_index]

            if should_truncate and line_index == truncate_start_line_index:
                gutter_space = " " * gutter_width
                colored_ellipsis_gutter = f"{gutter_space} {self._GRAY}|{self._RESET} {ellipsis_padding}{self._BOLD_RED}...{self._RESET}"
                output_lines.append(colored_ellipsis_gutter)
                continue

            elif should_truncate and (truncate_start_line_index <= line_index < span.end.line):
                continue

            formatted_line = self._format_line_content(raw_line, line_index, span)
            colored_gutter = f"{self._CYAN}{line_num:>{gutter_width}d}{self._RESET} {self._GRAY}|{self._RESET}"

            output_lines.append(f"{colored_gutter} {formatted_line}")

        return "\n".join(output_lines)

    def _format_line_content(self, line: str, line_idx: int, span: TextSpan) -> str:
        start_line, end_line = span.start.line, span.end.line

        if line_idx < start_line or line_idx > end_line:
            return line

        col_start = span.start.column if line_idx == start_line else 0
        col_end = span.end.column if line_idx == end_line else len(line)

        before = line[:col_start]
        highlighted = line[col_start:col_end]
        after = line[col_end:]

        return f"{before}{self._BOLD_RED}{highlighted}{self._RESET}{after}"


def main() -> None:
    set_global_location_formatter(AnsiLocationFormatter())
    set_global_spans_formatter(AnsiSpansFormatter())

    base_dir = Path(__file__).parent
    schema_path = base_dir / "schemas" / "user_manifest.json"
    bad_data_path = base_dir / "data" / "bad_user.json"

    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    validator = Draft202012Validator(schema)

    parser = DiagnosticJsonParser(validator, handlers=[AdditionalPropertiesHandler()])

    data = parser.parse_file(bad_data_path)  # type: ignore[reportUnusedVariable]


if __name__ == "__main__":
    main()
