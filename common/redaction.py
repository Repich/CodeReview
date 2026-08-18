from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


REDACTED_TOKEN = "<REDACTED>"
REDACTED_COMMENT = "<REDACTED_COMMENT>"

QUERY_STRING_START = re.compile(
    r"(Новый\s+Запрос\s*\(|Запрос\.Текст\s*=|ТекстЗапроса\s*=)",
    re.IGNORECASE,
)

_URI_CREDENTIALS = re.compile(
    r"(?P<scheme>[a-z][a-z0-9+.-]*://)[^/@\s:]+:[^/@\s]+@",
    re.IGNORECASE,
)
_CREDENTIAL_ASSIGNMENT = re.compile(
    r"(?P<prefix>\b(?:password|passwd|pwd|pass|парол(?:ь|я)|token|secret|"
    r"api[ _-]?key|authorization|login|username|user[ _-]?id|uid|логин)\b\s*[:=]\s*)"
    r"(?P<value>\"[^\"]*\"|'[^']*'|[^;\s,]+)",
    re.IGNORECASE,
)
_BEARER_TOKEN = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)
_KNOWN_TOKEN = re.compile(
    r"(?:AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|gh[pousr]_[0-9A-Za-z]{30,}|"
    r"sk-[0-9A-Za-z_-]{20,}|xox[baprs]-[0-9A-Za-z-]{20,}|"
    r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})"
)
_SENSITIVE_KEYS = re.compile(
    r"(?:password|passwd|pwd|pass|парол|token|secret|api[ _-]?key|authorization|credential)",
    re.IGNORECASE,
)


@dataclass
class RedactionStats:
    total_literals: int
    lines_with_redactions: list[int]
    redactions_by_line: dict[int, int]


def redact_sensitive_text(text: str) -> str:
    """Mask high-confidence credentials while preserving surrounding syntax."""

    value = _URI_CREDENTIALS.sub(r"\g<scheme><REDACTED_CREDENTIALS>@", text)
    value = _CREDENTIAL_ASSIGNMENT.sub(r"\g<prefix><REDACTED>", value)
    value = _BEARER_TOKEN.sub("Bearer <REDACTED>", value)
    return _KNOWN_TOKEN.sub(REDACTED_TOKEN, value)


def redact_structure(value: Any) -> Any:
    """Recursively remove secrets from diagnostic dictionaries and lists."""

    if isinstance(value, dict):
        return {
            key: REDACTED_TOKEN if _SENSITIVE_KEYS.search(str(key)) else redact_structure(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_structure(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_structure(item) for item in value)
    if isinstance(value, str):
        return redact_sensitive_text(value)
    return value


def _redact_line(
    line: str,
    in_string: bool,
    preserve_string: bool,
    preserve_next_string: bool,
) -> tuple[str, bool, bool, bool, int]:
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
    return redact_sensitive_text("".join(out)), in_string, preserve_string, preserve_next_string, redactions


def redact_lines(lines: list[str], start_line: int) -> tuple[list[str], RedactionStats]:
    redacted: list[str] = []
    redactions_by_line: dict[int, int] = {}
    in_string = False
    preserve_string = False
    preserve_next_string = False
    total = 0
    for idx, line in enumerate(lines):
        preserve_next_string = preserve_next_string or bool(QUERY_STRING_START.search(line))
        redacted_line, in_string, preserve_string, preserve_next_string, count = _redact_line(
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


def _redact_comments(lines: list[str]) -> list[str]:
    redacted: list[str] = []
    in_block_comment = False
    in_string = False

    for line in lines:
        out: list[str] = []
        i = 0
        while i < len(line):
            ch = line[i]
            nxt = line[i + 1] if i + 1 < len(line) else ""
            if in_block_comment:
                end_idx = line.find("*/", i)
                if end_idx == -1:
                    i = len(line)
                    continue
                out.append("*/")
                in_block_comment = False
                i = end_idx + 2
                continue
            if in_string:
                out.append(ch)
                if ch == '"' and nxt == '"':
                    out.append(nxt)
                    i += 2
                    continue
                if ch == '"':
                    in_string = False
                i += 1
                continue
            if ch == "/" and nxt == "/":
                out.append("//")
                out.append(REDACTED_COMMENT)
                i = len(line)
                continue
            if ch == "/" and nxt == "*":
                out.append("/*")
                out.append(REDACTED_COMMENT)
                end_idx = line.find("*/", i + 2)
                if end_idx == -1:
                    in_block_comment = True
                    i = len(line)
                    continue
                out.append("*/")
                i = end_idx + 2
                continue
            if ch == '"':
                in_string = True
            out.append(ch)
            i += 1
        redacted.append("".join(out))
    return redacted


def redact_bsl_source_text(text: str, start_line: int = 1) -> tuple[str, RedactionStats]:
    """Redact BSL comments, literals and credential patterns in query text."""

    comment_redacted = _redact_comments(text.splitlines())
    redacted, stats = redact_lines(comment_redacted, start_line)
    return "\n".join(redacted), stats
