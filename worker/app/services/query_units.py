from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable

from worker.app.models import SourceUnit


QUERY_ASSIGN_RE = re.compile(r"\b(?:Запрос\.Текст|ТекстЗапроса)\s*=", re.IGNORECASE)
QUERY_NEW_RE = re.compile(r"\bНовый\s+Запрос\s*\(", re.IGNORECASE)
QUERY_KEYWORD_RE = re.compile(r"\bВЫБРАТЬ\b", re.IGNORECASE)
PIPE_PREFIX_RE = re.compile(r"^\s*\|\s?")


@dataclass
class QueryUnit:
    unit_id: str
    source_path: str
    unit_name: str
    start_line: int
    end_line: int
    text: str
    line_map: list[tuple[int, str]]


def extract_query_units(source: SourceUnit) -> list[QueryUnit]:
    lines = source.content.splitlines()
    if not lines:
        return []

    units: list[QueryUnit] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        match = QUERY_ASSIGN_RE.search(line) or QUERY_NEW_RE.search(line)
        if not match:
            idx += 1
            continue
        _, line_map, end_idx = _collect_string_literals(lines, idx, match.end())
        if not line_map:
            idx = end_idx + 1
            continue
        normalized_map = [(line_no, _normalize_line(text)) for line_no, text in line_map]
        combined_text = "\n".join(text for _, text in normalized_map)
        if not QUERY_KEYWORD_RE.search(combined_text):
            idx = end_idx + 1
            continue
        if source.change_ranges and not _line_map_overlaps(normalized_map, source.change_ranges):
            idx = end_idx + 1
            continue
        unit = _build_query_unit(source.path, len(units) + 1, normalized_map, combined_text)
        units.append(unit)
        idx = end_idx + 1
    return units


def _collect_string_literals(
    lines: list[str], start_idx: int, start_col: int
) -> tuple[list[str], list[tuple[int, str]], int]:
    literals: list[str] = []
    line_map: list[tuple[int, str]] = []
    i = start_idx
    j = start_col
    paren_depth = 0
    while i < len(lines):
        line = lines[i]
        while j < len(line):
            ch = line[j]
            if ch == '"':
                literal_lines, end_line, end_col = _consume_string_literal(lines, i, j)
                if literal_lines:
                    literals.append("\n".join(text for _, text in literal_lines))
                    line_map.extend(literal_lines)
                i = end_line
                j = end_col + 1
                line = lines[i]
                continue
            if ch == "(":
                paren_depth += 1
            elif ch == ")":
                paren_depth = max(0, paren_depth - 1)
            elif ch == ";" and paren_depth == 0:
                return literals, line_map, i
            j += 1
        i += 1
        j = 0
    return literals, line_map, len(lines) - 1


def _consume_string_literal(
    lines: list[str], line_idx: int, col_idx: int
) -> tuple[list[tuple[int, str]], int, int]:
    collected: list[tuple[int, str]] = []
    buffer: list[str] = []
    i = line_idx
    j = col_idx + 1
    while i < len(lines):
        line = lines[i]
        while j < len(line):
            ch = line[j]
            if ch == '"':
                if j + 1 < len(line) and line[j + 1] == '"':
                    buffer.append('"')
                    j += 2
                    continue
                collected.append((i + 1, "".join(buffer)))
                return collected, i, j
            buffer.append(ch)
            j += 1
        collected.append((i + 1, "".join(buffer)))
        buffer = []
        i += 1
        j = 0
    if buffer and lines:
        line_no = min(i, len(lines) - 1) + 1
        collected.append((line_no, "".join(buffer)))
    return collected, max(line_idx, i - 1), 0


def _normalize_line(text: str) -> str:
    return PIPE_PREFIX_RE.sub("", text.rstrip())


def _line_map_overlaps(
    line_map: Iterable[tuple[int, str]], ranges: list[tuple[int, int]]
) -> bool:
    if not ranges:
        return True
    for line_no, _ in line_map:
        for start, end in ranges:
            if start <= line_no <= end:
                return True
    return False


def _build_query_unit(
    source_path: str,
    index: int,
    line_map: list[tuple[int, str]],
    combined_text: str,
) -> QueryUnit:
    start_line = min(line_no for line_no, _ in line_map)
    end_line = max(line_no for line_no, _ in line_map)
    unit_hash = hashlib.sha1(
        f"{source_path}:query:{start_line}:{end_line}:{index}".encode("utf-8")
    ).hexdigest()[:16]
    return QueryUnit(
        unit_id=unit_hash,
        source_path=source_path,
        unit_name=f"Query#{index}",
        start_line=start_line,
        end_line=end_line,
        text=combined_text,
        line_map=line_map,
    )
