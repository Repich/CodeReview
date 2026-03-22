from __future__ import annotations

import json
from dataclasses import dataclass

import httpx


class ModelLabLLMError(RuntimeError):
    pass


@dataclass
class ChatCompletionResult:
    content: str
    raw: dict


def discover_models(api_base: str, api_key: str, timeout_seconds: int) -> list[str]:
    base = api_base.strip().rstrip("/")
    if not base:
        raise ModelLabLLMError("api_base is empty")
    url = _resolve_endpoint(base, "models")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:500] if exc.response.text else "<empty>"
        raise ModelLabLLMError(f"Ошибка GET {url} ({exc.response.status_code}): {body}") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise ModelLabLLMError(f"Ошибка запроса GET {url}: {exc}") from exc

    rows = payload.get("data")
    if not isinstance(rows, list):
        raise ModelLabLLMError(f"Некорректный ответ GET {url}: отсутствует список data")
    models: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        model_id = row.get("id")
        if isinstance(model_id, str) and model_id.strip():
            models.append(model_id.strip())
    if not models:
        raise ModelLabLLMError("Список моделей пуст")
    models.sort()
    return models


def chat_completion(
    *,
    api_base: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    timeout_seconds: int,
    temperature: float | None = None,
) -> ChatCompletionResult:
    base = api_base.strip().rstrip("/")
    if not base:
        raise ModelLabLLMError("api_base is empty")
    url = _resolve_endpoint(base, "chat/completions")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if "/api/v3/" in url:
        payload["stream"] = False
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPStatusError as exc:
        preview = exc.response.text[:500] if exc.response.text else "<empty>"
        raise ModelLabLLMError(
            f"Ошибка chat completion ({exc.response.status_code}): {preview}"
        ) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise ModelLabLLMError(f"Ошибка запроса chat completion: {exc}") from exc

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        preview = json.dumps(body, ensure_ascii=False)[:500]
        raise ModelLabLLMError(f"Некорректный ответ chat completion: {preview}") from exc
    return ChatCompletionResult(content=str(content), raw=body)


def _resolve_endpoint(base: str, resource: str) -> str:
    cleaned = base.rstrip("/")
    lowered = cleaned.lower()
    if lowered.endswith("/v1") or lowered.endswith("/v3"):
        return f"{cleaned}/{resource}"
    if "/api/v3" in lowered:
        return f"{cleaned}/{resource}"
    if "ai.beeline.ru" in lowered:
        return f"{cleaned}/api/v3/{resource}"
    return f"{cleaned}/v1/{resource}"
