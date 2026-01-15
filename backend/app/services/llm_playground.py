from __future__ import annotations

import logging
import os
import time
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
    api_base: str
    endpoint: str
    timeout_seconds: int
    request_headers: dict[str, str]
    request_payload: dict[str, object]


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
    api_base = settings.llm_api_base.rstrip("/")
    url = api_base + "/v1/chat/completions"
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
    safe_headers = {
        "Authorization": "Bearer ***",
        "Content-Type": "application/json",
    }

    started_at = time.time()
    try:
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.ReadTimeout as exc:
        elapsed = time.time() - started_at
        logger.warning("LLM playground read timeout after %.2fs", elapsed)
        raise LLMPlaygroundError(
            f"Таймаут ожидания ответа LLM ({elapsed:.1f} сек.)"
        ) from exc
    except httpx.ConnectTimeout as exc:
        elapsed = time.time() - started_at
        logger.warning("LLM playground connect timeout after %.2fs", elapsed)
        raise LLMPlaygroundError(
            f"Таймаут подключения к LLM ({elapsed:.1f} сек.)"
        ) from exc
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:500] if exc.response.text else "<empty>"
        logger.warning(
            "LLM playground request failed (%s): %s",
            exc.response.status_code,
            body,
        )
        raise LLMPlaygroundError(
            f"Ошибка LLM ({exc.response.status_code}): {body}"
        ) from exc
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.warning("LLM playground request failed: %s", exc)
        raise LLMPlaygroundError("Ошибка запроса к LLM") from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("LLM playground response parse failed: %s", exc)
        raise LLMPlaygroundError("LLM response parsing failed") from exc

    return LLMPlaygroundResult(
        model=model,
        response=content,
        api_base=api_base,
        endpoint=url,
        timeout_seconds=settings.llm_timeout_seconds,
        request_headers=safe_headers,
        request_payload=payload,
    )
