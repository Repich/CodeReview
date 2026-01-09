from __future__ import annotations

import abc
from typing import Optional

from worker.app.models import AnalysisTask


class TaskQueue(abc.ABC):
    @abc.abstractmethod
    def fetch(self) -> Optional[AnalysisTask]:
        """Return next task or None if queue is empty."""


class InMemoryQueue(TaskQueue):
    def __init__(self, tasks: list[AnalysisTask] | None = None) -> None:
        self._tasks = tasks or []

    def fetch(self) -> Optional[AnalysisTask]:
        if not self._tasks:
            return None
        return self._tasks.pop(0)
