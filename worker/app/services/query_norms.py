from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from worker.app.services.norms_repo import NormCard

ROOT_DIR = Path(__file__).resolve().parents[3]
NORMS_PATH = ROOT_DIR / "norms.yaml"

QUERY_NORM_IDS = [
    "QUERY_NO_FULL_OUTER_JOIN_POSTGRES",
    "SEC_NO_DYNAMIC_CODE",
    "DYN_LIST_QUERY_01",
    "DYN_LIST_QUERY_02",
    "DYN_LIST_QUERY_03",
    "DYN_LIST_QUERY_04",
    "DYN_LIST_QUERY_05",
    "DYN_LIST_QUERY_06",
    "DYN_LIST_QUERY_07",
    "DYN_LIST_QUERY_08",
    "DYN_LIST_QUERY_09",
    "NAME_NO_QUERY_TABLE_WORDS",
    "TEMP_TABLES_01",
    "TEMP_TABLES_02",
    "TEMP_TABLES_03",
    "TEMP_TABLES_04",
    "TEMP_TABLES_05",
    "TEMP_TABLES_06",
    "TEMP_TABLES_07",
    "TEMP_TABLES_08",
    "TEMP_TABLES_09",
    "TEMP_TABLES_10",
    "STRING_FIELDS_08",
    "PERF_SERVER_CALLS_04",
    "INDEX_MISMATCH_01",
    "INDEX_MISMATCH_02",
    "INDEX_MISMATCH_03",
    "INDEX_MISMATCH_04",
    "INDEX_MISMATCH_05",
    "VIRTUAL_TABLE_01",
    "VIRTUAL_TABLE_02",
    "VIRTUAL_TABLE_03",
    "QUERY_GENERAL_01",
    "QUERY_GENERAL_02",
    "QUERY_GENERAL_03",
    "QUERY_GENERAL_04",
    "QUERY_HEAVY_CONSTRUCTS_01",
    "QUERY_RESULT_REPRESENTATION_01",
    "FULL_JOIN_LIMIT_01",
    "FULL_JOIN_LIMIT_02",
    "SUBQUERY_JOIN_LIMIT_01",
    "SUBQUERY_JOIN_LIMIT_02",
    "QUERY_EXPLICIT_ALIASES",
    "QUERY_KEYWORDS_UPPER",
    "QUERY_MULTILINE",
    "QUERY_NO_COMMENT_PATCHING",
    "LIST_DATE_FIELD_01",
    "LIST_DATE_FIELD_03",
    "USER_SETTINGS_02",
    "PERIOD_TOTALS_02",
]


@dataclass
class QueryNormRepository:
    path: Path = NORMS_PATH
    norm_ids: list[str] | None = None
    cards: list[NormCard] | None = None
    version: str = "unknown"

    def __post_init__(self) -> None:
        if self.norm_ids is None:
            self.norm_ids = list(QUERY_NORM_IDS)
        if self.cards is None:
            self.cards = []
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
    source_ref = entry.get("source_reference") or entry.get("source_standard") or "—"
    return (
        f"Раздел: {section}\n"
        f"Категория: {category}\n"
        f"Название: {title}\n"
        f"Текст нормы: {norm_text}\n"
        f"Источник: {source_ref}"
    ).strip()


TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9_]{3,}")


def _tokenize(text: str) -> list[str]:
    tokens = TOKEN_RE.findall(text.lower())
    return [token for token in tokens if len(token) > 2]


@lru_cache(maxsize=1)
def get_query_norm_repository() -> QueryNormRepository:
    return QueryNormRepository()
