#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from worker.app.models import AnalysisTask, SourceUnit  # noqa: E402
from worker.app.services.analyzer import Analyzer  # noqa: E402


SYSTEM_PROMPT = (
    "Ты — эксперт по код-ревью конфигураций 1С и автор свода норм. "
    "На основе приведённого кода, списка уже найденных нарушений и выдержек из стандартов "
    "найди дополнительные нарушения. Возвращай только новые нормы, которых нет в списке."
)


def load_api_key() -> str | None:
    key = os.getenv("DEEPSEEK_API_KEY")
    if key:
        return key
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if not line or line.strip().startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                if k.strip() == "DEEPSEEK_API_KEY":
                    key = v.strip()
                    os.environ["DEEPSEEK_API_KEY"] = key
                    return key
    return None


def run_static_analysis(path: Path, module_type: str, name: str) -> list[dict[str, Any]]:
    content = path.read_text(encoding="utf-8")
    analyzer = Analyzer()
    task = AnalysisTask(
        review_run_id=uuid.uuid4(),
        sources=[
            SourceUnit(
                path=str(path),
                name=name,
                content=content,
                module_type=module_type,
            )
        ],
    )
    result = analyzer.run(task)
    return [asdict(finding) for finding in result.findings]


def gather_context(files: list[Path]) -> str:
    chunks: list[str] = []
    for file in files:
        if not file.exists():
            continue
        chunks.append(f"### {file.name}\n{file.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(chunks)


def build_llm_prompt(code: str, findings: list[dict[str, Any]], context: str) -> str:
    findings_json = json.dumps(findings, ensure_ascii=False, indent=2) if findings else "[]"
    code_block = textwrap.dedent(
        f"""
        Код для анализа:

        ```
        {code}
        ```

        Найденные статическими детекторами нарушения (JSON):
        {findings_json}

        Контекст стандартов:
        {context or "—"}

        Задача: перечисли дополнительные нарушения норм, которые отсутствуют в списке выше.
        Для каждой новой нормы верни JSON-объект с полями:
        - norm_id (уникальное имя, например LONG_SERVER_OPS_ASYNC_001)
        - section (раздел стандарта)
        - category
        - norm_text
        - source_reference (ссылка на пункт стандарта или документ)
        - evidence (массив объектов с полями file, lines, reason)

        Верни только JSON-массив без пояснительного текста.
        """
    ).strip()
    return code_block


def call_deepseek(api_key: str, base_url: str, model: str, prompt: str) -> str:
    url = base_url.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": model,
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
    with httpx.Client(timeout=60) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"]


def auto_context_files(explicit: list[str] | None) -> list[Path]:
    if explicit:
        return [Path(p).resolve() for p in explicit]
    return sorted(ROOT.glob("docs/llm_*.md"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Анализ 1С-модуля статикой + LLM.")
    parser.add_argument("module_path", type=Path, help="Путь к файлу модуля 1С")
    parser.add_argument("--module-type", default="CommonModule", help="Тип модуля (по умолчанию CommonModule)")
    parser.add_argument("--name", help="Имя модуля (по умолчанию = имя файла)")
    parser.add_argument("--llm-context", action="append", help="Путь к файлу с пояснениями для LLM. Можно указать несколько.")
    parser.add_argument("--llm-base-url", default=os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com"), help="Базовый URL DeepSeek API")
    parser.add_argument("--llm-model", default=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"), help="Имя модели DeepSeek")
    parser.add_argument("--no-llm", action="store_true", help="Не вызывать LLM, вывести только результаты статанализа")
    args = parser.parse_args()

    module_path: Path = args.module_path.resolve()
    if not module_path.exists():
        raise SystemExit(f"Файл {module_path} не найден")

    name = args.name or module_path.stem
    static_findings = run_static_analysis(module_path, args.module_type, name)

    print("=== Статический анализ ===")
    if not static_findings:
        print("Нарушений не найдено детекторами.")
    else:
        for idx, finding in enumerate(static_findings, start=1):
            print(f"{idx}. [{finding['severity']}] {finding['norm_id']} — {finding['message']}")
            location = f"{finding.get('file_path')}:{finding.get('line')}"
            print(f"   {location}")
            if finding.get("recommendation"):
                print(f"   Рекомендация: {finding['recommendation']}")

    if args.no_llm:
        return

    api_key = load_api_key()
    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY не найден (установите переменную окружения или добавьте в .env).")

    context_files = auto_context_files(args.llm_context)
    context_text = gather_context(context_files)
    module_code = module_path.read_text(encoding="utf-8")
    prompt = build_llm_prompt(module_code, static_findings, context_text)

    print("\n=== Запрос к LLM ===")
    print(f"Модель: {args.llm_model}")
    if context_files:
        print("Подключённые контексты:")
        for file in context_files:
            print(f"  - {file.relative_to(ROOT)}")

    try:
        raw_response = call_deepseek(api_key, args.llm_base_url, args.llm_model, prompt)
    except httpx.HTTPError as exc:
        raise SystemExit(f"Ошибка запроса к LLM: {exc}") from exc

    print("\n=== Ответ LLM ===")
    print(raw_response)
    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError:
        return

    print("\n=== Предложенные новые нормы ===")
    if not parsed:
        print("LLM не предложила новых нарушений.")
        return
    for idx, item in enumerate(parsed, start=1):
        print(f"{idx}. {item.get('norm_id')} — {item.get('norm_text')}")
        source = item.get("source_reference")
        if source:
            print(f"   Источник: {source}")
        evidence = item.get("evidence") or []
        for ev in evidence:
            file = ev.get("file")
            lines = ev.get("lines")
            reason = ev.get("reason")
            print(f"   - {file}:{lines} → {reason}")


if __name__ == "__main__":
    main()
