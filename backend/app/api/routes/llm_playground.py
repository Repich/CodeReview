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
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return LLMPlaygroundResponse(model=result.model, response=result.response)
