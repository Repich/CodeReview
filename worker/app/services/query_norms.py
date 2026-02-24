from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from worker.app.services.general_norms import get_general_norm_repository
from worker.app.services.norms_repo import NormCard

ROOT_DIR = Path(__file__).resolve().parents[3]
NORMS_PATH = ROOT_DIR / "critical_norms.yaml"

QUERY_NORM_IDS = [
    "CRIT_NEW_10",
    "CRIT_NEW_23",
    "CRIT_NEW_28",
    "CRIT_NEW_29",
    "CRIT_NEW_30",
    "CRIT_QRY_01",
    "CRIT_QRY_02",
    "CRIT_QRY_03",
    "CRIT_QRY_04",
    "CRIT_QRY_05",
    "CRIT_QRY_06",
    "CRIT_QRY_07",
    "CRIT_QRY_08",
    "CRIT_QRY_09",
    "CRIT_QRY_10",
    "CRIT_QRY_11",
    "CRIT_QRY_12",
    "CRIT_QRY_13",
    "CRIT_QRY_14",
    "CRIT_QRY_15",
    "CRIT_QRY_16",
    "CRIT_QRY_17",
    "CRIT_QRY_18",
]


@dataclass
class QueryNormRepository:
    path: Path = NORMS_PATH
    norm_ids: list[str] | None = None
    cards: list[NormCard] | None = None
    entries: dict[str, dict] | None = None
    version: str = "unknown"
    include_general_query_norms: bool = False

    def __post_init__(self) -> None:
        if self.norm_ids is None:
            self.norm_ids = list(QUERY_NORM_IDS)
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
        data = yaml.safe_load(raw_text) or {}
        entries = data.get("norms", [])
        norm_map = {entry.get("norm_id"): entry for entry in entries if entry.get("norm_id")}
        for norm_id in self.norm_ids:
            entry = norm_map.get(norm_id)
            if not entry:
                continue
            self._append_entry(norm_id, entry)
        if self.include_general_query_norms:
            general_repo = get_general_norm_repository()
            added_ids: list[str] = []
            general_cards = {card.norm_id: card for card in general_repo.cards}
            for norm_id, entry in general_repo.entries.items():
                if norm_id in self.entries:
                    continue
                if not _is_query_related(entry):
                    continue
                self.entries[norm_id] = entry
                self.norm_ids.append(norm_id)
                card = general_cards.get(norm_id)
                if card is None:
                    self.cards.append(_build_card(norm_id, entry))
                else:
                    self.cards.append(card)
                added_ids.append(norm_id)
            version_seed += (
                f"|general:{general_repo.version}|"
                f"include_general_query_norms=1|"
                f"added:{','.join(sorted(added_ids))}"
            )
        self.version = hashlib.sha1(version_seed.encode("utf-8")).hexdigest()[:12]

    def _append_entry(self, norm_id: str, entry: dict) -> None:
        self.entries[norm_id] = entry
        self.cards.append(_build_card(norm_id, entry))


def _build_card(norm_id: str, entry: dict) -> NormCard:
    body = _format_norm_body(entry)
    checksum = hashlib.sha1(f"{norm_id}:{body}".encode("utf-8")).hexdigest()[:12]
    tokens = set(_tokenize(body))
    return NormCard(norm_id=norm_id, body=body, tokens=tokens, checksum=checksum)


def _is_query_related(entry: dict) -> bool:
    tags = entry.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    tag_set = {str(tag).strip().lower() for tag in tags if str(tag).strip()}
    if "queries" in tag_set:
        return True

    section = str(entry.get("section") or "").lower()
    category = str(entry.get("category") or "").lower()
    title = str(entry.get("title") or "").lower()

    return (
        "query" in category
        or "запрос" in section
        or "запрос" in title
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


@lru_cache(maxsize=2)
def get_query_norm_repository(include_general_query_norms: bool = False) -> QueryNormRepository:
    return QueryNormRepository(include_general_query_norms=include_general_query_norms)
