from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.app.api.deps import get_current_admin
from backend.app.core.config import get_settings
from backend.app.models.user import UserAccount
from backend.app.schemas.llm import LLMPlaygroundRequest, LLMPlaygroundResponse
from backend.app.services.llm_playground import LLMPlaygroundError, request_llm_playground

router = APIRouter(prefix="/admin/llm", tags=["admin"])


@router.post("/playground", response_model=LLMPlaygroundResponse)
def run_llm_playground(
    payload: LLMPlaygroundRequest,
    current_admin: UserAccount = Depends(get_current_admin),
) -> LLMPlaygroundResponse:
    settings = get_settings()
    model_override = payload.model.strip() if payload.model else None
    model_name = model_override or (
        settings.llm_reasoning_model if payload.use_reasoning else settings.llm_model
    )
    if not model_name:
        raise HTTPException(status_code=400, detail="LLM model is not configured")

    try:
        result = request_llm_playground(
            system_prompt=payload.system_prompt,
            user_prompt=payload.user_prompt,
            temperature=payload.temperature,
            model=model_name,
        )
    except LLMPlaygroundError as exc:
        detail: dict[str, object] = {"message": str(exc)}
        if exc.request_info:
            detail["request"] = {
                "api_base": exc.request_info.api_base,
                "endpoint": exc.request_info.endpoint,
                "timeout_seconds": exc.request_info.timeout_seconds,
                "model": exc.request_info.model,
                "temperature": exc.request_info.temperature,
                "use_reasoning": payload.use_reasoning,
                "model_override": payload.model,
                "request_headers": exc.request_info.request_headers,
                "request_payload": exc.request_info.request_payload,
            }
        raise HTTPException(status_code=400, detail=detail) from exc

    return LLMPlaygroundResponse(
        model=result.model,
        response=result.response,
        api_base=result.api_base,
        endpoint=result.endpoint,
        timeout_seconds=result.timeout_seconds,
        temperature=payload.temperature,
        use_reasoning=payload.use_reasoning,
        model_override=payload.model,
        request_headers=result.request_headers,
        request_payload=result.request_payload,
    )
