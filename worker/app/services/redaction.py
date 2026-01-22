from __future__ import annotations

from dataclasses import dataclass

REDACTED_TOKEN = "<REDACTED>"


@dataclass
class RedactionStats:
    total_literals: int
    lines_with_redactions: list[int]
    redactions_by_line: dict[int, int]


def _redact_line(line: str, in_string: bool) -> tuple[str, bool, int]:
    out: list[str] = []
    i = 0
    redactions = 0
    while i < len(line):
        ch = line[i]
        nxt = line[i + 1] if i + 1 < len(line) else ""
        if in_string:
            if ch == '"' and nxt == '"':
                i += 2
                continue
            if ch == '"':
                in_string = False
                out.append('"')
                i += 1
                continue
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append('"')
            out.append(REDACTED_TOKEN)
            redactions += 1
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out), in_string, redactions


def redact_lines(lines: list[str], start_line: int) -> tuple[list[str], RedactionStats]:
    redacted: list[str] = []
    redactions_by_line: dict[int, int] = {}
    in_string = False
    total = 0
    for idx, line in enumerate(lines):
        redacted_line, in_string, count = _redact_line(line, in_string)
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
