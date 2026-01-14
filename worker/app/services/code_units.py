from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Iterable, List

from worker.app.models import SourceUnit

PROCEDURE_RE = re.compile(r"^\s*(Процедура|Функция)\s+([A-Za-zА-Яа-я0-9_]+)")
REGION_RE = re.compile(r"^\s*#Область\s+(.+)$", re.IGNORECASE)
TAG_KEYWORDS = {
    "transaction": ("начатьтранзак", "зафиксироватьтранзак", "отменитьтранзак"),
    "query": ("запрос.", "запрос =", "выполнить(", "выполнить();", "выполнить();", "выполнить()"),
    "temp_table": ("поместить", "временнаятаблица", "создатьвременнуютаблицу"),
    "long_operation": ("длительн", "фонова", "начатьпомещени", "помещениенасервер"),
    "privileged": ("привилегирован", "установитьпривилегирован"),
    "external_call": ("httpзапрос", "httpсоединение", "comобъект", "wsсервис"),
}
MAX_UNIT_LINES = 200
OVERLAP_LINES = 20


@dataclass
class CodeUnit:
    unit_id: str
    source_path: str
    unit_name: str
    unit_type: str
    start_line: int
    end_line: int
    text: str
    tags: set[str]
    review_ranges: list[tuple[int, int]] = field(default_factory=list)


def split_source_into_units(source: SourceUnit) -> list[CodeUnit]:
    lines = source.content.splitlines()
    if not lines:
        return []

    boundaries = _find_boundaries(lines)
    units: list[CodeUnit] = []
    for idx, boundary in enumerate(boundaries):
        start = boundary.start_line
        end = boundary.end_line or len(lines)
        text = "\n".join(lines[start - 1 : end])
        units.extend(_build_segments(source.path, boundary.name, boundary.kind, start, end, text))

    if not units:
        text = source.content
        units = _build_segments(source.path, source.name, "module", 1, len(lines), text)

    if source.change_ranges:
        filtered: list[CodeUnit] = []
        for unit in units:
            overlaps = _intersect_ranges(source.change_ranges, unit.start_line, unit.end_line)
            if overlaps:
                unit.review_ranges = overlaps
                filtered.append(unit)
        return filtered

    return units


def _build_segments(
    source_path: str,
    unit_name: str,
    unit_type: str,
    start_line: int,
    end_line: int,
    text: str,
) -> list[CodeUnit]:
    total_lines = end_line - start_line + 1
    if total_lines <= MAX_UNIT_LINES:
        return [
            _create_unit(
                source_path=source_path,
                unit_name=unit_name,
                unit_type=unit_type,
                start_line=start_line,
                end_line=end_line,
                text=text,
            )
        ]

    segments: list[CodeUnit] = []
    current_start = start_line
    counter = 1
    while current_start <= end_line:
        segment_end = min(end_line, current_start + MAX_UNIT_LINES - 1)
        offset_start = current_start - start_line
        offset_end = segment_end - start_line + 1
        segment_text = "\n".join(text.splitlines()[offset_start:offset_end])
        segment_name = f"{unit_name}#part{counter}"
        segments.append(
            _create_unit(
                source_path=source_path,
                unit_name=segment_name,
                unit_type=unit_type,
                start_line=current_start,
                end_line=segment_end,
                text=segment_text,
            )
        )
        if segment_end == end_line:
            break
        current_start = segment_end - OVERLAP_LINES + 1
        counter += 1
    return segments


def _create_unit(
    source_path: str,
    unit_name: str,
    unit_type: str,
    start_line: int,
    end_line: int,
    text: str,
) -> CodeUnit:
    unit_hash = hashlib.sha1(
        f"{source_path}:{unit_name}:{start_line}:{end_line}".encode("utf-8")
    ).hexdigest()[:16]
    cleaned_text = "\n".join(_strip_comments(text.splitlines()))
    tags = _extract_tags(cleaned_text.lower())
    return CodeUnit(
        unit_id=unit_hash,
        source_path=source_path,
        unit_name=unit_name,
        unit_type=unit_type,
        start_line=start_line,
        end_line=end_line,
        text=text,
        tags=tags,
        review_ranges=[],
    )


def _strip_comments(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    in_block_comment = False
    for raw in lines:
        result_chars: list[str] = []
        i = 0
        in_string = False
        while i < len(raw):
            ch = raw[i]
            nxt = raw[i + 1] if i + 1 < len(raw) else ""
            if in_block_comment:
                if ch == "*" and nxt == "/":
                    in_block_comment = False
                    i += 2
                    continue
                i += 1
                continue
            if in_string:
                if ch == '"' and nxt == '"':
                    result_chars.append('"')
                    result_chars.append('"')
                    i += 2
                    continue
                if ch == '"':
                    in_string = False
                    result_chars.append(ch)
                    i += 1
                    continue
                result_chars.append(ch)
                i += 1
                continue
            if ch == "/" and nxt == "/":
                break
            if ch == "/" and nxt == "*":
                in_block_comment = True
                i += 2
                continue
            if ch == '"':
                in_string = True
                result_chars.append(ch)
                i += 1
                continue
            result_chars.append(ch)
            i += 1
        cleaned.append("".join(result_chars))
    return cleaned


def _intersect_ranges(
    ranges: list[tuple[int, int]], start: int, end: int
) -> list[tuple[int, int]]:
    overlaps: list[tuple[int, int]] = []
    for rng_start, rng_end in ranges:
        overlap_start = max(start, rng_start)
        overlap_end = min(end, rng_end)
        if overlap_start <= overlap_end:
            overlaps.append((overlap_start, overlap_end))
    return overlaps


def _extract_tags(lower_text: str) -> set[str]:
    tags: set[str] = set()
    for tag, keywords in TAG_KEYWORDS.items():
        if any(keyword in lower_text for keyword in keywords):
            tags.add(tag)
    return tags


@dataclass
class _Boundary:
    name: str
    kind: str
    start_line: int
    end_line: int | None = None


def _find_boundaries(lines: list[str]) -> list[_Boundary]:
    proc_boundaries: list[_Boundary] = []
    region_boundaries: list[_Boundary] = []
    current_region: str | None = None
    for idx, line in enumerate(lines, start=1):
        procedure_match = PROCEDURE_RE.match(line)
        if procedure_match:
            name = procedure_match.group(2)
            proc_boundaries.append(_Boundary(name=name, kind="procedure", start_line=idx))
            continue
        region_match = REGION_RE.match(line)
        if region_match:
            current_region = region_match.group(1).strip()
            region_boundaries.append(
                _Boundary(name=f"Region: {current_region}", kind="region", start_line=idx)
            )

    if proc_boundaries:
        boundaries = proc_boundaries
    else:
        boundaries = region_boundaries

    for i in range(len(boundaries) - 1):
        boundaries[i].end_line = boundaries[i + 1].start_line - 1
    if boundaries:
        boundaries[-1].end_line = len(lines)
    return boundaries
