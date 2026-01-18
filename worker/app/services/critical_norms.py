from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from worker.app.services.norms_repo import NormCard

ROOT_DIR = Path(__file__).resolve().parents[3]
NORMS_PATH = ROOT_DIR / "critical_norms.yaml"

CODE_NORM_IDS = [
    "CRIT_NEW_01",
    "CRIT_NEW_02",
    "CRIT_NEW_03",
    "CRIT_NEW_04",
    "CRIT_NEW_05",
    "CRIT_NEW_06",
    "CRIT_NEW_07",
    "CRIT_NEW_08",
    "CRIT_NEW_09",
    "CRIT_NEW_11",
    "CRIT_NEW_12",
    "CRIT_NEW_13",
    "CRIT_NEW_14",
    "CRIT_NEW_15",
    "CRIT_NEW_16",
    "CRIT_NEW_17",
    "CRIT_NEW_18",
    "CRIT_NEW_19",
    "CRIT_NEW_20",
    "CRIT_NEW_21",
    "CRIT_NEW_22",
    "CRIT_NEW_24",
    "CRIT_NEW_25",
    "CRIT_NEW_26",
    "CRIT_NEW_27",
    "SECURITY_COM_AUTOMATION_DISABLE_MACROS",
    "SECURITY_PASSWORD_STORAGE_NO_PLAINTEXT",
    "SECURITY_TLS_VERIFY_SERVER_AUTH",
]


@dataclass
class CriticalNormRepository:
    path: Path = NORMS_PATH
    norm_ids: list[str] | None = None
    cards: list[NormCard] | None = None
    entries: dict[str, dict] | None = None
    version: str = "unknown"

    def __post_init__(self) -> None:
        if self.norm_ids is None:
            self.norm_ids = list(CODE_NORM_IDS)
        if self.cards is None:
            self.cards = []
        if self.entries is None:
            self.entries = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        raw_text = self.path.read_text(encoding="utf-8")
        version_seed = raw_text + "|" + ",".join(self.norm_ids)
        self.version = hashlib.sha1(version_seed.encode("utf-8")).hexdigest()[:12]
        data = yaml.safe_load(raw_text) or {}
        entries = data.get("norms", [])
        norm_map = {entry.get("norm_id"): entry for entry in entries if entry.get("norm_id")}
        for norm_id in self.norm_ids:
            entry = norm_map.get(norm_id)
            if not entry:
                continue
            self.entries[norm_id] = entry
            body = _format_norm_body(entry)
            checksum = hashlib.sha1(f"{norm_id}:{body}".encode("utf-8")).hexdigest()[:12]
            tokens = set(_tokenize(body))
            self.cards.append(
                NormCard(norm_id=norm_id, body=body, tokens=tokens, checksum=checksum)
            )


def _format_norm_body(entry: dict) -> str:
    section = entry.get("section") or "—"
    category = entry.get("category") or "—"
    title = entry.get("title") or "—"
    norm_text = entry.get("norm_text") or "—"
    rationale = entry.get("rationale") or "—"
    detection_hint = entry.get("detection_hint") or "—"
    scope = entry.get("scope") or "—"
    exceptions = entry.get("exceptions") or "—"
    priority = entry.get("priority") or "—"
    source_ref = entry.get("source_reference") or entry.get("source_standard") or "—"
    return (
        f"Раздел: {section}\n"
        f"Категория: {category}\n"
        f"Название: {title}\n"
        f"Текст нормы: {norm_text}\n"
        f"Обоснование: {rationale}\n"
        f"Подсказка детекта: {detection_hint}\n"
        f"Область: {scope}\n"
        f"Исключения: {exceptions}\n"
        f"Приоритет: {priority}\n"
        f"Источник: {source_ref}"
    ).strip()


TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9_]{3,}")


def _tokenize(text: str) -> list[str]:
    tokens = TOKEN_RE.findall(text.lower())
    return [token for token in tokens if len(token) > 2]


@lru_cache(maxsize=1)
def get_critical_norm_repository() -> CriticalNormRepository:
    return CriticalNormRepository()
