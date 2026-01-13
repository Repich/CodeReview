from __future__ import annotations

import json
import logging
import os
import textwrap
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable
import re
from datetime import datetime

import httpx

from worker.app.config import get_settings
from worker.app.models import AISuggestion, AnalysisTask, DetectorFinding, LLMDiagnostic
from worker.app.services.code_units import CodeUnit, split_source_into_units
from worker.app.services.norms_repo import NormCard, get_norm_repository

logger = logging.getLogger(__name__)
ROOT_DIR = Path(__file__).resolve().parents[3]

SYSTEM_PROMPT = (
    "Ты — эксперт по код-ревью конфигураций 1С и автор свода норм. "
    "Ты получаешь отдельные фрагменты модулей 1С и выдержки из стандарта. "
    "Твоя задача — найти новые нарушения норм в данном фрагменте. "
    "Не дублируй статические находки. Для каждого нарушения указывай norm_id, "
    "обоснование, строки и краткое описание. "
    "Используй только нормы из раздела «Выдержки стандартов» и не придумывай новые. "
    "norm_id должен совпадать с идентификатором из выдержек (например, std437). "
    "Если подходящей нормы нет, верни пустой массив."
)

MAX_UNIT_CODE_CHARS = 6_000
MAX_NORM_TEXT_CHARS = 8_000
MAX_UNITS_PER_RUN = 40


@dataclass
class LLMResult:
    suggestions: list[AISuggestion]
    prompt_version: str | None
    log_entries: list[LLMDiagnostic]


def generate_ai_suggestions(
    task: AnalysisTask, findings: Iterable[DetectorFinding]
) -> LLMResult | None:
    api_key = _load_api_key()
    if not api_key:
        logger.debug("DEEPSEEK_API_KEY is not configured; skipping LLM stage")
        return None

    norm_repo = get_norm_repository()
    units: list[CodeUnit] = []
    for source in task.sources:
        units.extend(split_source_into_units(source))
    if not units:
        logger.debug("No code units generated for run %s", task.review_run_id)
        return None

    logger.info("Run %s: generated %s code units", task.review_run_id, len(units))

    if len(units) > MAX_UNITS_PER_RUN:
        logger.info(
            "Truncating units for run %s from %s to %s",
            task.review_run_id,
            len(units),
            MAX_UNITS_PER_RUN,
        )
        units = units[:MAX_UNITS_PER_RUN]

    logger.debug(
        "Run %s: using norm repository version %s",
        task.review_run_id,
        norm_repo.version,
    )

    all_suggestions: list[AISuggestion] = []
    diagnostics: list[LLMDiagnostic] = []
    findings_list = list(findings)
    for unit in units:
        unit_findings = _filter_findings_for_unit(findings_list, unit)
        keywords = _derive_keywords(unit, unit_findings)
        norm_cards = norm_repo.search(keywords, limit=8)
        logger.info(
            "LLM unit %s (%s lines %s-%s): keywords=%s norms=%s findings=%s",
            unit.unit_name,
            unit.unit_type,
            unit.start_line,
            unit.end_line,
            len(keywords),
            [card.norm_id for card in norm_cards],
            len(unit_findings),
        )
        prompt = _build_unit_prompt(unit, unit_findings, norm_cards)
        response_text = _call_deepseek(prompt, api_key)
        if not response_text:
            logger.warning("LLM unit %s: no response", unit.unit_name)
            continue
        allowed_norm_ids = {card.norm_id for card in norm_cards}
        unit_suggestions = _parse_response(
            response_text,
            unit_findings,
            unit,
            allowed_norm_ids,
        )
        if unit_suggestions:
            logger.info(
                "LLM unit %s: received %s suggestions",
                unit.unit_name,
                len(unit_suggestions),
            )
            all_suggestions.extend(unit_suggestions)
        else:
            logger.info("LLM unit %s: no additional suggestions", unit.unit_name)
        diagnostics.append(
            LLMDiagnostic(
                prompt=prompt,
                response=response_text,
                context_files=[f"norm:{card.norm_id}" for card in norm_cards],
                source_paths=[unit.source_path],
                static_findings=json.loads(_serialize_findings(unit_findings)),
                created_at=datetime.utcnow().isoformat(),
                prompt_version=norm_repo.version,
                unit_id=unit.unit_id,
                unit_name=unit.unit_name,
            )
        )

    if not all_suggestions:
        logger.info("Run %s: LLM produced zero suggestions", task.review_run_id)
        return None

    logger.info(
        "Run %s: LLM produced %s suggestions across %s units",
        task.review_run_id,
        len(all_suggestions),
        len(diagnostics),
    )

    return LLMResult(
        suggestions=all_suggestions,
        prompt_version=norm_repo.version,
        log_entries=diagnostics,
    )


def _call_deepseek(prompt: str, api_key: str) -> str | None:
    settings = get_settings()
    url = settings.llm_api_base.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as exc:
        body = exc.response.text
        logger.warning(
            "LLM request failed (%s): %s",
            exc.response.status_code,
            body[:500] if body else "<empty>",
        )
        return None
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.warning("LLM request failed: %s", exc)
        return None


def _build_unit_prompt(
    unit: CodeUnit,
    findings: list[DetectorFinding],
    norm_cards: list[NormCard],
) -> str:
    code_block = _extract_relevant_code(unit)
    serialized_findings = _serialize_findings(findings)
    norm_text = _truncate_text(_format_norm_cards(norm_cards), MAX_NORM_TEXT_CHARS, "нормы")
    tags = ", ".join(sorted(unit.tags)) if unit.tags else "нет"
    changed_desc = (
        ", ".join(f"{start}-{end}" for start, end in unit.review_ranges)
        if unit.review_ranges
        else f"{unit.start_line}-{unit.end_line}"
    )

    return textwrap.dedent(
        f"""
        Модуль: {unit.source_path}
        Единица анализа: {unit.unit_name} ({unit.unit_type}), строки {unit.start_line}–{unit.end_line}
        Изменённые строки: {changed_desc}
        Характерные признаки: {tags}

        Код:
        ```
        {code_block}
        ```
        (строки, начинающиеся с символа ">", были изменены; остальные приведены только для контекста)

        Статические нарушения (JSON, может быть пустым):
        {serialized_findings}

        Выдержки стандартов:
        {norm_text}

        Инструкция:
        - Проанализируй только этот фрагмент.
        - Если строки помечены знаком ">", именно они изменены; остальные строки используй только как контекст.
        - Если знак ">" отсутствует, значит анализируется весь блок целиком.
        - Не отмечай нарушения, находящиеся исключительно в контексте, если изменённые строки их не затрагивают.
        - Если нарушение уже есть в статических находках, не повторяй его.
        - Для каждого нового нарушения верни объект с полями
          norm_id, section, category, norm_text, source_reference, severity (optional),
          evidence (массив объектов с file, lines и reason).
        - lines указывай относительно исходного файла (например "CommonModules/Module.bsl:210-235").
        - Если нарушений нет, верни пустой массив [].

        Ответ: строго JSON-массив без пояснений.
        """
    ).strip()


def _serialize_findings(findings: Iterable[DetectorFinding]) -> str:
    payload = []
    for item in findings:
        payload.append(
            {
                "norm_id": item.norm_id,
                "detector_id": item.detector_id,
                "severity": item.severity,
                "message": item.message,
                "file_path": item.file_path,
                "line": item.line,
                "snippet": item.snippet,
            }
        )
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _filter_findings_for_unit(
    findings: list[DetectorFinding], unit: CodeUnit
) -> list[DetectorFinding]:
    unit_findings: list[DetectorFinding] = []
    for item in findings:
        if item.file_path and item.file_path != unit.source_path:
            continue
        if item.line is not None and not (unit.start_line <= item.line <= unit.end_line):
            continue
        unit_findings.append(item)
    return unit_findings


def _derive_keywords(unit: CodeUnit, findings: list[DetectorFinding]) -> list[str]:
    keywords = set()
    keywords.add(unit.unit_name)
    keywords.update(unit.tags)
    for finding in findings:
        keywords.add(finding.norm_id)
        keywords.add(finding.detector_id)
        keywords.update(_tokenize_text(finding.message))
    keywords.update(_tokenize_text(unit.text)[:50])
    return list(keywords)


def _format_norm_cards(cards: list[NormCard]) -> str:
    if not cards:
        return "—"
    chunks = []
    for card in cards:
        chunks.append(f"### {card.norm_id}\n{card.body}\n")
    return "\n".join(chunks).strip()


def _parse_response(
    raw_text: str,
    unit_findings: list[DetectorFinding],
    unit: CodeUnit,
    allowed_norm_ids: set[str],
) -> list[AISuggestion]:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        lines = cleaned.splitlines()
        if lines and lines[0].lower().startswith("json"):
            lines = lines[1:]
        cleaned = "\n".join(lines)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("LLM response is not a valid JSON payload")
        return []

    suggestions: list[AISuggestion] = []
    if not isinstance(parsed, list):
        return suggestions

    existing_norms = {finding.norm_id for finding in unit_findings}
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        norm_text = entry.get("norm_text")
        if not norm_text:
            continue
        norm_id = entry.get("norm_id")
        if not norm_id or norm_id not in allowed_norm_ids:
            logger.debug("Skipping unknown norm_id: %s", norm_id)
            continue
        if norm_id and norm_id in existing_norms:
            logger.debug("Skipping norm %s already covered by static finding", norm_id)
            continue
        if not _evidence_matches_entry(entry, unit):
            logger.debug("Skipping norm %s due to invalid evidence", norm_id)
            continue
        suggestion = AISuggestion(
            norm_id=norm_id,
            section=entry.get("section"),
            category=entry.get("category"),
            norm_text=str(norm_text),
            source_reference=entry.get("source_reference"),
            severity=entry.get("severity"),
            evidence=entry.get("evidence"),
            llm_raw_response=entry,
        )
        suggestions.append(suggestion)
    return suggestions


@lru_cache(maxsize=1)
def _load_api_key() -> str | None:
    key = os.getenv("DEEPSEEK_API_KEY")
    if key:
        return key
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return None
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if not line or line.strip().startswith("#"):
                continue
            if "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name.strip() == "DEEPSEEK_API_KEY":
                key = value.strip()
                os.environ["DEEPSEEK_API_KEY"] = key
                return key
    except OSError:
        return None
    return None


def _truncate_text(text: str, limit: int, label: str) -> str:
    if len(text) <= limit:
        return text
    suffix = f"\n\n[Обрезано автоматически: показаны первые {limit} символов из {len(text)} ({label}).]"
    logger.debug("Truncating %s to %s/%s chars", label, limit, len(text))
    return text[:limit] + suffix


TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9_]{3,}")


def _tokenize_text(text: str) -> list[str]:
    return [token for token in TOKEN_RE.findall(text.lower()) if len(token) > 2]


def _evidence_matches_entry(entry: dict, unit: CodeUnit) -> bool:
    norm_id = (entry.get("norm_id") or "").upper()
    evidence = entry.get("evidence") or []
    if not evidence:
        return False
    if norm_id == "STD456":
        return any(
            _lines_contain_pattern(unit, ev.get("lines"), pattern=r"[A-Za-z]")
            for ev in evidence
        )
    if norm_id == "STD444":
        return any(
            _lines_exceed_length(unit, ev.get("lines"), limit=150)
            for ev in evidence
        )
    return True


def _lines_contain_pattern(unit: CodeUnit, lines: str | None, pattern: str) -> bool:
    if not lines:
        return False
    regex = re.compile(pattern)
    for line in _extract_lines(unit, lines):
        if regex.search(line):
            return True
    return False


def _lines_exceed_length(unit: CodeUnit, lines: str | None, limit: int) -> bool:
    if not lines:
        return False
    for line in _extract_lines(unit, lines):
        if len(line) > limit:
            return True
    return False


def _extract_lines(unit: CodeUnit, lines: str) -> list[str]:
    extracted: list[str] = []
    parts = lines.split(":")
    range_part = parts[-1]
    if "-" in range_part:
        start, end = range_part.split("-", 1)
    else:
        start = end = range_part
    try:
        start_no = int(start.strip())
        end_no = int(end.strip())
    except ValueError:
        return []
    unit_lines = unit.text.splitlines()
    for idx in range(max(1, start_no) - unit.start_line + 1, end_no - unit.start_line + 2):
        if 0 <= idx - 1 < len(unit_lines):
            extracted.append(unit_lines[idx - 1])
    return extracted


def _extract_relevant_code(unit: CodeUnit) -> str:
    text = unit.text.strip("\n")
    if not text:
        return ""
    lines = unit.text.splitlines()
    if not unit.review_ranges:
        numbered = [
            f"{unit.start_line + idx:>5}: {line}" for idx, line in enumerate(lines)
        ]
        return _truncate_text("\n".join(numbered), MAX_UNIT_CODE_CHARS, "фрагмент кода")

    context = 3
    min_line = min(start for start, _ in unit.review_ranges)
    max_line = max(end for _, end in unit.review_ranges)
    start_idx = max(min_line - context - unit.start_line, 0)
    end_idx = min(max_line - unit.start_line + context, len(lines) - 1)
    snippet: list[str] = []
    for idx in range(start_idx, end_idx + 1):
        absolute_line = unit.start_line + idx
        marker = ">" if any(start <= absolute_line <= end for start, end in unit.review_ranges) else " "
        snippet.append(f"{marker} {absolute_line:>5}: {lines[idx]}")
    return _truncate_text("\n".join(snippet), MAX_UNIT_CODE_CHARS, "фрагмент кода")
