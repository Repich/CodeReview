from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List

ROOT_DIR = Path(__file__).resolve().parents[3]
STANDARDS_PATH = ROOT_DIR / "docs" / "system_standards.txt"
TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9_]{3,}")


@dataclass
class NormCard:
    norm_id: str
    body: str
    tokens: set[str]
    checksum: str


class NormRepository:
    def __init__(self, path: Path = STANDARDS_PATH) -> None:
        self.path = path
        self.cards: list[NormCard] = []
        self.version = "unknown"
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        raw_text = self.path.read_text(encoding="utf-8")
        self.version = hashlib.sha1(raw_text.encode("utf-8")).hexdigest()[:12]
        blocks = _split_blocks(raw_text)
        for norm_id, text in blocks:
            checksum = hashlib.sha1(f"{norm_id}:{text}".encode("utf-8")).hexdigest()[:12]
            tokens = set(_tokenize(text))
            if tokens:
                self.cards.append(NormCard(norm_id=norm_id, body=text.strip(), tokens=tokens, checksum=checksum))

    def search(self, keywords: Iterable[str], limit: int = 6) -> list[NormCard]:
        query_tokens = set(_tokenize(" ".join(keywords)))
        if not query_tokens:
            return self.cards[:limit]
        scored = []
        for card in self.cards:
            score = sum(1 for token in query_tokens if token in card.tokens)
            if score > 0:
                scored.append((score, card))
        if not scored:
            return self.cards[:limit]
        scored.sort(key=lambda item: (-item[0], item[1].norm_id))
        return [card for _, card in scored[:limit]]


def _split_blocks(raw_text: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    current_id: str | None = None
    current_lines: list[str] = []
    for line in raw_text.splitlines():
        line = line.rstrip()
        if line.startswith("#std"):
            if current_id and current_lines:
                blocks.append((current_id, "\n".join(current_lines).strip()))
            current_id = line.lstrip("#").strip()
            current_lines = []
            continue
        if current_id is None:
            continue
        current_lines.append(line)
    if current_id and current_lines:
        blocks.append((current_id, "\n".join(current_lines).strip()))
    return blocks


def _tokenize(text: str) -> list[str]:
    tokens = TOKEN_RE.findall(text.lower())
    return [token for token in tokens if len(token) > 2]


@lru_cache(maxsize=1)
def get_norm_repository() -> NormRepository:
    return NormRepository()
