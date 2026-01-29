from __future__ import annotations

import json
import logging
import os
import textwrap
from dataclasses import dataclass, asdict
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Any
import re
from datetime import datetime

import httpx

from worker.app.config import get_settings
from worker.app.models import AISuggestion, AnalysisTask, DetectorFinding, LLMDiagnostic
from worker.app.services.code_units import CodeUnit, split_source_into_units
from worker.app.services.redaction import redact_lines, redact_text, RedactionStats


@dataclass
class CommentRedactionStats:
    total_comments: int
    lines_with_comments: list[int]
    comments_by_line: dict[int, int]
from worker.app.services.critical_norms import get_critical_norm_repository
from worker.app.services.general_norms import get_general_norm_repository
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
MAX_NORM_SELECTION_CHARS = 100_000
QUERY_TEMPERATURE = 0.2
PREFILTER_MAX_CARDS = 60

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

SELECTION_SYSTEM_PROMPT = (
    "Ты — ведущий архитектор и ревьюер 1С:Предприятие (BSL) с опытом промышленной "
    "эксплуатации и high-load. Твоя задача — выбрать из списка норм только те, которые "
    "можно проверить по данному фрагменту кода. "
    "Используй только предоставленный список норм. "
    "Если подходящих норм нет — верни пустой массив."
)

MERGE_SYSTEM_PROMPT = (
    "Ты — ведущий архитектор и ревьюер 1С:Предприятие (BSL) с опытом промышленной "
    "эксплуатации и high-load. Твоя задача — объединить список нарушений, удалить дубли "
    "и вернуть единый итоговый массив. "
    "Используй только переданные данные, не придумывай новые нарушения. "
    "Если элементы дублируются, оставь наиболее подробный (с большим числом evidence). "
    "Ответ: строго JSON-массив."
)


@dataclass
class LLMResult:
    suggestions: list[AISuggestion]
    prompt_version: str | None
    log_entries: list[LLMDiagnostic]
    evaluation_report: dict[str, Any] | None = None


def generate_ai_suggestions(
    task: AnalysisTask, findings: Iterable[DetectorFinding]
) -> LLMResult | None:
    settings = get_settings()
    api_key = _load_api_key(settings.llm_provider)
    if not api_key:
        logger.debug("LLM API key is not configured; skipping LLM stage")
        return None

    norm_repo = get_critical_norm_repository()
    llm_provider = (task.settings or {}).get("llm_provider") or settings.llm_provider
    llm_model = (task.settings or {}).get("llm_model") or settings.llm_model
    use_all_norms = bool(task.settings and task.settings.get("use_all_norms"))
    disable_patterns = bool(task.settings and task.settings.get("disable_patterns"))
    general_repo = get_general_norm_repository() if use_all_norms else None
    evaluation_config = (task.context or {}).get("evaluation_config") if task.context else None
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
    critical_suggestions: list[AISuggestion] = []
    general_suggestions: list[AISuggestion] = []
    pattern_suggestions: list[AISuggestion] = []
    query_suggestions: list[AISuggestion] = []
    diagnostics: list[LLMDiagnostic] = []
    prompt_versions: list[str] = []
    findings_list = list(findings)
    selected_by_unit: dict[str, list[NormCard]] = {}

    if units:
        selection_pool: list[NormCard] = []
        if norm_repo.cards:
            selection_pool.extend(norm_repo.cards)
        if general_repo and general_repo.cards:
            selection_pool.extend(general_repo.cards)
        if not selection_pool:
            logger.warning("Norm repository is empty; skipping LLM selection stage")
        else:
            if evaluation_config:
                report = _evaluate_selection_compare(
                    units=units,
                    norm_cards=selection_pool,
                    api_key=api_key,
                    diagnostics=diagnostics,
                    selection_runs=_extract_selection_runs(evaluation_config),
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                )
                prompt_versions.append("evaluation")
                return LLMResult(
                    suggestions=[],
                    prompt_version="evaluation",
                    log_entries=diagnostics,
                    evaluation_report=report,
                )
            for unit in units:
                selected_by_unit[unit.unit_id] = _select_norm_cards(
                    unit,
                    selection_pool,
                    api_key,
                    diagnostics,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                )

    # Паттерны (отдельный проход)
    pattern_repo = get_pattern_norm_repository()
    if units and pattern_repo.cards and not disable_patterns:
        pattern_norm_ids = set(pattern_repo.norm_ids)
        prompt_versions.append(f"pattern:{pattern_repo.version}")
        for unit in units:
            unit_findings = _filter_findings_for_unit(findings_list, unit)
            prompt, redaction_report = _build_pattern_prompt(unit, unit_findings, pattern_repo.cards)
            response_text = _call_llm(
                prompt,
                api_key,
                system_prompt=PATTERN_SYSTEM_PROMPT,
                temperature=0,
                provider=llm_provider,
                model=llm_model,
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
                pattern_suggestions.extend(unit_suggestions)
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

    # Критические нормы (код)
    if units and norm_repo.cards:
        prompt_versions.append(f"critical:{norm_repo.version}")
        critical_ids = set(norm_repo.entries.keys())
        for unit in units:
            unit_findings = _filter_findings_for_unit(findings_list, unit)
            selected_cards = selected_by_unit.get(unit.unit_id, [])
            critical_cards = [card for card in selected_cards if card.norm_id in critical_ids]
            if not critical_cards:
                logger.info("LLM unit %s: no selected critical norms", unit.unit_name)
                continue
            unit_suggestions = _run_code_pass(
                unit=unit,
                unit_findings=unit_findings,
                norm_cards=critical_cards,
                norm_lookup=norm_repo.entries,
                api_key=api_key,
                diagnostics=diagnostics,
                prompt_version=f"critical:{norm_repo.version}",
                context_prefix="norm",
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
            if unit_suggestions:
                critical_suggestions.extend(unit_suggestions)

    # Остальные нормы (norms.yaml) — только если включено
    if units and general_repo and general_repo.cards:
        prompt_versions.append(f"norms:{general_repo.version}")
        general_ids = set(general_repo.entries.keys())
        for unit in units:
            unit_findings = _filter_findings_for_unit(findings_list, unit)
            selected_cards = selected_by_unit.get(unit.unit_id, [])
            general_cards = [card for card in selected_cards if card.norm_id in general_ids]
            if not general_cards:
                logger.info("LLM unit %s: no selected general norms", unit.unit_name)
                continue
            unit_suggestions = _run_code_pass(
                unit=unit,
                unit_findings=unit_findings,
                norm_cards=general_cards,
                norm_lookup=general_repo.entries,
                api_key=api_key,
                diagnostics=diagnostics,
                prompt_version=f"norms:{general_repo.version}",
                context_prefix="norms",
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
            if unit_suggestions:
                general_suggestions.extend(unit_suggestions)

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
                response_text = _call_llm(
                    prompt,
                    api_key,
                    system_prompt=QUERY_SYSTEM_PROMPT,
                    temperature=QUERY_TEMPERATURE,
                    provider=llm_provider,
                    model=llm_model,
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
                    query_suggestions.extend(unit_suggestions)
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
                    prompt_version=f"query:{query_norm_repo.version}",
                    unit_id=unit.unit_id,
                    unit_name=unit.unit_name,
                    redaction_report=redaction_report,
                )
            )

    merged_suggestions = _merge_suggestions(
        critical_suggestions=critical_suggestions,
        general_suggestions=general_suggestions,
        pattern_suggestions=pattern_suggestions,
        api_key=api_key,
        diagnostics=diagnostics,
        prompt_versions=prompt_versions,
    )
    all_suggestions.extend(merged_suggestions)
    if query_suggestions:
        all_suggestions.extend(query_suggestions)

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


def _call_llm(
    prompt: str,
    api_key: str,
    system_prompt: str = SYSTEM_PROMPT,
    temperature: float = 0,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> str | None:
    settings = get_settings()
    provider = (provider or settings.llm_provider or "deepseek").lower()
    base_url = settings.llm_api_base
    if provider == "openai" and "deepseek" in base_url:
        base_url = "https://api.openai.com"
    url = base_url.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": model or settings.llm_model,
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
            "LLM request failed (%s, %s): %s",
            provider,
            exc.response.status_code,
            body[:500] if body else "<empty>",
        )
        return None
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.warning("LLM request failed (%s): %s", provider, exc)
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


def _build_norm_selection_prompt(
    unit: CodeUnit,
    norm_cards: list[NormCard],
) -> tuple[str, dict]:
    code_block, redaction_report = _extract_relevant_code(unit)
    norms_text = _truncate_text(
        _format_norm_titles(norm_cards), MAX_NORM_SELECTION_CHARS, "нормы"
    )
    selection_prelude = (
        "Роль: ты классификатор применимости норм к фрагменту кода 1С.\n\n"
        "Правило применимости:\n"
        "- Норма \"применима\" (applicable=true) ТОЛЬКО если в данном фрагменте есть явный "
        "триггер/маркер, из-за которого эта норма может быть нарушена.\n"
        "- Если триггер не виден в коде напрямую — applicable=false.\n"
        "- Не угадывай контекст проекта и внешние вызовы, опирайся только на текст фрагмента.\n"
        "- Для applicable=true обязательно укажи evidence: 1) строку(и) кода (номера), 2) "
        "короткий маркер (1 фраза).\n\n"
        "Выход: строго JSON-массив объектов вида:\n"
        '[{ "norm_id": "...", "applicable": true/false, "evidence": "строки N-M: ..." }]\n\n'
        "Порядок: верни объекты в том же порядке, в котором нормы даны во входном списке."
    )
    prompt = textwrap.dedent(
        f"""
        {selection_prelude}

        Модуль: {unit.source_path}
        Единица анализа: {unit.unit_name} ({unit.unit_type}), строки {unit.start_line}–{unit.end_line}

        Код:
        ```
        {code_block}
        ```

        Список норм (id и название):
        {norms_text}

        Ответ: строго JSON-массив объектов по формату выше.
        """
    ).strip()
    redaction_report["phase"] = "select"
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


def _build_merge_prompt(
    critical_suggestions: list[AISuggestion],
    general_suggestions: list[AISuggestion],
    pattern_suggestions: list[AISuggestion],
) -> str:
    payload = {
        "critical": _suggestions_to_payload(critical_suggestions),
        "norms": _suggestions_to_payload(general_suggestions),
        "patterns": _suggestions_to_payload(pattern_suggestions),
    }
    prompt = textwrap.dedent(
        f"""
        Ниже три списка найденных нарушений. Объедини их в один итоговый список,
        удалив дубликаты. Если записи совпадают по norm_id и пересекающимся линиям,
        оставь наиболее подробную (с большим числом evidence или более точной reason).

        Входные данные (JSON):
        {json.dumps(payload, ensure_ascii=False, indent=2)}

        Ответ: строго JSON-массив объектов с полями
        norm_id, section, category, norm_text, source_reference, severity (optional),
        evidence (массив объектов с file, lines, reason).
        """
    ).strip()
    return prompt


def _suggestions_to_payload(suggestions: list[AISuggestion]) -> list[dict[str, Any]]:
    return [asdict(item) for item in suggestions]


def _parse_merge_response(response_text: str) -> list[AISuggestion]:
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError:
        logger.warning("LLM merge response is not valid JSON")
        return []
    if not isinstance(payload, list):
        logger.warning("LLM merge response is not a list")
        return []
    merged: list[AISuggestion] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        merged.append(
            AISuggestion(
                norm_id=item.get("norm_id"),
                section=item.get("section"),
                category=item.get("category"),
                severity=item.get("severity"),
                norm_text=item.get("norm_text") or "",
                source_reference=item.get("source_reference"),
                evidence=item.get("evidence"),
                llm_raw_response=None,
            )
        )
    return merged


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


def _run_code_pass(
    unit: CodeUnit,
    unit_findings: list[DetectorFinding],
    norm_cards: list[NormCard],
    norm_lookup: dict[str, dict],
    api_key: str,
    diagnostics: list[LLMDiagnostic],
    prompt_version: str,
    context_prefix: str,
    llm_provider: str,
    llm_model: str,
) -> list[AISuggestion]:
    allowed_norm_ids = {card.norm_id for card in norm_cards}
    prompt, redaction_report = _build_unit_prompt(unit, unit_findings, norm_cards)
    response_text = _call_llm(prompt, api_key, provider=llm_provider, model=llm_model)
    if not response_text:
        logger.warning("LLM unit %s: no response", unit.unit_name)
        return []
    unit_suggestions = _parse_response(
        response_text,
        unit_findings,
        unit,
        allowed_norm_ids,
        norm_lookup=norm_lookup,
    )
    if unit_suggestions:
        logger.info(
            "LLM unit %s: received %s suggestions",
            unit.unit_name,
            len(unit_suggestions),
        )
    else:
        logger.info("LLM unit %s: no additional suggestions", unit.unit_name)
    diagnostics.append(
        LLMDiagnostic(
            prompt=prompt,
            response=response_text,
            context_files=[f"{context_prefix}:{card.norm_id}" for card in norm_cards],
            source_paths=[unit.source_path],
            static_findings=json.loads(_serialize_findings(unit_findings)[0]),
            created_at=datetime.utcnow().isoformat(),
            prompt_version=prompt_version,
            unit_id=unit.unit_id,
            unit_name=unit.unit_name,
            redaction_report=redaction_report,
        )
    )
    return unit_suggestions


def _merge_suggestions(
    critical_suggestions: list[AISuggestion],
    general_suggestions: list[AISuggestion],
    pattern_suggestions: list[AISuggestion],
    api_key: str,
    diagnostics: list[LLMDiagnostic],
    prompt_versions: list[str],
) -> list[AISuggestion]:
    non_empty = [
        item
        for item in (critical_suggestions, general_suggestions, pattern_suggestions)
        if item
    ]
    if len(non_empty) <= 1:
        merged = []
        merged.extend(critical_suggestions)
        merged.extend(general_suggestions)
        merged.extend(pattern_suggestions)
        return merged

    prompt = _build_merge_prompt(
        critical_suggestions=critical_suggestions,
        general_suggestions=general_suggestions,
        pattern_suggestions=pattern_suggestions,
    )
    response_text = _call_llm(
        prompt,
        api_key,
        system_prompt=MERGE_SYSTEM_PROMPT,
        temperature=0,
        provider=llm_provider,
        model=llm_model,
    )
    if not response_text:
        logger.warning("LLM merge: no response, keeping raw suggestions")
        merged = []
        merged.extend(critical_suggestions)
        merged.extend(general_suggestions)
        merged.extend(pattern_suggestions)
        return merged
    merged = _parse_merge_response(response_text)
    if not merged:
        logger.warning("LLM merge returned empty; keeping raw suggestions")
        merged = []
        merged.extend(critical_suggestions)
        merged.extend(general_suggestions)
        merged.extend(pattern_suggestions)
    diagnostics.append(
        LLMDiagnostic(
            prompt=prompt,
            response=response_text,
            context_files=["merge:critical", "merge:norms", "merge:pattern"],
            source_paths=[],
            static_findings=[],
            created_at=datetime.utcnow().isoformat(),
            prompt_version="merge",
        )
    )
    prompt_versions.append("merge")
    return merged


def _format_norm_titles(norm_cards: list[NormCard]) -> str:
    lines = []
    for card in norm_cards:
        title = getattr(card, "title", None) or _extract_body_field(card.body, "Название") or card.norm_id
        section_value = getattr(card, "section", None) or _extract_body_field(card.body, "Раздел")
        section = f" [{section_value}]" if section_value else ""
        hint = _extract_body_field(card.body, "Подсказка детекта") or _extract_body_field(
            card.body, "Подсказка"
        )
        hint_text = ""
        if hint and hint != "—":
            hint_text = f" | маркеры: {hint}"
        lines.append(f"- {card.norm_id}: {title}{section}{hint_text}")
    return "\n".join(lines)


def _extract_body_field(body: str, label: str) -> str | None:
    prefix = f"{label}:"
    for line in body.splitlines():
        if line.startswith(prefix):
            value = line.split(":", 1)[1].strip()
            return value or None
    return None


def _select_norm_cards(
    unit: CodeUnit,
    norm_cards: list[NormCard],
    api_key: str,
    diagnostics: list[LLMDiagnostic],
    llm_provider: str,
    llm_model: str,
) -> list[NormCard]:
    if not norm_cards:
        return []
    midpoint = (len(norm_cards) + 1) // 2
    parts = [norm_cards[:midpoint], norm_cards[midpoint:]]
    combined_selected: set[str] = set()

    for idx, part in enumerate(parts, start=1):
        if not part:
            continue
        prompt, redaction_report = _build_norm_selection_prompt(unit, part)
        response_text = _call_llm(
            prompt,
            api_key,
            system_prompt=SELECTION_SYSTEM_PROMPT,
            temperature=0,
            provider=llm_provider,
            model=llm_model,
        )
        selected_ids = _parse_selected_norm_ids(response_text)
        if not selected_ids:
            logger.info("LLM norm selection returned empty for %s (part %s)", unit.unit_name, idx)
            diagnostics.append(
                LLMDiagnostic(
                    prompt=prompt,
                    response=response_text or "[]",
                    context_files=[f"norm:{card.norm_id}" for card in part],
                    source_paths=[unit.source_path],
                    static_findings=[],
                    created_at=datetime.utcnow().isoformat(),
                    prompt_version=f"select:part{idx}",
                    unit_id=unit.unit_id,
                    unit_name=unit.unit_name,
                    redaction_report=redaction_report,
                )
            )
            continue
        combined_selected.update(selected_ids)
        diagnostics.append(
            LLMDiagnostic(
                prompt=prompt,
                response=response_text or "[]",
                context_files=[f"norm:{card.norm_id}" for card in part],
                source_paths=[unit.source_path],
                static_findings=[],
                created_at=datetime.utcnow().isoformat(),
                prompt_version=f"select:part{idx}",
                unit_id=unit.unit_id,
                unit_name=unit.unit_name,
                redaction_report=redaction_report,
            )
        )

    if not combined_selected:
        return []
    selected = [card for card in norm_cards if card.norm_id in combined_selected]
    return selected


def _extract_selection_runs(config: dict) -> int:
    try:
        value = int(config.get("selection_runs", 5))
    except (TypeError, ValueError):
        value = 5
    return max(2, min(20, value))


def _evaluate_selection_stability(
    units: list[CodeUnit],
    norm_cards: list[NormCard],
    api_key: str,
    diagnostics: list[LLMDiagnostic],
    selection_runs: int,
    llm_provider: str,
    llm_model: str,
    *,
    label: str,
    prefilter: bool = False,
) -> dict[str, Any]:
    unit_reports: list[dict[str, Any]] = []
    jaccards: list[float] = []
    for unit in units:
        sets: list[set[str]] = []
        candidate_cards = norm_cards
        prefilter_stats = None
        if prefilter:
            candidate_cards = _prefilter_norm_cards(unit, norm_cards)
            prefilter_stats = {
                "candidate_count": len(norm_cards),
                "filtered_count": len(candidate_cards),
            }
        for _ in range(selection_runs):
            if not candidate_cards:
                selected = []
            else:
                selected = _select_norm_cards(
                    unit,
                    candidate_cards,
                    api_key,
                    diagnostics,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                )
            sets.append(set(card.norm_id for card in selected))
        avg_jaccard = _average_pairwise_jaccard(sets)
        union_all = set().union(*sets) if sets else set()
        intersection_all = set(sets[0]) if sets else set()
        for s in sets[1:]:
            intersection_all &= s
        report_entry = {
            "unit_id": unit.unit_id,
            "unit_name": unit.unit_name,
            "runs": [sorted(list(s)) for s in sets],
            "avg_jaccard": avg_jaccard,
            "union_size": len(union_all),
            "intersection_size": len(intersection_all),
            "counts": [len(s) for s in sets],
        }
        if prefilter_stats:
            report_entry["prefilter"] = prefilter_stats
        unit_reports.append(report_entry)
        jaccards.append(avg_jaccard)
    overall = {
        "avg_jaccard": sum(jaccards) / len(jaccards) if jaccards else 1.0,
        "units": len(units),
        "selection_runs": selection_runs,
    }
    return {"label": label, "overall": overall, "units": unit_reports}


def _evaluate_selection_compare(
    units: list[CodeUnit],
    norm_cards: list[NormCard],
    api_key: str,
    diagnostics: list[LLMDiagnostic],
    selection_runs: int,
    llm_provider: str,
    llm_model: str,
) -> dict[str, Any]:
    baseline = _evaluate_selection_stability(
        units=units,
        norm_cards=norm_cards,
        api_key=api_key,
        diagnostics=diagnostics,
        selection_runs=selection_runs,
        llm_provider=llm_provider,
        llm_model=llm_model,
        label="baseline",
        prefilter=False,
    )
    prefiltered = _evaluate_selection_stability(
        units=units,
        norm_cards=norm_cards,
        api_key=api_key,
        diagnostics=diagnostics,
        selection_runs=selection_runs,
        llm_provider=llm_provider,
        llm_model=llm_model,
        label="prefiltered",
        prefilter=True,
    )
    return {"baseline": baseline, "prefiltered": prefiltered}


def _average_pairwise_jaccard(sets: list[set[str]]) -> float:
    if len(sets) <= 1:
        return 1.0
    total = 0.0
    count = 0
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            a, b = sets[i], sets[j]
            union = a | b
            if not union:
                score = 1.0
            else:
                score = len(a & b) / len(union)
            total += score
            count += 1
    return total / count if count else 1.0


def _parse_selected_norm_ids(response_text: str | None) -> list[str]:
    if not response_text:
        return []
    text = response_text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            return []
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
    if not isinstance(data, list):
        return []
    results: list[str] = []
    for item in data:
        if isinstance(item, str):
            value = item.strip()
            if value:
                results.append(value)
            continue
        if isinstance(item, dict):
            norm_id = item.get("norm_id")
            applicable = item.get("applicable")
            if applicable is True and isinstance(norm_id, str) and norm_id.strip():
                results.append(norm_id.strip())
    return results


def _prefilter_norm_cards(unit: CodeUnit, norm_cards: list[NormCard]) -> list[NormCard]:
    if not norm_cards:
        return []
    code_tokens = set(_tokenize_text(unit.text))
    scored: list[tuple[tuple[int, int], NormCard]] = []
    for card in norm_cards:
        hint_tokens = _extract_detection_hint_tokens(card.body)
        hint_match = any(token in code_tokens for token in hint_tokens)
        overlap = len(card.tokens & code_tokens) if card.tokens else 0
        if not hint_match and overlap == 0:
            continue
        score = (2 if hint_match else 0, overlap)
        scored.append((score, card))
    if not scored:
        return []
    scored.sort(key=lambda item: (-item[0][0], -item[0][1], item[1].norm_id))
    return [card for _, card in scored[:PREFILTER_MAX_CARDS]]


def _extract_detection_hint_tokens(body: str) -> list[str]:
    hint = _extract_body_field(body, "Подсказка детекта") or _extract_body_field(body, "Подсказка")
    if not hint:
        return []
    return _tokenize_text(hint)


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
def _load_api_key(provider: str) -> str | None:
    provider = (provider or "deepseek").lower()
    if provider == "openai":
        key = os.getenv("OPENAI_APIKEY") or os.getenv("OPENAI_API_KEY")
        if key:
            return key
    else:
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
            name = name.strip()
            if provider == "openai" and name in {"OPENAI_APIKEY", "OPENAI_API_KEY"}:
                key = value.strip()
                os.environ[name] = key
                return key
            if provider != "openai" and name == "DEEPSEEK_API_KEY":
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


def _redact_comments(lines: list[str], start_line: int) -> tuple[list[str], CommentRedactionStats]:
    redacted: list[str] = []
    comments_by_line: dict[int, int] = {}
    in_block_comment = False
    for idx, raw in enumerate(lines):
        line_no = start_line + idx
        i = 0
        in_string = False
        comment_count = 0
        out: list[str] = []
        while i < len(raw):
            ch = raw[i]
            nxt = raw[i + 1] if i + 1 < len(raw) else ""
            if in_block_comment:
                out.append("<REDACTED_COMMENT>")
                comment_count += 1
                end_idx = raw.find("*/", i)
                if end_idx != -1:
                    out.append("*/")
                    i = end_idx + 2
                    in_block_comment = False
                    continue
                i = len(raw)
                continue
            if in_string:
                if ch == '"' and nxt == '"':
                    out.append('"')
                    out.append('"')
                    i += 2
                    continue
                if ch == '"':
                    in_string = False
                    out.append(ch)
                    i += 1
                    continue
                out.append(ch)
                i += 1
                continue
            if ch == "/" and nxt == "/":
                out.append("//")
                out.append("<REDACTED_COMMENT>")
                comment_count += 1
                i = len(raw)
                continue
            if ch == "/" and nxt == "*":
                out.append("/*")
                out.append("<REDACTED_COMMENT>")
                comment_count += 1
                end_idx = raw.find("*/", i + 2)
                if end_idx != -1:
                    out.append("*/")
                    i = end_idx + 2
                    continue
                in_block_comment = True
                i = len(raw)
                continue
            if ch == '"':
                in_string = True
                out.append(ch)
                i += 1
                continue
            out.append(ch)
            i += 1
        if comment_count:
            comments_by_line[line_no] = comment_count
        redacted.append("".join(out))
    return redacted, CommentRedactionStats(
        total_comments=sum(comments_by_line.values()),
        lines_with_comments=sorted(comments_by_line),
        comments_by_line=comments_by_line,
    )


def _redact_comments_line_map(
    line_map: list[tuple[int, str]],
) -> tuple[list[tuple[int, str]], CommentRedactionStats]:
    redacted_lines: list[tuple[int, str]] = []
    comments_by_line: dict[int, int] = {}
    in_block_comment = False
    for line_no, raw in line_map:
        i = 0
        in_string = False
        comment_count = 0
        out: list[str] = []
        while i < len(raw):
            ch = raw[i]
            nxt = raw[i + 1] if i + 1 < len(raw) else ""
            if in_block_comment:
                out.append("<REDACTED_COMMENT>")
                comment_count += 1
                end_idx = raw.find("*/", i)
                if end_idx != -1:
                    out.append("*/")
                    i = end_idx + 2
                    in_block_comment = False
                    continue
                i = len(raw)
                continue
            if in_string:
                if ch == '"' and nxt == '"':
                    out.append('"')
                    out.append('"')
                    i += 2
                    continue
                if ch == '"':
                    in_string = False
                    out.append(ch)
                    i += 1
                    continue
                out.append(ch)
                i += 1
                continue
            if ch == "/" and nxt == "/":
                out.append("//")
                out.append("<REDACTED_COMMENT>")
                comment_count += 1
                i = len(raw)
                continue
            if ch == "/" and nxt == "*":
                out.append("/*")
                out.append("<REDACTED_COMMENT>")
                comment_count += 1
                end_idx = raw.find("*/", i + 2)
                if end_idx != -1:
                    out.append("*/")
                    i = end_idx + 2
                    continue
                in_block_comment = True
                i = len(raw)
                continue
            if ch == '"':
                in_string = True
                out.append(ch)
                i += 1
                continue
            out.append(ch)
            i += 1
        if comment_count:
            comments_by_line[line_no] = comment_count
        redacted_lines.append((line_no, "".join(out)))
    return redacted_lines, CommentRedactionStats(
        total_comments=sum(comments_by_line.values()),
        lines_with_comments=sorted(comments_by_line),
        comments_by_line=comments_by_line,
    )


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


def _filter_comment_stats(
    stats: CommentRedactionStats,
    included_lines: set[int],
) -> CommentRedactionStats:
    if not included_lines:
        return stats
    comments_by_line = {
        line_no: count
        for line_no, count in stats.comments_by_line.items()
        if line_no in included_lines
    }
    return CommentRedactionStats(
        total_comments=sum(comments_by_line.values()),
        lines_with_comments=sorted(comments_by_line),
        comments_by_line=comments_by_line,
    )


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
    comment_redacted_lines, comment_stats = _redact_comments(lines, unit.start_line)
    redacted_lines, stats = redact_lines(comment_redacted_lines, unit.start_line)
    if not unit.review_ranges:
        numbered = [
            f"{unit.start_line + idx:>5}: {line}" for idx, line in enumerate(redacted_lines)
        ]
        report = _base_redaction_report(unit, stats)
        report.update(
            {
                "redacted_comments": comment_stats.total_comments,
                "comment_lines": comment_stats.lines_with_comments,
                "comments_by_line": comment_stats.comments_by_line,
            }
        )
        return (
            _truncate_text("\n".join(numbered), MAX_UNIT_CODE_CHARS, "фрагмент кода"),
            report,
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
    filtered_comment_stats = _filter_comment_stats(comment_stats, included_lines)
    report = _filter_redaction_report(unit, stats, included_lines)
    report.update(
        {
            "redacted_comments": filtered_comment_stats.total_comments,
            "comment_lines": filtered_comment_stats.lines_with_comments,
            "comments_by_line": filtered_comment_stats.comments_by_line,
        }
    )
    return (
        _truncate_text("\n".join(snippet), MAX_UNIT_CODE_CHARS, "фрагмент кода"),
        report,
    )


def _format_query_lines(unit: QueryUnit) -> tuple[str, dict]:
    comment_redacted, comment_stats = _redact_comments_line_map(unit.line_map)
    redacted_lines, stats = redact_lines([line for _, line in comment_redacted], unit.start_line)
    numbered = [
        f"{line_no:>5}: {line}"
        for (line_no, _), line in zip(comment_redacted, redacted_lines)
    ]
    included_lines = {line_no for line_no, _ in unit.line_map}
    filtered_comment_stats = _filter_comment_stats(comment_stats, included_lines)
    report = _filter_redaction_report(unit, stats, included_lines)
    report.update(
        {
            "redacted_comments": filtered_comment_stats.total_comments,
            "comment_lines": filtered_comment_stats.lines_with_comments,
            "comments_by_line": filtered_comment_stats.comments_by_line,
        }
    )
    return (
        _truncate_text("\n".join(numbered), MAX_QUERY_TEXT_CHARS, "текст запроса"),
        report,
    )
