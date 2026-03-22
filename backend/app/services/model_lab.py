from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.models.ai_finding import AIFinding
from backend.app.models.enums import ReviewStatus
from backend.app.models.model_lab import ModelLabCase, ModelLabJudgement, ModelLabSession
from backend.app.models.open_world_candidate import OpenWorldCandidate
from backend.app.models.review_run import ReviewRun
from backend.app.models.user import UserAccount
from backend.app.schemas.model_lab import (
    ModelLabCaseRead,
    ModelLabEvaluateRequest,
    ModelLabJudgementRead,
    ModelLabLeaderboardRow,
    ModelLabSessionCreate,
    ModelLabSessionDetail,
    ModelLabSessionRead,
    ModelOption,
)
from backend.app.services import artifacts as artifact_service
from backend.app.services.model_lab_llm import chat_completion
from backend.app.services.model_lab_secrets import drop_secret, put_secret

EVALUATION_SYSTEM_PROMPT = (
    "Ты независимый эксперт по code review 1С. "
    "Тебе дают набор замечаний модели по одному запуску. "
    "Оцени качество набора строго по критериям и верни JSON. "
    "Шкала критериев: 0..100, где 100 — отлично. "
    "Не добавляй пояснений вне JSON."
)


def ensure_model_lab_enabled() -> None:
    settings = get_settings()
    if not settings.model_lab_enabled:
        raise RuntimeError("Model Lab disabled by configuration")


def create_session(
    db: Session,
    *,
    payload: ModelLabSessionCreate,
    current_admin: UserAccount,
) -> ModelLabSession:
    settings = get_settings()
    ensure_model_lab_enabled()
    if len(payload.internal_models) > settings.model_lab_max_models:
        raise ValueError(f"Too many internal models: max {settings.model_lab_max_models}")
    if payload.sample_size > settings.model_lab_max_sample_size:
        raise ValueError(f"sample_size limit exceeded: max {settings.model_lab_max_sample_size}")

    source_runs = _select_source_runs(db, payload.sample_size)
    if not source_runs:
        raise ValueError("No completed review runs with source artifacts found")

    target_models: list[dict[str, str]] = []
    for model in payload.internal_models:
        cleaned = model.strip()
        if cleaned:
            target_models.append({"provider": "internal", "model": cleaned})
    for item in payload.baseline_models:
        if item.provider in {"deepseek", "openai"} and item.model.strip():
            target_models.append({"provider": item.provider, "model": item.model.strip()})
    target_models = _dedupe_model_entries(target_models)
    if not target_models:
        raise ValueError("No target models selected")
    if len(target_models) > settings.model_lab_max_models:
        raise ValueError(f"Too many target models: max {settings.model_lab_max_models}")

    paid_target_models = [item for item in target_models if _is_paid_provider(str(item.get("provider")))]
    if len(paid_target_models) > settings.model_lab_max_paid_target_models:
        raise ValueError(
            "Too many paid baseline models: "
            f"max {settings.model_lab_max_paid_target_models}"
        )
    estimated_paid_target_runs = payload.sample_size * len(paid_target_models)
    if estimated_paid_target_runs > settings.model_lab_max_paid_target_runs:
        raise ValueError(
            "Paid baseline limit exceeded: "
            f"{estimated_paid_target_runs} > {settings.model_lab_max_paid_target_runs} "
            "(sample_size * paid_target_models)"
        )

    expert_models = [
        {"provider": item.provider, "model": item.model.strip()}
        for item in payload.expert_models
        if item.provider in {"deepseek", "openai"} and item.model.strip()
    ]
    expert_models = _dedupe_model_entries(expert_models)
    if not expert_models:
        raise ValueError("At least one expert model is required")
    if len(expert_models) > settings.model_lab_max_expert_models:
        raise ValueError(f"Too many expert models: max {settings.model_lab_max_expert_models}")
    estimated_expert_calls = payload.sample_size * len(target_models) * len(expert_models)
    if estimated_expert_calls > settings.model_lab_max_expert_calls:
        raise ValueError(
            "Expert evaluation limit exceeded: "
            f"{estimated_expert_calls} > {settings.model_lab_max_expert_calls} "
            "(sample_size * target_models * expert_models)"
        )

    secret_ref = put_secret(payload.api_key, ttl_seconds=settings.model_lab_secret_ttl_seconds)
    session = ModelLabSession(
        id=uuid.uuid4(),
        created_by=current_admin.id,
        title=(payload.title or "").strip() or None,
        status="running",
        target_models=target_models,
        expert_models=expert_models,
        settings={
            "include_open_world": payload.include_open_world,
            "use_all_norms": payload.use_all_norms,
            "disable_patterns": payload.disable_patterns,
        },
        internal_api_base=payload.api_base.strip().rstrip("/"),
        internal_secret_ref=secret_ref,
        sample_size=payload.sample_size,
        started_at=datetime.utcnow(),
    )
    db.add(session)
    db.flush()

    for source_run in source_runs:
        source_artifact = _extract_source_artifact(source_run)
        for target in target_models:
            case_id = uuid.uuid4()
            review_run_id = uuid.uuid4()
            provider = target["provider"]
            model = target["model"]

            worker_override: dict[str, Any] = {
                "llm_provider": "openai" if provider in {"internal", "openai"} else "deepseek",
                "llm_model": model,
                "use_all_norms": payload.use_all_norms,
                "disable_patterns": payload.disable_patterns,
                "open_world_use_chatgpt": False,
            }
            if provider == "internal":
                worker_override["llm_api_base"] = payload.api_base.strip().rstrip("/")
                worker_override["llm_api_key_ref"] = secret_ref

            clone_context = {
                "source_artifact": source_artifact,
                "change_ranges": (source_run.context or {}).get("change_ranges") or {},
                "model_lab_session_id": str(session.id),
                "model_lab_case_id": str(case_id),
                "worker_settings_override": worker_override,
            }

            review_run = ReviewRun(
                id=review_run_id,
                user_id=current_admin.id,
                project_id=source_run.project_id,
                external_ref=f"model-lab:{session.id}:{case_id}",
                status=ReviewStatus.QUEUED,
                cost_points=0,
                context=clone_context,
            )
            db.add(review_run)
            # Ensure ReviewRun rows exist before ModelLabCase FK inserts.
            db.flush()

            case = ModelLabCase(
                id=case_id,
                session_id=session.id,
                source_run_id=source_run.id,
                review_run_id=review_run_id,
                target_provider=provider,
                target_model=model,
                status="queued",
            )
            db.add(case)

    db.commit()
    db.refresh(session)
    return session


def list_sessions(db: Session, *, created_by: uuid.UUID | None = None, limit: int = 100) -> list[ModelLabSession]:
    query = db.query(ModelLabSession).order_by(ModelLabSession.created_at.desc())
    if created_by:
        query = query.filter(ModelLabSession.created_by == created_by)
    return query.limit(limit).all()


def get_session_detail(db: Session, session_id: uuid.UUID) -> ModelLabSessionDetail:
    session = db.get(ModelLabSession, session_id)
    if not session:
        raise ValueError("Model Lab session not found")
    cases = (
        db.query(ModelLabCase)
        .filter(ModelLabCase.session_id == session_id)
        .order_by(ModelLabCase.created_at.asc())
        .all()
    )
    case_ids = [item.id for item in cases]
    judgements: list[ModelLabJudgement] = []
    if case_ids:
        judgements = (
            db.query(ModelLabJudgement)
            .filter(ModelLabJudgement.case_id.in_(case_ids))
            .order_by(ModelLabJudgement.created_at.asc())
            .all()
        )
    return ModelLabSessionDetail(
        session=ModelLabSessionRead.model_validate(session),
        cases=[ModelLabCaseRead.model_validate(item) for item in cases],
        judgements=[ModelLabJudgementRead.model_validate(item) for item in judgements],
        leaderboard=_build_leaderboard(cases),
    )


def mark_case_started(db: Session, review_run: ReviewRun) -> None:
    ctx = review_run.context or {}
    case_id = ctx.get("model_lab_case_id")
    if not case_id:
        return
    case = db.get(ModelLabCase, uuid.UUID(str(case_id)))
    if not case or case.status not in {"queued", "running"}:
        return
    case.status = "running"
    case.started_at = case.started_at or datetime.utcnow()
    db.add(case)
    db.commit()


def handle_case_result(
    db: Session,
    *,
    review_run: ReviewRun,
    findings_count: int,
    ai_findings_count: int,
    open_world_count: int,
    duration_ms: int,
) -> None:
    ctx = review_run.context or {}
    case_id = ctx.get("model_lab_case_id")
    session_id = ctx.get("model_lab_session_id")
    if not case_id or not session_id:
        return

    case = db.get(ModelLabCase, uuid.UUID(str(case_id)))
    if not case:
        return
    case.status = "completed" if review_run.status == ReviewStatus.COMPLETED else "failed"
    case.duration_ms = duration_ms
    case.findings_count = findings_count
    case.ai_findings_count = ai_findings_count
    case.open_world_count = open_world_count
    case.finished_at = datetime.utcnow()
    db.add(case)
    db.flush()

    session = db.get(ModelLabSession, uuid.UUID(str(session_id)))
    if session:
        session_cases = db.query(ModelLabCase).filter(ModelLabCase.session_id == session.id).all()
        if session_cases and all(item.status in {"completed", "failed"} for item in session_cases):
            completed = [item for item in session_cases if item.status == "completed"]
            session.status = "ready_for_evaluation" if completed else "failed"
            session.finished_at = datetime.utcnow()
            if not completed:
                session.error_message = "All benchmark cases failed"
            db.add(session)
    db.commit()


def evaluate_session(
    db: Session,
    *,
    session_id: uuid.UUID,
    payload: ModelLabEvaluateRequest,
) -> ModelLabSessionDetail:
    settings = get_settings()
    ensure_model_lab_enabled()
    session = db.get(ModelLabSession, session_id)
    if not session:
        raise ValueError("Model Lab session not found")

    cases = db.query(ModelLabCase).filter(ModelLabCase.session_id == session_id).all()
    completed_cases = [item for item in cases if item.status == "completed"]
    if not completed_cases:
        raise ValueError("No completed cases for evaluation")

    experts: list[ModelOption]
    if payload.experts:
        experts = payload.experts
    else:
        experts = [
            ModelOption(provider=str(item.get("provider")), model=str(item.get("model")))
            for item in (session.expert_models or [])
            if isinstance(item, dict)
        ]
    if not experts:
        raise ValueError("No expert models configured")
    if len(experts) > settings.model_lab_max_expert_models:
        raise ValueError(f"Too many expert models: max {settings.model_lab_max_expert_models}")
    estimated_calls = len(completed_cases) * len(experts)
    if estimated_calls > settings.model_lab_max_expert_calls:
        raise ValueError(
            "Expert evaluation limit exceeded for current session: "
            f"{estimated_calls} > {settings.model_lab_max_expert_calls}"
        )

    session.status = "evaluating"
    session.error_message = None
    db.add(session)
    db.commit()

    try:
        for case in completed_cases:
            ai_rows = (
                db.query(AIFinding)
                .filter(AIFinding.review_run_id == case.review_run_id)
                .order_by(AIFinding.created_at.asc())
                .all()
            )
            include_open_world = bool((session.settings or {}).get("include_open_world"))
            open_world_rows: list[OpenWorldCandidate] = []
            if include_open_world:
                open_world_rows = (
                    db.query(OpenWorldCandidate)
                    .filter(OpenWorldCandidate.review_run_id == case.review_run_id)
                    .order_by(OpenWorldCandidate.created_at.asc())
                    .all()
                )
            source_map = _load_source_map(db, case.review_run_id)
            user_prompt = _build_expert_prompt(case, ai_rows, open_world_rows, source_map)

            db.query(ModelLabJudgement).filter(ModelLabJudgement.case_id == case.id).delete(
                synchronize_session=False
            )
            db.flush()

            weighted_scores: list[tuple[float, float, str]] = []
            summaries: list[str] = []
            for expert in experts:
                api_base, api_key = _resolve_expert_credentials(expert.provider, settings)
                result = chat_completion(
                    api_base=api_base,
                    api_key=api_key,
                    model=expert.model,
                    system_prompt=EVALUATION_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    timeout_seconds=settings.llm_timeout_seconds,
                    temperature=None,
                )
                parsed = _parse_expert_response(result.content)
                judgement = ModelLabJudgement(
                    case_id=case.id,
                    expert_provider=expert.provider,
                    expert_model=expert.model,
                    overall_score=parsed["overall_score"],
                    criteria=parsed.get("criteria"),
                    summary=parsed.get("summary"),
                    raw_response={"content": result.content, "payload": result.raw},
                )
                db.add(judgement)
                bias_weight = 0.3 if case.target_provider == expert.provider else 1.0
                weighted_scores.append((parsed["overall_score"], bias_weight, expert.provider))
                if parsed.get("summary"):
                    summaries.append(str(parsed["summary"]))

            if weighted_scores:
                total_weight = sum(item[1] for item in weighted_scores) or 1.0
                score = sum(score * weight for score, weight, _ in weighted_scores) / total_weight
                case.score_overall = round(float(score), 2)
            else:
                case.score_overall = None
            if summaries:
                case.score_summary = " | ".join(summaries[:2])
            db.add(case)
            db.commit()

        session.status = "evaluated"
        session.finished_at = datetime.utcnow()
        db.add(session)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        session.status = "failed"
        session.error_message = str(exc)
        db.add(session)
        db.commit()
        raise
    finally:
        if session.status in {"evaluated", "failed", "ready_for_evaluation"}:
            drop_secret(session.internal_secret_ref)

    return get_session_detail(db, session_id)


def _extract_source_artifact(review_run: ReviewRun) -> str:
    ctx = review_run.context or {}
    source_artifact = ctx.get("source_artifact")
    if not isinstance(source_artifact, str) or not source_artifact.strip():
        raise ValueError(f"Run {review_run.id} has no source_artifact")
    return source_artifact


def _select_source_runs(db: Session, sample_size: int) -> list[ReviewRun]:
    query = (
        db.query(ReviewRun)
        .filter(ReviewRun.status == ReviewStatus.COMPLETED)
        .order_by(ReviewRun.finished_at.desc().nullslast(), ReviewRun.queued_at.desc())
    )
    rows = query.limit(max(sample_size * 5, sample_size)).all()
    selected: list[ReviewRun] = []
    for row in rows:
        if not row.context:
            continue
        if "source_artifact" not in row.context:
            continue
        if row.context.get("evaluation_of"):
            continue
        if row.context.get("model_lab_case_id"):
            continue
        selected.append(row)
        if len(selected) >= sample_size:
            break
    return selected


def _resolve_expert_credentials(provider: str, settings) -> tuple[str, str]:
    provider_l = provider.lower()
    if provider_l == "deepseek":
        import os

        key = os.getenv("DEEPSEEK_API_KEY")
        if not key:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured")
        return settings.llm_api_base.rstrip("/"), key
    if provider_l == "openai":
        import os

        key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_APIKEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY / OPENAI_APIKEY is not configured")
        return settings.openai_api_base.rstrip("/"), key
    raise RuntimeError(f"Unsupported expert provider: {provider}")


def _build_expert_prompt(
    case: ModelLabCase,
    ai_rows: list[AIFinding],
    open_world_rows: list[OpenWorldCandidate],
    source_map: dict[str, list[str]],
) -> str:
    findings_payload: list[dict[str, Any]] = []
    for row in ai_rows:
        evidence = row.evidence if isinstance(row.evidence, list) else []
        findings_payload.append(
            {
                "kind": "known_norm",
                "norm_id": row.norm_id,
                "severity": row.severity,
                "norm_text": row.norm_text,
                "evidence": evidence,
                "snippets": _extract_snippets(source_map, evidence),
            }
        )
    for row in open_world_rows:
        evidence = row.evidence if isinstance(row.evidence, list) else []
        findings_payload.append(
            {
                "kind": "open_world",
                "title": row.title,
                "severity": row.severity,
                "norm_text": row.norm_text or row.description,
                "evidence": evidence,
                "snippets": _extract_snippets(source_map, evidence),
            }
        )

    return (
        "Оцени результат code-review модели.\n"
        f"Провайдер модели: {case.target_provider}\n"
        f"Модель: {case.target_model}\n"
        f"Количество замечаний: {len(findings_payload)}\n\n"
        "Критерии (0..100): groundedness, norm_accuracy, evidence_quality, actionability, "
        "coverage, noise, severity_calibration.\n"
        "Верни JSON объекта:\n"
        "{\n"
        '  "overall_score": 0,\n'
        '  "criteria": {\n'
        '    "groundedness": 0,\n'
        '    "norm_accuracy": 0,\n'
        '    "evidence_quality": 0,\n'
        '    "actionability": 0,\n'
        '    "coverage": 0,\n'
        '    "noise": 0,\n'
        '    "severity_calibration": 0\n'
        "  },\n"
        '  "summary": "краткий вывод"\n'
        "}\n\n"
        f"Замечания модели:\n{json.dumps(findings_payload, ensure_ascii=False, indent=2)}"
    )


def _extract_snippets(source_map: dict[str, list[str]], evidence: list[dict]) -> list[dict[str, Any]]:
    snippets: list[dict[str, Any]] = []
    for item in evidence[:4]:
        if not isinstance(item, dict):
            continue
        file_path = str(item.get("file") or "").strip()
        lines = str(item.get("lines") or "").strip()
        if not file_path or not lines:
            continue
        line_start, line_end = _parse_line_range(lines)
        if line_start is None:
            continue
        source_lines = source_map.get(file_path)
        if not source_lines:
            continue
        start_idx = max(line_start - 1, 0)
        end_idx = min(line_end, len(source_lines))
        if start_idx >= end_idx:
            continue
        chunk = []
        for idx in range(start_idx, end_idx):
            chunk.append(f"{idx + 1}: {source_lines[idx]}")
        snippets.append({"file": file_path, "lines": lines, "code": "\n".join(chunk)})
    return snippets


def _parse_line_range(value: str) -> tuple[int | None, int]:
    if not value:
        return None, 0
    marker = value.rsplit(":", 1)[-1]
    nums = [int(part) for part in marker.replace(" ", "").split("-") if part.isdigit()]
    if not nums:
        nums = [int(num) for num in re.findall(r"\d+", marker)]
    if not nums:
        return None, 0
    start = nums[0]
    end = nums[1] if len(nums) > 1 else nums[0]
    if end < start:
        end = start
    return start, end


def _load_source_map(db: Session, review_run_id: uuid.UUID) -> dict[str, list[str]]:
    run = db.get(ReviewRun, review_run_id)
    if not run:
        return {}
    artifact_path = _extract_source_artifact(run)
    sources = artifact_service.load_sources(artifact_path)
    result: dict[str, list[str]] = {}
    for source in sources:
        path = source.get("path")
        content = source.get("content")
        if isinstance(path, str) and isinstance(content, str):
            result[path] = content.splitlines()
    return result


def _parse_expert_response(text: str) -> dict[str, Any]:
    parsed = _extract_json_object(text)
    if not isinstance(parsed, dict):
        raise RuntimeError("Expert response is not valid JSON object")
    overall = _coerce_score(parsed.get("overall_score"))
    criteria = parsed.get("criteria")
    normalized_criteria: dict[str, float] = {}
    if isinstance(criteria, dict):
        for key, value in criteria.items():
            normalized_criteria[str(key)] = _coerce_score(value)
    summary = str(parsed.get("summary") or "").strip() or None
    return {"overall_score": overall, "criteria": normalized_criteria, "summary": summary}


def _extract_json_object(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    snippet = cleaned[start : end + 1]
    try:
        data = json.loads(snippet)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _coerce_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = 0.0
    if score < 0:
        return 0.0
    if score > 100:
        return 100.0
    return score


def _build_leaderboard(cases: list[ModelLabCase]) -> list[ModelLabLeaderboardRow]:
    grouped: dict[tuple[str, str], list[float]] = {}
    for case in cases:
        if case.score_overall is None:
            continue
        key = (case.target_provider, case.target_model)
        grouped.setdefault(key, []).append(float(case.score_overall))
    rows: list[ModelLabLeaderboardRow] = []
    for (provider, model), scores in grouped.items():
        rows.append(
            ModelLabLeaderboardRow(
                provider=provider,
                model=model,
                cases=len(scores),
                avg_score=round(mean(scores), 2),
            )
        )
    rows.sort(key=lambda item: (-item.avg_score, item.provider, item.model))
    return rows


def _is_paid_provider(provider: str) -> bool:
    return provider.lower() in {"deepseek", "openai"}


def _dedupe_model_entries(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        provider = str(row.get("provider") or "").strip().lower()
        model = str(row.get("model") or "").strip()
        if not provider or not model:
            continue
        key = (provider, model)
        if key in seen:
            continue
        seen.add(key)
        result.append({"provider": provider, "model": model})
    return result
