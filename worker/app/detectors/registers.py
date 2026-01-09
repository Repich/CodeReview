from __future__ import annotations

from typing import Iterable

from worker.app.detectors.base import BaseDetector, DetectorContext
from worker.app.detectors.registry import register
from worker.app.models import DetectorFinding


def _is_loop_start(line: str) -> bool:
    stripped = line.strip().lower()
    return ("для" in stripped or "пока" in stripped) and "цикл" in stripped


def _is_loop_end(line: str) -> bool:
    return line.strip().lower().startswith("конеццикла")


@register
class RegisterLoopRecordsetCreationDetector(BaseDetector):
    norm_id = "MULTI_WRITE_REG_01"
    detector_id = "detector.register_loop_creation"
    severity = "major"

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        loop_depth = 0
        for line_no, line in self.iter_lines(ctx.source.content):
            if _is_loop_start(line):
                loop_depth += 1
            elif _is_loop_end(line) and loop_depth > 0:
                loop_depth -= 1
            if loop_depth <= 0:
                continue
            if "СоздатьНаборЗаписей" in line:
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Создание набора записей регистра внутри цикла",
                        recommendation="Готовьте набор записей вне цикла и записывайте батчом вместо вызовов в каждой итерации.",
                        line=line_no,
                        extra={"line": line.strip()},
                    )
                )
        return findings


@register
class RegisterLoopRecordsetWriteDetector(BaseDetector):
    norm_id = "MULTI_WRITE_REG_03"
    detector_id = "detector.register_loop_write"
    severity = "major"

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        loop_depth = 0
        for line_no, line in self.iter_lines(ctx.source.content):
            if _is_loop_start(line):
                loop_depth += 1
            elif _is_loop_end(line) and loop_depth > 0:
                loop_depth -= 1
            if loop_depth <= 0:
                continue
            lowered = line.lower()
            if ".записать" in lowered and ("регистры" in lowered or "наборзаписей" in lowered):
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Запись набора записей регистра внутри цикла",
                        recommendation="Формируйте изменения регистра одним набором записей вне цикла и выполняйте запись единоразово.",
                        line=line_no,
                        extra={"line": line.strip()},
                    )
                )
        return findings


def _extract_owner_from_path(path: str) -> str | None:
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        return None
    if parts[0] in {
        "Catalogs",
        "Documents",
        "AccumulationRegisters",
        "InformationRegisters",
        "AccountingRegisters",
        "CalculationRegisters",
        "ChartsOfAccounts",
        "ChartsOfCharacteristicTypes",
        "ChartsOfCalculationTypes",
        "Enums",
    }:
        return parts[1]
    return None


@register
class ChildNameMatchesOwnerDetector(BaseDetector):
    norm_id = "NAME_NO_OWNER_DUPLICATE"
    detector_id = "detector.child_name_dup_owner"
    severity = "medium"

    prefixes = ("Реквизиты.", "Измерения.", "Ресурсы.", "Показатели.", "Измерение.", "ТабличныеЧасти.")

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        owner = _extract_owner_from_path(ctx.source.path)
        if not owner:
            return []
        owner_lower = owner.lower()
        findings: list[DetectorFinding] = []
        for line_no, line in self.iter_lines(ctx.source.content):
            lowered = line.lower()
            for prefix in self.prefixes:
                prefix_lower = prefix.lower()
                if prefix_lower + owner_lower in lowered:
                    findings.append(
                        self.create_finding(
                            ctx,
                            message="Имя подчиненного объекта совпадает с именем владельца",
                            recommendation="Переименуйте реквизит/измерение, чтобы оно отличалось от имени объекта.",
                            line=line_no,
                            extra={"owner": owner, "line": line.strip()},
                        )
                    )
                    break
        return findings
