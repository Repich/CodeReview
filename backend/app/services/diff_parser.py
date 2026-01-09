from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

DIFF_LINE_RE = re.compile(
    r"^\s*(?P<m1>[<>_])?\s*(?P<m2>[<>_])?\s*(?P<old>\d+|_)?\s*(?P<new>\d+|_)?\s*(?P<code>.*)$"
)


@dataclass
class ParsedLine:
    include: bool
    changed: bool
    text: str


def parse_crucible_diff(text: str) -> tuple[str, list[tuple[int, int]]]:
    """
    Parse Crucible-style side-by-side diff and return reconstructed module text
    plus list of changed ranges (line numbers in the new version).
    If content does not look like diff, original text is returned with empty ranges.
    """
    if not text:
        return "", []

    lines = text.splitlines()
    parsed: list[ParsedLine] = []
    diff_detected = False

    for line in lines:
        match = DIFF_LINE_RE.match(line)
        if not match:
            return text, []

        markers = {m for m in (match.group("m1"), match.group("m2")) if m}
        old_token = match.group("old")
        new_token = match.group("new")
        code = match.group("code")

        if not old_token and not new_token:
            return text, []

        diff_detected = diff_detected or bool(markers) or bool(old_token and new_token)
        include = True
        is_changed = False

        new_number_present = new_token and new_token != "_"
        old_number_present = old_token and old_token != "_"

        if not new_number_present and not old_number_present:
            return text, []

        addition_marker = ">" in markers and "_" not in markers
        deletion_marker = "<" in markers and "_" not in markers and not addition_marker

        if not new_number_present and not addition_marker:
            include = False

        if include and (addition_marker or (("<" in markers or ">" in markers) and "_" not in markers)):
            is_changed = True

        parsed.append(ParsedLine(include=include, changed=is_changed, text=code))

    if not diff_detected:
        return text, []

    rebuilt_lines: list[str] = []
    ranges: list[tuple[int, int]] = []
    current_range: list[int] | None = None

    for item in parsed:
        if not item.include:
            continue
        rebuilt_lines.append(item.text)
        if item.changed:
            line_no = len(rebuilt_lines)
            if current_range:
                current_range[1] = line_no
            else:
                current_range = [line_no, line_no]
        else:
            if current_range:
                ranges.append((current_range[0], current_range[1]))
                current_range = None

    if current_range:
        ranges.append((current_range[0], current_range[1]))

    return "\n".join(rebuilt_lines), ranges


def merge_change_ranges(items: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    sorted_items = sorted(items)
    merged: list[tuple[int, int]] = []
    for start, end in sorted_items:
        if not merged:
            merged.append((start, end))
            continue
        last_start, last_end = merged[-1]
        if start <= last_end + 1:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged
