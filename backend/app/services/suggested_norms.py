from __future__ import annotations

import json
import logging
import textwrap
from pathlib import Path
from typing import Any

from backend.app.models.norm import Norm
from backend.app.schemas.suggested_norms import SuggestedNormLLMResult
from backend.app.services.llm_playground import LLMPlaygroundError, request_llm_playground

logger = logging.getLogger(__name__)

MAX_NORM_TEXT_CHARS = 0  # мы не отправляем norm_text

CANONICAL_SECTIONS: list[tuple[str, tuple[str, ...]]] = [
    ("Безопасность", ("безопас", "парол", "auth", "tls", "rce", "sql-инъ", "доступ")),
    ("Запросы/SQL", ("запрос", "query", "join", "select", "вт", "индекс", "остат", "упоряд")),
    ("Транзакции/Блокировки", ("транзак", "блокир", "lock", "монопол", "исключит", "управляемая")),
    ("Архитектура/Стиль", ("архитект", "паттерн", "solid", "стиль", "code", "оформление")),
    ("UI/Формы", ("форма", "ui", "интерфейс", "элемент формы", "управляемое прил")),
    ("Данные/Метаданные", ("метадан", "справочник", "документ", "регистр", "реквизит")),
    ("Интеграции/Инфра", ("http", "ftp", "интеграц", "обмен", "внешн", "компонент")),
    ("Производительность", ("производ", "perf", "оптимизац", "кэш", "slow")),
    ("Прочее", ()),
]


def _load_catalog_norms() -> list[dict[str, Any]]:
    root_dir = Path(__file__).resolve().parents[3]
    paths = [root_dir / "norms.yaml", root_dir / "critical_norms.yaml"]
    try:
        import yaml  # lazy import
    except ImportError:
        logger.warning("yaml not available, cannot load norms catalog")
        return []
    results: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load %s: %s", path.name, exc)
            continue
        entries = data.get("norms") if isinstance(data, dict) else data
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            if not entry.get("norm_id"):
                continue
            sev = str(entry.get("default_severity") or "").lower()
            if sev == "info":
                continue
            results.append(entry)
    return results


def _truncate_norm(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "norm_id": entry.get("norm_id"),
        "title": entry.get("title"),
        "section": entry.get("section"),
        "scope": entry.get("scope"),
        "default_severity": entry.get("default_severity"),
    }


def build_sections_list(db_norms: list[Norm], catalog_norms: list[dict[str, Any]]) -> list[str]:
    sections = set()
    for norm in db_norms:
        sections.add(map_section_name(norm.section))
    for entry in catalog_norms:
        if isinstance(entry, dict) and entry.get("section"):
            sections.add(map_section_name(entry["section"]))
    # сохраняем порядок из CANONICAL_SECTIONS
    ordered = [name for name, _ in CANONICAL_SECTIONS if name in sections]
    return ordered or [name for name, _ in CANONICAL_SECTIONS]


def map_section_name(section: str) -> str:
    lowered = (section or "").lower()
    for name, keywords in CANONICAL_SECTIONS:
        if not keywords:
            continue
        if any(k in lowered for k in keywords):
            return name
    return "Прочее"


def call_llm_for_norm(
    user_section: str,
    user_severity: str,
    user_text: str,
    db_norms: list[Norm],
    catalog_norms: list[dict[str, Any]] | None = None,
) -> SuggestedNormLLMResult:
    catalog_norms = catalog_norms or []
    combined_norms = []
    for norm in db_norms:
        if str(norm.default_severity or "").lower() == "info":
            continue
        combined_norms.append(
            _truncate_norm(
                {
                    "norm_id": norm.norm_id,
                    "title": norm.title,
                    "section": norm.section,
                    "scope": norm.scope,
                    "default_severity": norm.default_severity,
                    "norm_text": norm.norm_text,
                }
            )
        )
    for entry in catalog_norms:
        combined_norms.append(_truncate_norm(entry))

    system_prompt = (
        "Ты заполняешь карточку новой нормы код-ревью 1С. "
        "Тебе дают черновой текст нормы от пользователя. "
        "Нужно: (1) Проверить, дубликат ли это существующей нормы (любое смысловое совпадение темы считается дубликатом, даже если формулировки различаются); "
        "(2) Если не дубликат — оформить норму по образцу: norm_id, title, section, scope, "
        "detector_type, check_type, default_severity, version (целое), norm_text (формализуй, но по смыслу пользователя). "
        "Всегда отвечай строго JSON без комментариев."
    )
    user_prompt = (
        "Существующие нормы (усечённые):\n"
        f"{json.dumps(combined_norms, ensure_ascii=False, indent=2)}\n\n"
        "Черновик новой нормы:\n"
        f"section={user_section}, severity={user_severity}\n"
        f"text={user_text}\n\n"
        "Верни JSON вида:\n"
        "{\n"
        '  "duplicate": true/false,\n'
        '  "duplicate_norm_ids": ["..."],\n'
        '  "norm_id": "...",\n'
        '  "title": "...",\n'
        '  "section": "...",\n'
        '  "scope": "...",\n'
        '  "detector_type": "...",\n'
        '  "check_type": "...",\n'
        '  "default_severity": "...",\n'
        '  "version": 1,\n'
        '  "norm_text": "..."\n'
        "}\n"
        "Если это дубликат — duplicate=true и duplicate_norm_ids заполни, остальные поля можно оставить пустыми."
    )

    response = request_llm_playground(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.0,
        model="deepseek-chat",
    )
    raw = response.response
    parsed = _extract_json(raw)
    if not parsed:
        raise LLMPlaygroundError("Не удалось распарсить ответ LLM", None)
    return SuggestedNormLLMResult(
        duplicate=bool(parsed.get("duplicate")),
        duplicate_norm_ids=parsed.get("duplicate_norm_ids") or [],
        norm_id=parsed.get("norm_id"),
        title=parsed.get("title"),
        section=parsed.get("section"),
        scope=parsed.get("scope"),
        detector_type=parsed.get("detector_type"),
        check_type=parsed.get("check_type"),
        default_severity=parsed.get("default_severity"),
        version=parsed.get("version"),
        norm_text=parsed.get("norm_text"),
        raw_response=raw,
    )


def _extract_json(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = text[start : end + 1]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            return None
    return None
