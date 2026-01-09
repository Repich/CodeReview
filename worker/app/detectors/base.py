from __future__ import annotations

import abc
import re
from dataclasses import dataclass
from typing import Iterable

from worker.app.models import DetectorFinding, SourceUnit


@dataclass
class DetectorContext:
    source: SourceUnit


class BaseDetector(abc.ABC):
    norm_id: str
    detector_id: str
    severity: str

    def __init__(self) -> None:
        if not getattr(self, "norm_id", None):
            raise ValueError("norm_id must be set")
        if not getattr(self, "detector_id", None):
            raise ValueError("detector_id must be set")
        if not getattr(self, "severity", None):
            raise ValueError("severity must be set")

    @abc.abstractmethod
    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        ...

    def create_finding(
        self,
        ctx: DetectorContext,
        message: str,
        recommendation: str,
        line: int,
        extra: dict | None = None,
    ) -> DetectorFinding:
        snippet = self.build_snippet(ctx.source.content, line)
        return DetectorFinding(
            norm_id=self.norm_id,
            detector_id=self.detector_id,
            severity=self.severity,
            message=message,
            recommendation=recommendation,
            file_path=ctx.source.path,
            line=line,
            context=extra or {"module_type": ctx.source.module_type},
            snippet=snippet,
        )

    @staticmethod
    def build_snippet(content: str, line: int, window: int = 2) -> str:
        lines = content.splitlines()
        start = max(line - 1 - window, 0)
        end = min(line - 1 + window, len(lines) - 1)
        snippet_lines = []
        for idx in range(start, end + 1):
            snippet_lines.append(f"{idx + 1:>4}: {lines[idx]}")
        return "\n".join(snippet_lines)

    @staticmethod
    def iter_lines(text: str) -> Iterable[tuple[int, str]]:
        for idx, line in enumerate(text.splitlines(), start=1):
            yield idx, line
