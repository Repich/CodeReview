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
from worker.app.services.redaction import redact_lines, redact_text, RedactionStats
from worker.app.services.critical_norms import get_critical_norm_repository
from worker.app.services.pattern_norms import get_pattern_norm_repository
from worker.app.services.norms_repo import NormCard
from worker.app.services.query_norms import get_query_norm_repository
from worker.app.services.query_units import QueryUnit, extract_query_units

logger = logging.getLogger(__name__)
ROOT_DIR = Path(__file__).resolve().parents[3]

SYSTEM_PROMPT = (
    "Ты — ведущий архитектор и ревьюер 1С:Предприятие (BSL) с опытом промышленной "
    "эксплуатации и high-load. Задача: делать практическое код-ревью предоставленного "
    "кода 1С, выявляя дефекты и риски, которые проявятся в эксплуатации: корректность, "
    "производительность, безопасность, устойчивость, сопровождаемость. "
    "Ты получаешь отдельные фрагменты модулей 1С и выдержки из стандарта. "
    "Твоя задача — найти новые нарушения норм в данном фрагменте. "
    "Не дублируй статические находки. Для каждого нарушения указывай norm_id, "
    "обоснование, строки и краткое описание. "
    "Используй только нормы из раздела «Выдержки стандартов» и не придумывай новые. "
    "norm_id должен совпадать с идентификатором из выдержек (например, std437). "
    "Не возвращай проверки соответствия норме или комментарии «нарушений нет». "
    "Если подходящей нормы нет, верни пустой массив."
)

QUERY_SYSTEM_PROMPT = (
    "Ты — ведущий архитектор и ревьюер 1С:Предприятие (BSL) с опытом промышленной "
    "эксплуатации и high-load. Задача: делать практическое код-ревью предоставленного "
    "кода 1С, выявляя дефекты и риски, которые проявятся в эксплуатации: корректность, "
    "производительность, безопасность, устойчивость, сопровождаемость. "
    "Ты — эксперт по ревью текстов запросов 1С. "
    "Ты получаешь только текст запроса из модуля. "
    "Твоя задача — найти нарушения норм по запросам. "
    "Используй только нормы из раздела «Выдержки стандартов» и не придумывай новые. "
    "norm_id должен совпадать с идентификатором из выдержек. "
    "Если есть потенциальное нарушение или риск, даже если требуется проверка контекста "
    "(объем данных, индексы, назначение результата), все равно верни его и пометь в reason, "
    "что это «возможное» нарушение. "
    "Не возвращай проверки соответствия норме или комментарии «нарушений нет». "
    "Если сомневаешься, лучше вернуть потенциальное нарушение с severity info/warning, чем пустой массив."
)

MAX_UNIT_CODE_CHARS = 6_000
MAX_NORM_TEXT_CHARS = 40_000
MAX_UNITS_PER_RUN = 40
MAX_QUERY_TEXT_CHARS = 32_000
MAX_QUERY_NORM_TEXT_CHARS = 40_000
MAX_QUERY_UNITS_PER_RUN = 40
MAX_PATTERN_NORM_TEXT_CHARS = 40_000
QUERY_TEMPERATURE = 0.2

PATTERN_SYSTEM_PROMPT = (
    "Ты — ведущий архитектор и ревьюер 1С:Предприятие (BSL) с опытом промышленной "
    "эксплуатации и high-load. Задача: делать практическое код-ревью предоставленного "
    "кода 1С, выявляя дефекты и риски, которые проявятся в эксплуатации: корректность, "
    "производительность, безопасность, устойчивость, сопровождаемость. "
    "Ты — ведущий архитектор 1С. Ищи только нарушения архитектурных паттернов: SRP, SoC, CQRS, "
    "Repository, Unit of Work, устойчивость интеграций (идемпотентность, Circuit Breaker, "
    "retry/backoff, Bulkhead, Adapter) и другие из списка. Не дублируй статические находки. "
    "Возвращай только предполагаемые нарушения паттернов."
)


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

    norm_repo = get_critical_norm_repository()
    units: list[CodeUnit] = []
    for source in task.sources:
        units.extend(split_source_into_units(source))

    if units:
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
    prompt_versions: list[str] = []
    findings_list = list(findings)
    if units:
        if not norm_repo.cards:
            logger.warning("Norm repository is empty; skipping LLM stage for code units")
        else:
            prompt_versions.append(norm_repo.version)
            allowed_norm_ids = {card.norm_id for card in norm_repo.cards}
            for unit in units:
                unit_findings = _filter_findings_for_unit(findings_list, unit)
                norm_cards = norm_repo.cards
                # debug: logger.info(
                #     "LLM unit %s (%s lines %s-%s): norms=%s findings=%s",
                #     unit.unit_name,
                #     unit.unit_type,
                #     unit.start_line,
                #     unit_end_line,
                #     len(norm_cards),
                #     len(unit_findings),
                # )
                prompt, redaction_report = _build_unit_prompt(unit, unit_findings, norm_cards)
                response_text = _call_deepseek(prompt, api_key)
                if not response_text:
                    logger.warning("LLM unit %s: no response", unit.unit_name)
                    continue
                unit_suggestions = _parse_response(
                    response_text,
                    unit_findings,
                    unit,
                    allowed_norm_ids,
                    norm_lookup=norm_repo.entries,
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
                        static_findings=json.loads(_serialize_findings(unit_findings)[0]),
                        created_at=datetime.utcnow().isoformat(),
                        prompt_version=norm_repo.version,
                        unit_id=unit.unit_id,
                        unit_name=unit.unit_name,
                        redaction_report=redaction_report,
                    )
                )

    # Паттерны (отдельный проход)
    pattern_repo = get_pattern_norm_repository()
    if units and pattern_repo.cards:
        pattern_norm_ids = set(pattern_repo.norm_ids)
        prompt_versions.append(f"pattern:{pattern_repo.version}")
        for unit in units:
            unit_findings = _filter_findings_for_unit(findings_list, unit)
            prompt, redaction_report = _build_pattern_prompt(unit, unit_findings, pattern_repo.cards)
            response_text = _call_deepseek(
                prompt,
                api_key,
                system_prompt=PATTERN_SYSTEM_PROMPT,
                temperature=0,
            )
            if not response_text:
                logger.warning("LLM patterns %s: no response", unit.unit_name)
                continue
            unit_suggestions = _parse_response(
                response_text,
                unit_findings,
                unit,
                pattern_norm_ids,
                norm_lookup=pattern_repo.entries,
            )
            if unit_suggestions:
                logger.info(
                    "LLM patterns %s: received %s suggestions",
                    unit.unit_name,
                    len(unit_suggestions),
                )
                all_suggestions.extend(unit_suggestions)
            diagnostics.append(
                LLMDiagnostic(
                    prompt=prompt,
                    response=response_text,
                    context_files=[f"pattern:{card.norm_id}" for card in pattern_repo.cards],
                    source_paths=[unit.source_path],
                    static_findings=json.loads(_serialize_findings(unit_findings)[0]),
                    created_at=datetime.utcnow().isoformat(),
                    prompt_version=f"pattern:{pattern_repo.version}",
                    unit_id=unit.unit_id,
                    unit_name=unit.unit_name,
                    redaction_report=redaction_report,
                )
            )

    query_units: list[QueryUnit] = []
    for source in task.sources:
        query_units.extend(extract_query_units(source))
    if query_units:
        logger.info("Run %s: extracted %s query blocks", task.review_run_id, len(query_units))
    if len(query_units) > MAX_QUERY_UNITS_PER_RUN:
        logger.info(
            "Truncating query units for run %s from %s to %s",
            task.review_run_id,
            len(query_units),
            MAX_QUERY_UNITS_PER_RUN,
        )
        query_units = query_units[:MAX_QUERY_UNITS_PER_RUN]

    if query_units:
        query_norm_repo = get_query_norm_repository()
        if not query_norm_repo.cards:
            logger.warning("Query norms are not available; skipping query LLM stage")
            query_units = []
        else:
            query_norm_ids = set(query_norm_repo.norm_ids)
            prompt_versions.append(f"query:{query_norm_repo.version}")
            for unit in query_units:
                unit_findings = [
                    item
                    for item in _filter_findings_for_unit(findings_list, unit)
                    if item.norm_id in query_norm_ids
                ]
                logger.info(
                    "LLM query %s lines %s-%s: norms=%s findings=%s",
                    unit.unit_name,
                    unit.start_line,
                    unit.end_line,
                    len(query_norm_repo.cards),
                    len(unit_findings),
                )
                prompt, redaction_report = _build_query_prompt(unit, unit_findings, query_norm_repo.cards)
                response_text = _call_deepseek(
                    prompt,
                    api_key,
                    system_prompt=QUERY_SYSTEM_PROMPT,
                    temperature=QUERY_TEMPERATURE,
                )
                if not response_text:
                    logger.warning("LLM query %s: no response", unit.unit_name)
                    continue
                unit_suggestions = _parse_response(
                    response_text,
                    unit_findings,
                    unit,
                    query_norm_ids,
                    norm_lookup=query_norm_repo.entries,
                )
                if unit_suggestions:
                    logger.info(
                        "LLM query %s: received %s suggestions",
                        unit.unit_name,
                        len(unit_suggestions),
                    )
                    all_suggestions.extend(unit_suggestions)
                else:
                    logger.info("LLM query %s: no additional suggestions", unit.unit_name)
                diagnostics.append(
                    LLMDiagnostic(
                        prompt=prompt,
                        response=response_text,
                        context_files=[f"norm:{card.norm_id}" for card in query_norm_repo.cards],
                        source_paths=[unit.source_path],
                        static_findings=json.loads(_serialize_findings(unit_findings)[0]),
                        created_at=datetime.utcnow().isoformat(),
                        prompt_version=query_norm_repo.version,
                        unit_id=unit.unit_id,
                        unit_name=unit.unit_name,
                        redaction_report=redaction_report,
                    )
                )

    if not all_suggestions:
        logger.info("Run %s: LLM produced zero suggestions", task.review_run_id)
        if not diagnostics:
            return None
        return LLMResult(
            suggestions=[],
            prompt_version=";".join(prompt_versions) if prompt_versions else None,
            log_entries=diagnostics,
        )

    logger.info(
        "Run %s: LLM produced %s suggestions across %s units",
        task.review_run_id,
        len(all_suggestions),
        len(diagnostics),
    )

    return LLMResult(
        suggestions=all_suggestions,
        prompt_version=";".join(prompt_versions) if prompt_versions else None,
        log_entries=diagnostics,
    )


def _call_deepseek(
    prompt: str,
    api_key: str,
    system_prompt: str = SYSTEM_PROMPT,
    temperature: float = 0,
) -> str | None:
    settings = get_settings()
    url = settings.llm_api_base.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
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
) -> tuple[str, dict]:
    code_block, redaction_report = _extract_relevant_code(unit)
    serialized_findings, findings_redaction = _serialize_findings(findings)
    if findings_redaction:
        redaction_report["redacted_in_findings"] = findings_redaction
    norm_text = _truncate_text(_format_norm_cards(norm_cards), MAX_NORM_TEXT_CHARS, "нормы")
    tags = ", ".join(sorted(unit.tags)) if unit.tags else "нет"
    changed_desc = (
        ", ".join(f"{start}-{end}" for start, end in unit.review_ranges)
        if unit.review_ranges
        else f"{unit.start_line}-{unit.end_line}"
    )

    prompt = textwrap.dedent(
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
        - Не возвращай записи, где указано, что нарушений нет или что фрагмент соответствует норме.
        - Для каждого нового нарушения верни объект с полями
          norm_id, section, category, norm_text, source_reference, severity (optional),
          evidence (массив объектов с file, lines и reason).
        - lines указывай относительно исходного файла (например "CommonModules/Module.bsl:210-235").
        - Если нарушений нет, верни пустой массив [].

        Ответ: строго JSON-массив без пояснений.
        """
    ).strip()
    return prompt, redaction_report


def _build_query_prompt(
    unit: QueryUnit,
    findings: list[DetectorFinding],
    norm_cards: list[NormCard],
) -> tuple[str, dict]:
    query_block, redaction_report = _format_query_lines(unit)
    serialized_findings, findings_redaction = _serialize_findings(findings)
    if findings_redaction:
        redaction_report["redacted_in_findings"] = findings_redaction
    norm_text = _truncate_text(
        _format_norm_cards(norm_cards), MAX_QUERY_NORM_TEXT_CHARS, "нормы"
    )
    prompt = textwrap.dedent(
        f"""
        Модуль: {unit.source_path}
        Блок запроса: строки {unit.start_line}–{unit.end_line}

        Текст запроса (строки из исходного файла):
        ```
        {query_block}
        ```

        Статические нарушения (JSON, может быть пустым):
        {serialized_findings}

        Выдержки стандартов:
        {norm_text}

        Инструкция:
        - Анализируй только текст запроса в блоке выше.
        - Некоторые строки могут быть собраны динамически и не начинаться с символа "|".
        - Не отмечай нарушения, которые уже есть в статических находках.
        - Если нарушение зависит от контекста (объем данных, индексы, назначение результата),
          все равно укажи его как потенциальное и отметь в reason, что требуется проверка.
        - При низкой уверенности допускается эвристика — лучше вернуть возможное нарушение,
          чем пустой массив.
        - Не возвращай записи, где указано, что нарушений нет или что запрос соответствует норме.
        - Для каждого нового нарушения верни объект с полями
          norm_id, severity (optional), evidence (массив объектов с file, lines и reason).
        - Не добавляй norm_text/section/category/source_reference — мы заполним их по norm_id.
        - В текстовых полях избегай двойных кавычек, используй «» или одинарные кавычки.
        - lines указывай относительно исходного файла (например "CommonModules/Module.bsl:210-235").
        - Если нарушений нет, верни пустой массив [].

        Ответ: строго JSON-массив без пояснений.
        """
    ).strip()
    return prompt, redaction_report


def _build_pattern_prompt(
    unit: CodeUnit,
    findings: list[DetectorFinding],
    norm_cards: list[NormCard],
) -> tuple[str, dict]:
    code_block, redaction_report = _extract_relevant_code(unit)
    serialized_findings, findings_redaction = _serialize_findings(findings)
    if findings_redaction:
        redaction_report["redacted_in_findings"] = findings_redaction
    norm_text = _truncate_text(
        _format_norm_cards(norm_cards), MAX_PATTERN_NORM_TEXT_CHARS, "паттерны"
    )
    tags = ", ".join(sorted(unit.tags)) if unit.tags else "нет"
    changed_desc = (
        ", ".join(f"{start}-{end}" for start, end in unit.review_ranges)
        if unit.review_ranges
        else f"{unit.start_line}-{unit.end_line}"
    )
    prompt = textwrap.dedent(
        f"""
        Модуль: {unit.source_path}
        Единица анализа: {unit.unit_name} ({unit.unit_type}), строки {unit.start_line}–{unit.end_line}
        Изменённые строки: {changed_desc}
        Характерные признаки: {tags}

        Код:
        ```
        {code_block}
        ```

        Статические нарушения (JSON, может быть пустым):
        {serialized_findings}

        Паттерны (карточки):
        {norm_text}

        Инструкция:
        - Ищи только нарушения паттернов из списка (SRP/SoC/CQRS/Repository/Unit of Work и паттерны устойчивости/интеграций).
        - Не повторяй статические нарушения.
        - При низкой уверенности указывай в reason: «предполагаемое нарушение паттерна <название>».
        - Для каждого нарушения верни norm_id, section, category, norm_text, source_reference, severity (optional),
          evidence (массив объектов с file, lines, reason).
        - lines указывай относительно исходного файла (например \"CommonModules/Module.bsl:210-235\").
        - Если нарушений нет, верни [].

        Ответ: строго JSON-массив без пояснений.
        """
    ).strip()
    return prompt, redaction_report


def _serialize_findings(findings: Iterable[DetectorFinding]) -> tuple[str, int]:
    payload = []
    redaction_count = 0
    for item in findings:
        snippet = item.snippet
        if snippet:
            redacted_snippet, stats = redact_text(snippet)
            snippet = redacted_snippet
            redaction_count += stats.total_literals
        payload.append(
            {
                "norm_id": item.norm_id,
                "detector_id": item.detector_id,
                "severity": item.severity,
                "message": item.message,
                "file_path": item.file_path,
                "line": item.line,
                "snippet": snippet,
            }
        )
    return json.dumps(payload, ensure_ascii=False, indent=2), redaction_count


def _filter_findings_for_unit(
    findings: list[DetectorFinding], unit: CodeUnit | QueryUnit
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
    unit: CodeUnit | QueryUnit,
    allowed_norm_ids: set[str],
    norm_lookup: dict[str, dict] | None = None,
) -> list[AISuggestion]:
    parsed = _load_json_array(raw_text)
    if parsed is None:
        logger.warning("LLM response is not a valid JSON payload")
        return []

    suggestions: list[AISuggestion] = []
    if not isinstance(parsed, list):
        return suggestions

    existing_norms = {finding.norm_id for finding in unit_findings}
    norm_id_map = {norm_id.upper(): norm_id for norm_id in allowed_norm_ids}
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        norm_id_raw = str(entry.get("norm_id") or "").strip()
        norm_id = norm_id_map.get(norm_id_raw.upper())
        if not norm_id:
            logger.debug("Skipping unknown norm_id: %s", norm_id_raw)
            continue
        if norm_id and norm_id in existing_norms:
            logger.debug("Skipping norm %s already covered by static finding", norm_id)
            continue
        evidence = entry.get("evidence")
        if isinstance(evidence, dict):
            evidence = [evidence]
        elif evidence is not None and not isinstance(evidence, list):
            evidence = None
        entry["evidence"] = evidence
        if not _evidence_matches_entry(entry, unit):
            logger.debug("Skipping norm %s due to invalid evidence", norm_id)
            continue
        meta = norm_lookup.get(norm_id) if norm_lookup else {}
        norm_text = entry.get("norm_text") or (meta.get("norm_text") if meta else None)
        if not norm_text:
            continue
        suggestion = AISuggestion(
            norm_id=norm_id,
            section=entry.get("section") or (meta.get("section") if meta else None),
            category=entry.get("category") or (meta.get("category") if meta else None),
            norm_text=str(norm_text),
            source_reference=entry.get("source_reference")
            or (meta.get("source_reference") or meta.get("source_standard") if meta else None),
            severity=entry.get("severity"),
            evidence=entry.get("evidence"),
            llm_raw_response=entry,
        )
        suggestions.append(suggestion)
    return suggestions


def _load_json_array(raw_text: str) -> list[dict] | None:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        lines = cleaned.splitlines()
        if lines and lines[0].lower().startswith("json"):
            lines = lines[1:]
        cleaned = "\n".join(lines).strip()
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    snippet = cleaned[start : end + 1]
    try:
        parsed = json.loads(snippet)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, list):
        return parsed
    return None

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


def _base_redaction_report(unit: CodeUnit | QueryUnit, stats: RedactionStats) -> dict:
    return {
        "source_path": unit.source_path,
        "unit_id": getattr(unit, "unit_id", None),
        "unit_name": unit.unit_name,
        "redacted_literals": stats.total_literals,
        "redacted_lines": stats.lines_with_redactions,
        "redactions_by_line": stats.redactions_by_line,
    }


def _filter_redaction_report(
    unit: CodeUnit | QueryUnit,
    stats: RedactionStats,
    included_lines: set[int],
) -> dict:
    if not included_lines:
        return _base_redaction_report(unit, stats)
    redactions_by_line = {
        line_no: count
        for line_no, count in stats.redactions_by_line.items()
        if line_no in included_lines
    }
    filtered = RedactionStats(
        total_literals=sum(redactions_by_line.values()),
        lines_with_redactions=sorted(redactions_by_line),
        redactions_by_line=redactions_by_line,
    )
    return _base_redaction_report(unit, filtered)


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


def _extract_relevant_code(unit: CodeUnit) -> tuple[str, dict]:
    text = unit.text.strip("\n")
    if not text:
        return "", _base_redaction_report(unit, RedactionStats(0, [], {}))
    lines = unit.text.splitlines()
    cleaned_lines = _strip_comments(lines)
    redacted_lines, stats = redact_lines(cleaned_lines, unit.start_line)
    if not unit.review_ranges:
        numbered = [
            f"{unit.start_line + idx:>5}: {line}" for idx, line in enumerate(redacted_lines)
        ]
        return (
            _truncate_text("\n".join(numbered), MAX_UNIT_CODE_CHARS, "фрагмент кода"),
            _base_redaction_report(unit, stats),
        )

    context = 3
    min_line = min(start for start, _ in unit.review_ranges)
    max_line = max(end for _, end in unit.review_ranges)
    start_idx = max(min_line - context - unit.start_line, 0)
    end_idx = min(max_line - unit.start_line + context, len(lines) - 1)
    included_lines = {unit.start_line + idx for idx in range(start_idx, end_idx + 1)}
    snippet: list[str] = []
    for idx in range(start_idx, end_idx + 1):
        absolute_line = unit.start_line + idx
        marker = ">" if any(start <= absolute_line <= end for start, end in unit.review_ranges) else " "
        snippet.append(f"{marker} {absolute_line:>5}: {redacted_lines[idx]}")
    return (
        _truncate_text("\n".join(snippet), MAX_UNIT_CODE_CHARS, "фрагмент кода"),
        _filter_redaction_report(unit, stats, included_lines),
    )


def _format_query_lines(unit: QueryUnit) -> tuple[str, dict]:
    raw_lines = [line for _, line in unit.line_map]
    redacted_lines, stats = redact_lines(raw_lines, unit.start_line)
    numbered = [
        f"{line_no:>5}: {line}"
        for (line_no, _), line in zip(unit.line_map, redacted_lines)
    ]
    return (
        _truncate_text("\n".join(numbered), MAX_QUERY_TEXT_CHARS, "текст запроса"),
        _filter_redaction_report(unit, stats, {line_no for line_no, _ in unit.line_map}),
    )


def _strip_comments(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    in_block_comment = False
    for raw in lines:
        result_chars: list[str] = []
        i = 0
        in_string = False
        while i < len(raw):
            ch = raw[i]
            nxt = raw[i + 1] if i + 1 < len(raw) else ""
            if in_block_comment:
                if ch == "*" and nxt == "/":
                    in_block_comment = False
                    i += 2
                    continue
                i += 1
                continue
            if in_string:
                if ch == '"' and nxt == '"':
                    result_chars.append('"')
                    result_chars.append('"')
                    i += 2
                    continue
                if ch == '"':
                    in_string = False
                    result_chars.append(ch)
                    i += 1
                    continue
                result_chars.append(ch)
                i += 1
                continue
            if ch == "/" and nxt == "/":
                break
            if ch == "/" and nxt == "*":
                in_block_comment = True
                i += 2
                continue
            if ch == '"':
                in_string = True
                result_chars.append(ch)
                i += 1
                continue
            result_chars.append(ch)
            i += 1
        cleaned.append("".join(result_chars))
    return cleaned
