from __future__ import annotations

import re
from typing import Iterable

from worker.app.detectors.base import BaseDetector, DetectorContext
from worker.app.detectors.registry import register
from worker.app.models import DetectorFinding


REGION_START = ("#область", "#region")
REGION_END = ("#конецобласти", "#endregion")


@register
class EmptyRegionDetector(BaseDetector):
    norm_id = "MODULE_STRUCTURE_08"
    detector_id = "detector.empty_regions"
    severity = "major"

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        content_lines = ctx.source.content.splitlines()
        in_block_comment = False
        stack: list[dict[str, int | bool]] = []
        findings: list[DetectorFinding] = []

        for idx, line in enumerate(content_lines, start=1):
            stripped = line.strip()
            lowered = stripped.lower()
            if lowered.startswith(REGION_START):
                stack.append({"start_line": idx, "has_content": False})
                continue
            if lowered.startswith(REGION_END):
                if stack:
                    region = stack.pop()
                    if not region["has_content"]:
                        findings.append(
                            self.create_finding(
                                ctx,
                                message="Пустая область модуля",
                                recommendation="Удалите пустую область или добавьте в нее содержимое.",
                                line=int(region["start_line"]),
                                extra={"line": stripped},
                            )
                        )
                continue

            if not stack:
                continue

            stripped_comment, in_block_comment = self._strip_comments(line, in_block_comment)
            if stripped_comment.strip():
                for region in stack:
                    region["has_content"] = True

        return findings


@register
class IndentSpacesDetector(BaseDetector):
    norm_id = "TEXT_INDENT_TABS"
    detector_id = "detector.indent_spaces"
    severity = "minor"

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        for line_no, line in enumerate(ctx.source.content.splitlines(), start=1):
            if not line.strip():
                continue
            match = re.match(r"[ \t]+", line)
            if not match:
                continue
            if " " in match.group(0):
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Отступы сделаны пробелами вместо табуляции",
                        recommendation="Используйте табуляцию для синтаксического отступа.",
                        line=line_no,
                        extra={"line": line.strip()},
                    )
                )
        return findings


@register
class TrailingTabsDetector(BaseDetector):
    norm_id = "TEXT_TRAILING_TABS"
    detector_id = "detector.trailing_tabs"
    severity = "minor"

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        for line_no, line in enumerate(ctx.source.content.splitlines(), start=1):
            raw_line = line.rstrip("\r\n")
            if not raw_line.strip():
                continue
            match = re.search(r"[ \t]+$", raw_line)
            if not match:
                continue
            if "\t" in match.group(0):
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Лишние табуляции в конце строки",
                        recommendation="Удалите табуляции и пробелы после последнего символа строки.",
                        line=line_no,
                        extra={"line": raw_line.rstrip()},
                    )
                )
        return findings


@register
class MultipleBlankLinesDetector(BaseDetector):
    norm_id = "TEXT_EXTRA_BLANK_LINES"
    detector_id = "detector.multiple_blank_lines"
    severity = "minor"

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        blank_streak = 0
        for line_no, line in enumerate(ctx.source.content.splitlines(), start=1):
            if line.strip():
                blank_streak = 0
                continue
            blank_streak += 1
            if blank_streak > 1:
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Лишняя пустая строка",
                        recommendation="Оставляйте не более одной пустой строки подряд.",
                        line=line_no,
                        extra={"line": ""},
                    )
                )
        return findings
