# Контракты данных и сущности

Документ фиксирует целевые сущности системы код-ревью 1С и форматы обмена данными. Он используется как источник истины для моделей БД, API-схем и миграций.

## Таблицы БД

### Norm
- `id` — UUID PK.
- `norm_id` — строковый код нормы (уникальный).
- `title`, `section`, `scope`, `detector_type`, `check_type`, `default_severity`, `norm_text` — справочная информация из каталога норм.
- `code_applicability` — bool, применяется ли к модулю.
- `is_active` — bool, чтобы отключать норму без удаления.
- `version` — int, инкремент при правке текста нормы.
- `created_at`, `updated_at` — временные метки.

### ReviewRun
- `id` — UUID PK.
- `external_ref` — строка для связи с системой пользователя (например, номер MR/таска).
- `project_id` — namespace конфигурации или репозитория.
- `status` — enum (`queued`, `running`, `completed`, `failed`).
- `input_hash` — контрольная сумма загруженного кода.
- `engine_version`, `detectors_version`, `norms_version`, `llm_prompt_version` — строки для воспроизводимости.
- `initiator`, `source_type`, `context` (JSONB) — вспомогательные поля.
- `queued_at`, `started_at`, `finished_at` — временные метки.

### Finding
- `id` — UUID PK.
- `review_run_id` — FK → ReviewRun.
- `norm_id` — FK → Norm.
- `detector_id` — строковый идентификатор детектора.
- `severity` — enum (`critical`, `major`, `minor`, `info`).
- `file_path` — относительный путь к файлу.
- `line_start`, `line_end`, `column_start`, `column_end` — позиции.
- `message` — краткое описание нарушения.
- `code_snippet` — текст вокруг нарушения.
- `recommendation` — текст.
- `finding_hash` — строка для дедупликации.
- `engine_version`, `trace_id` — тех. поля.
- `llm_raw_response` — JSONB (результат второго этапа, пока NULL).
- `context` — JSONB дополнительной информации (например, имя объекта 1С).
- `created_at` — timestamp.

### AIFinding
- `id` — UUID PK.
- `review_run_id` — FK → ReviewRun.
- `status` — enum (`suggested`, `pending`, `confirmed`, `rejected`).
- `norm_id`, `section`, `category`, `severity` — описание новой нормы от LLM (могут быть NULL).
- `norm_text` — текст нормы (обязателен).
- `source_reference` — строка со ссылкой на пункт стандарта.
- `evidence` — JSONB массив ссылок на строки кода (file/lines/reason).
- `llm_raw_response` — исходный JSON объекта из LLM.
- `created_at`, `updated_at` — временные метки.

### Feedback
- `id` — UUID PK.
- `review_run_id`, `finding_id` — связи.
- `reviewer` — логин или email.
- `verdict` — enum (`tp`, `fp`, `fn`, `skip`).
- `comment` — текст.
- `created_at` — timestamp.

### AuditLog
- `id` — UUID PK.
- `review_run_id` — FK.
- `event_type` — строка (`run_created`, `worker_started`, `detector_finished`, ...).
- `actor` — service/user.
- `payload` — JSONB произвольный.
- `created_at` — timestamp.

### IOLog
- `id` — UUID PK.
- `review_run_id` — FK.
- `direction` — enum (`in`, `out`).
- `artifact_type` — строка (`source_zip`, `finding_jsonl`, `llm_log.json`, ...).
- `storage_path` — относительный путь к файлу в `artifact_storage`.
- `checksum` — SHA256.
- `size_bytes` — bigint.
- `created_at` — timestamp.

### LLMPromptVersion
- `id` — UUID PK.
- `name` — человекочитаемое название.
- `version_tag` — semver/commit hash.
- `prompt_body` — TEXT.
- `created_at` — timestamp.

## JSON контракт Findings

Worker возвращает результаты анализа в виде JSON объекта:

```json
{
  "review_run_id": "uuid",
  "norms_version": "hash",
  "detectors_version": "hash",
  "engine_version": "semver",
  "findings": [
    {
      "id": "uuid",
      "norm_id": "SECURITY_EXEC_EVAL_SERVER_RESTRICTED",
      "detector_id": "detector.exec_eval",
      "severity": "critical",
      "file_path": "CommonModules/ServerModule.bsl",
      "range": {
        "start": { "line": 42, "column": 5 },
        "end": { "line": 45, "column": 12 }
      },
      "message": "Использование Выполнить без безопасного режима",
      "recommendation": "Включите безопасный режим и проверьте входные параметры.",
      "code_snippet": "...",
      "context": {
        "object_name": "CommonModule.Server" ,
        "trace_id": "abc123"
      }
    }
  ],
  "trace": {
    "worker_id": "hostname",
    "duration_ms": 1542,
    "detectors": [
      { "id": "detector.exec_eval", "duration_ms": 42, "status": "ok" }
    ]
  }
}
```

Требования:
1. `findings` — единый формат, используется UI и этап обучения.
2. Поле `range` обязательно, даже если известна только одна строка (тогда start=end).
3. `context` — расширяемый словарь для детализированной информации.
4. `trace` фиксирует исполнение детекторов для дебага и аудита.

LLM-этап добавляет поля:
- `ai_findings` — список объектов с полями `norm_id`, `section`, `category`, `severity`, `norm_text`, `source_reference`, `evidence`, `llm_raw_response`.
- `llm_prompt_version` — идентификатор набора подсказок/контекста, переданных в модель.

## Версионирование
- `norms_version` — hash файла `norms.yaml`.
- `detectors_version` — git hash worker-а.
- `engine_version` — semver backend/worker.
- `llm_prompt_version` — ссылка на запись в `LLMPromptVersion`.

## Примечания
- Все временные поля хранятся в UTC и имеют timezone (`TIMESTAMP WITH TIME ZONE`).
- UUID генерируются на приложении.
- JSONB используется для гибкой сохранности метаданных и будущей интеграции с LLM.

## Источник данных анализа

При создании `ReviewRun` клиент передаёт список модулей (SourceUnit). Структура SourceUnit:

```json
{
  "path": "CommonModules/DangerousModule.bsl",
  "name": "DangerousModule",
  "content": "... исходный текст ...",
  "module_type": "CommonModule"
}
```

Бэкенд сохраняет массив модулей в файл `<run_id>_sources.json` в каталоге `artifact_storage` и фиксирует запись `IOLog` (direction=in, artifact_type=sources.json). Путь к файлу кладётся в `ReviewRun.context.source_artifact`. Воркер самостоятельно анализирует директивы `&НаСервере`/`&НаКлиенте`, поэтому дополнительные флаги контекста от клиента не требуются.

## API обмена воркера и бэкенда

- `POST /api/review-runs` — создаёт запуск. Тело запроса: поля `ReviewRunCreate` + `sources` (список SourceUnit). Ответ — `ReviewRunRead`.
- `GET /api/review-runs/next-task` — выдаёт следующий запуск со статусом `queued`, переводит его в `running` и возвращает `AnalysisTaskResponse` (run_id + sources). Если задач нет — HTTP 204.
- `POST /api/review-runs/{id}/results` — принимает результат анализа (`AnalysisResultPayload`), создаёт записи `findings`, обновляет статус запуска на `completed`, сохраняет версии движка и длительность анализа.
- `GET /api/ai-findings` — список AI-предложений (фильтр по `review_run_id`/`status`).
- `PATCH /api/ai-findings/{id}` — обновление статуса (подтверждено/отклонено и т.д.).
- `GET /api/review-runs/{id}/llm/logs` — вернуть JSON содержимое логов LLM (только администраторы).

Все обмены используют единый формат Findings (см. выше). Это обеспечивает консистентность UI, обучения и дальнейших интеграций.
