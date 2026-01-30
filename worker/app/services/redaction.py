from __future__ import annotations

from dataclasses import dataclass
import re

REDACTED_TOKEN = "<REDACTED>"
QUERY_STRING_START = re.compile(
    r"(Новый\s+Запрос\s*\(|Запрос\.Текст\s*=|ТекстЗапроса\s*=)",
    re.IGNORECASE,
)


@dataclass
class RedactionStats:
    total_literals: int
    lines_with_redactions: list[int]
    redactions_by_line: dict[int, int]


def _redact_line(
    line: str,
    in_string: bool,
    preserve_string: bool,
    preserve_next_string: bool,
) -> tuple[str, bool, bool, int]:
    out: list[str] = []
    i = 0
    redactions = 0
    while i < len(line):
        ch = line[i]
        nxt = line[i + 1] if i + 1 < len(line) else ""
        if in_string:
            if ch == '"' and nxt == '"':
                if preserve_string:
                    out.append('""')
                i += 2
                continue
            if ch == '"':
                in_string = False
                preserve_string = False
                out.append('"')
                i += 1
                continue
            if preserve_string:
                out.append(ch)
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append('"')
            if preserve_next_string:
                preserve_string = True
                preserve_next_string = False
            else:
                out.append(REDACTED_TOKEN)
                redactions += 1
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out), in_string, preserve_string, redactions


def redact_lines(lines: list[str], start_line: int) -> tuple[list[str], RedactionStats]:
    redacted: list[str] = []
    redactions_by_line: dict[int, int] = {}
    in_string = False
    preserve_string = False
    total = 0
    for idx, line in enumerate(lines):
        preserve_next_string = bool(QUERY_STRING_START.search(line))
        redacted_line, in_string, preserve_string, count = _redact_line(
            line, in_string, preserve_string, preserve_next_string
        )
        redacted.append(redacted_line)
        if count:
            line_no = start_line + idx
            redactions_by_line[line_no] = count
            total += count
    lines_with = sorted(redactions_by_line)
    return redacted, RedactionStats(total, lines_with, redactions_by_line)


def redact_text(text: str, start_line: int = 1) -> tuple[str, RedactionStats]:
    lines = text.splitlines()
    redacted_lines, stats = redact_lines(lines, start_line)
    return "\n".join(redacted_lines), stats
