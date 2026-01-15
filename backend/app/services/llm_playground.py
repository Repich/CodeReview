from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import httpx

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMPlaygroundError(RuntimeError):
    pass


@dataclass
class LLMPlaygroundResult:
    model: str
    response: str


def request_llm_playground(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    model: str,
) -> LLMPlaygroundResult:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise LLMPlaygroundError("DEEPSEEK_API_KEY is not configured")

    settings = get_settings()
    url = settings.llm_api_base.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
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
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "LLM playground request failed (%s): %s",
            exc.response.status_code,
            exc.response.text[:500] if exc.response.text else "<empty>",
        )
        raise LLMPlaygroundError("LLM request failed") from exc
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.warning("LLM playground request failed: %s", exc)
        raise LLMPlaygroundError("LLM request failed") from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("LLM playground response parse failed: %s", exc)
        raise LLMPlaygroundError("LLM response parsing failed") from exc

    return LLMPlaygroundResult(model=model, response=content)
