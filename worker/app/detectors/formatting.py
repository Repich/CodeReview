from __future__ import annotations

import re
from typing import Iterable

from worker.app.detectors.base import BaseDetector, DetectorContext
from worker.app.detectors.registry import register
from worker.app.models import DetectorFinding


REGION_START = ("#область", "#region")
REGION_END = ("#конецобласти", "#endregion")
PROC_START_RE = re.compile(r"^\s*(Процедура|Функция)\b", re.IGNORECASE)


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


@register
class MaxFunctionParamsDetector(BaseDetector):
    norm_id = "FUNC_MAX_PARAMS_05"
    detector_id = "detector.max_function_params"
    severity = "minor"

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        lines = ctx.source.content.splitlines()
        in_block_comment = False
        idx = 0
        while idx < len(lines):
            stripped, in_block_comment = self._strip_comments(lines[idx], in_block_comment)
            if not PROC_START_RE.match(stripped):
                idx += 1
                continue
            signature, end_idx, in_block_comment = self._collect_signature(
                lines, idx, in_block_comment, stripped
            )
            param_count = self._count_params(signature)
            if param_count > 5:
                findings.append(
                    self.create_finding(
                        ctx,
                        message=f"Слишком много параметров в сигнатуре: {param_count}",
                        recommendation="Сократите количество параметров до 5, сгруппируйте их в структуру или объект.",
                        line=idx + 1,
                        extra={"signature": signature.strip()},
                    )
                )
            idx = end_idx + 1
        return findings

    def _collect_signature(
        self,
        lines: list[str],
        start_idx: int,
        in_block_comment: bool,
        first_line: str,
    ) -> tuple[str, int, bool]:
        parts = [first_line.strip()]
        idx = start_idx
        if ")" in first_line:
            return " ".join(parts), idx, in_block_comment
        while idx + 1 < len(lines):
            idx += 1
            stripped, in_block_comment = self._strip_comments(lines[idx], in_block_comment)
            parts.append(stripped.strip())
            if ")" in stripped:
                break
        return " ".join(parts), idx, in_block_comment

    def _count_params(self, signature: str) -> int:
        start = signature.find("(")
        if start == -1:
            return 0
        count = 0
        depth = 0
        in_string = False
        token_has_content = False
        i = start + 1
        while i < len(signature):
            ch = signature[i]
            nxt = signature[i + 1] if i + 1 < len(signature) else ""
            if in_string:
                if ch == '"' and nxt == '"':
                    i += 2
                    continue
                if ch == '"':
                    in_string = False
                    i += 1
                    continue
                i += 1
                continue
            if ch == '"':
                in_string = True
                i += 1
                continue
            if ch == "(":
                depth += 1
                token_has_content = True
                i += 1
                continue
            if ch == ")":
                if depth == 0:
                    if token_has_content:
                        count += 1
                    break
                depth -= 1
                i += 1
                continue
            if ch == "," and depth == 0:
                if token_has_content:
                    count += 1
                token_has_content = False
                i += 1
                continue
            if not ch.isspace():
                token_has_content = True
            i += 1
        return count
