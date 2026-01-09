from __future__ import annotations

from typing import Iterable, Type

from worker.app.detectors.base import BaseDetector


class DetectorRegistry:
    def __init__(self) -> None:
        self._detectors: list[Type[BaseDetector]] = []

    def register(self, detector_cls: Type[BaseDetector]) -> None:
        self._detectors.append(detector_cls)

    def all(self) -> Iterable[BaseDetector]:
        for cls in self._detectors:
            yield cls()


default_registry = DetectorRegistry()


def register(detector_cls: Type[BaseDetector]) -> Type[BaseDetector]:
    default_registry.register(detector_cls)
    return detector_cls
