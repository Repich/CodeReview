import os
import time

import httpx

from backend.app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("DEEPSEEK_API_KEY is missing")
        raise SystemExit(1)

    url = settings.llm_api_base.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": "ping"},
            {"role": "user", "content": "ping"},
        ],
        "temperature": 0,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    print("api_base:", settings.llm_api_base)
    print("model:", settings.llm_model)
    print("timeout:", settings.llm_timeout_seconds)

    started_at = time.time()
    try:
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            elapsed = time.time() - started_at
            print("status:", response.status_code, "elapsed:", round(elapsed, 2), "sec")
            print("body:", response.text[:500])
    except Exception as exc:
        elapsed = time.time() - started_at
        print("error:", repr(exc), "elapsed:", round(elapsed, 2), "sec")


if __name__ == "__main__":
    main()
