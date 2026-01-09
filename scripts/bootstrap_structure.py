#!/usr/bin/env python3
"""Bootstrap repository directories and placeholder files for the CodeReview project."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def ensure_dir(path: Path) -> None:
    """Create directory if it does not exist."""
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)


@dataclass
class FileTemplate:
    relative_path: str
    content: str

    @property
    def absolute_path(self) -> Path:
        return PROJECT_ROOT / self.relative_path

    def ensure(self) -> None:
        file_path = self.absolute_path
        ensure_dir(file_path.parent)
        if file_path.exists():
            return
        file_path.write_text(dedent(self.content).lstrip("\n"), encoding="utf-8")


DIRECTORIES = [
    "backend/app/api",
    "backend/app/core",
    "backend/app/db",
    "backend/app/models",
    "backend/app/schemas",
    "backend/tests",
    "worker/app/detectors",
    "worker/app/queue",
    "worker/tests",
    "common",
    "ui",
    "infrastructure/docker",
    "docs",
    "scripts",
]

FILE_TEMPLATES = [
    FileTemplate(
        "README.md",
        '''\
        # CodeReview 1C

        Репозиторий системы анализа и код-ревью для 1С: Предприятие.
        Подробное описание структуры будет заполняться по мере разработки.
        '''
    ),
    FileTemplate(
        "Makefile",
        '''\
        .PHONY: bootstrap

        bootstrap:
        \tpython3 scripts/bootstrap_structure.py
        '''
    ),
    FileTemplate(
        "backend/app/__init__.py",
        '# Backend application package\n'
    ),
    FileTemplate(
        "backend/app/main.py",
        '''\
        def create_app():
            """Placeholder for FastAPI app factory."""
            raise NotImplementedError


        if __name__ == "__main__":
            create_app()
        '''
    ),
    FileTemplate(
        "backend/tests/__init__.py",
        '# Backend tests package\n'
    ),
    FileTemplate(
        "worker/app/__init__.py",
        '# Worker application package\n'
    ),
    FileTemplate(
        "worker/app/main.py",
        '''\
        def main():
            """Placeholder for worker entrypoint."""
            raise NotImplementedError


        if __name__ == "__main__":
            main()
        '''
    ),
    FileTemplate(
        "worker/tests/__init__.py",
        '# Worker tests package\n'
    ),
    FileTemplate(
        "common/__init__.py",
        '# Common utilities package\n'
    ),
    FileTemplate(
        "infrastructure/docker/README.md",
        '''\
        # Docker artifacts

        Здесь будут храниться Dockerfile и вспомогательные скрипты.
        '''
    ),
    FileTemplate(
        "docs/README.md",
        'Документация проекта.\n'
    ),
]


def main() -> None:
    for rel_dir in DIRECTORIES:
        ensure_dir(PROJECT_ROOT / rel_dir)
    for template in FILE_TEMPLATES:
        template.ensure()
    print("Repository structure ensured.")


if __name__ == "__main__":
    main()
