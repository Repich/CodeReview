# CodeReview 1C

Платформа для автоматизированного code-review 1С:Предприятие. Состоит из backend (FastAPI + Postgres), worker с детекторами, UI на React и инфраструктуры для развёртывания через Docker.

## Структура

- `backend/` — FastAPI API, модели, миграции.
- `worker/` — очередь задач, детекторы, тесты.
- `ui/` — React/Vite интерфейс (список запусков, карточка запуска, личный кабинет с AI-блоком).
- `docs/` — описание сущностей, норм, пайплайна и требований к инфраструктуре.
- `docs/deployment_security.md` — сводка по прод-окружению, блок-листам и аудитам.
- `infrastructure/docker/` — Dockerfile'ы и конфигурация nginx.
- `scripts/` — `bootstrap_structure.py`, `analyze_module.py`, утилиты для генерации структуры и ручного прогона воркера.

## Быстрый старт (локально)

```bash
make bootstrap        # убедиться, что структура создана
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt -r worker/requirements.txt pytest
alembic -c backend/alembic.ini upgrade head
uvicorn backend.app.main:app
python -m worker.app.main
```

> Авторизация использует JWT (`Authorization: Bearer ...`). Для разработки достаточно значения по умолчанию, но в проде задайте `CODEREVIEW_AUTH_JWT_SECRET`, `CODEREVIEW_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` и осмысленный `DEEPSEEK_API_KEY` (если задействуете LLM).

**Создание запуска с исходниками:**

```bash
curl -X POST http://localhost:8000/api/review-runs \
  -H "Content-Type: application/json" \
  -d '{
        "project_id": "demo",
        "sources": [
          {
            "path": "CommonModules/DangerousModule.bsl",
            "name": "DangerousModule",
            "module_type": "CommonModule",
            "content": "Процедура Опасность()\n    Выполнить(\"Сообщить(1)\");\nКонецПроцедуры"
          }
        ]
      }'
```

После создания воркер (`python -m worker.app.main --once`) запросит задачу через `/api/review-runs/next-task`, выполнит анализ и отправит `POST /api/review-runs/{id}/results`.

UI:

```bash
cd ui
npm install
npm run dev
```

## Сборка UI и раздача статики

В продакшне фронтенд обслуживается самим backend. После изменений UI выполните:

```bash
cd ui
npm ci
npm run build

cd ..
rm -rf backend/app/static
mkdir -p backend/app/static
cp -r ui/dist/* backend/app/static/
```

Проверяем, что `GET /` и `HEAD /` возвращают 200: `curl -I http://127.0.0.1:8000/`.

## Продакшн (домашний сервер)

1. Подготовьте Postgres (отдельный контейнер/кластер):
   ```sql
   CREATE DATABASE codereview;
   CREATE USER codereview_user WITH PASSWORD '***';
   GRANT ALL PRIVILEGES ON DATABASE codereview TO codereview_user;
   ```
2. `.env`:
   ```
   DATABASE_URL=postgresql+psycopg://codereview_user:***@host.docker.internal:5432/codereview
   CODEREVIEW_DATABASE_URL=postgresql+psycopg://codereview_user:***@host.docker.internal:5432/codereview
   CODEREVIEW_WORKER_BACKEND_API_URL=http://backend:8000/api
   DEEPSEEK_API_KEY=...
   ```
3. `docker-compose up -d --build backend worker` (redis поднимется автоматически).
4. Выполните миграции: `docker-compose exec backend bash -c "cd /app/backend && PYTHONPATH=/app alembic upgrade head"`.
5. Caddy на Raspberry Pi проксирует `codereview.1cretail.ru` → `192.168.1.76:8200` и заверщает TLS. В backend нет отдельного nginx — он отвечает и за API, и за статику.

Детали — в `docs/deployment_security.md`.

### Автоматический анализ отдельных модулей

Для локального ревью конкретного модуля 1С используйте CLI-скрипт:

```bash
python scripts/analyze_module.py path/to/Module.bsl \
  --llm-context docs/llm_long_operation_prompt.md
```

Скрипт выполняет текущий набор статических детекторов (см. `worker/app`) и затем отправляет код в LLM (по умолчанию DeepSeek) вместе с выдержками из стандартов.  
Промпт формируется покусочно: модуль делится на процедурные фрагменты, для каждого подбираются релевантные нормы из `docs/system_standards.txt` и только после этого выполняется вызов модели. Это позволяет укладываться в ограничение контекста и получать более точные рекомендации.
Требуется переменная `DEEPSEEK_API_KEY` (можно задать в `.env`). Дополнительные подробности о пайплайне — в `docs/analysis_pipeline.md`.

### Интеграция LLM в основном пайплайне

- Воркер автоматически вызывает DeepSeek для модулей, которые обладают признаками длительных операций/импорта файлов.  
- Контекст для модели берётся из кратких справок (`docs/llm_*.md`); версия подсказки фиксируется в `review_runs.llm_prompt_version`.
- Результат сохраняется в таблицу `ai_findings` со статусом `suggested`. Пользователь может подтвердить или отклонить предложение в UI на странице запуска.
- Каждый запрос/ответ LLM пишется в JSON-лог (`artifact_storage/<run_id>_llm_*.json`) и доступен только администраторам через карточку запуска (одна запись на каждый проанализированный фрагмент).
- Для работы необходим ключ `DEEPSEEK_API_KEY` (env или `.env`). Дополнительно доступны переменные `CODEREVIEW_WORKER_LLM_API_BASE`, `CODEREVIEW_WORKER_LLM_MODEL`, `CODEREVIEW_WORKER_LLM_CONTEXT_GLOB`.

### Авторизация и баллы

- `POST /api/auth/register` — регистрация пользователя (ответ: JWT).
- `POST /api/auth/login` — вход по email/паролю (ответ: JWT). Используйте `Authorization: Bearer <token>` для всех защищённых запросов.
- `POST /api/users` — создание пользователя администратором (можно выдать роль admin/user).
- `GET /api/users/me` — текущий профиль (роль, статус, email).
- `GET /api/wallets/me` — баланс пользователя в баллах.
- `GET /api/wallets/transactions` — история списаний/пополнений.
- `POST /api/wallets/adjust` — админское начисление/списание баллов (можно передать `user_email` и причину).

После миграций автоматически создаётся администратор `admin@localhost` с паролем `admin123`. Каждый запуск code-review списывает 10 баллов с кошелька владельца запуска; при недостатке средств `POST /api/review-runs` вернёт `402`.

### Артефакты и выгрузки

- `GET /api/audit/io/{io_log_id}/download` — отдать файл из `artifact_storage`, привязанный к записи IOLog.
- `GET /api/findings/export/{review_run_id}.jsonl` — выгрузить находки запуска в JSONL (по запросу создаётся артефакт `findings.jsonl`).
- `GET /api/ai-findings?review_run_id=<id>` — вернуть предложения LLM (доступно владельцу запуска).
- `PATCH /api/ai-findings/{id}` — изменить статус AI-замечания (`suggested` → `pending`/`confirmed`/`rejected`).
- `GET /api/review-runs/{id}/llm/logs` — список диагностических логов LLM (только администраторы). Каждый лог можно скачать через `/api/audit/io/{io_log_id}/download`.

## Production deployment (сейчас поднято на codereview.1cretail.ru)

1. **UI build**  
   ```bash
   cd ui
   npm ci
   npm run build
   rm -rf ../backend/app/static && mkdir -p ../backend/app/static
   cp -r dist/* ../backend/app/static/
   ```
   FastAPI отдаёт `backend/app/static/index.html` и все ассеты самостоятельно, поэтому
   отдельный контейнер UI не нужен.

2. **Подготовить `.env` на сервере**

   ```dotenv
   CODEREVIEW_DATABASE_URL=postgresql+psycopg://codereview_user:***@host.docker.internal:5432/codereview
   CODEREVIEW_WORKER_BACKEND_API_URL=http://backend:8000/api
   CODEREVIEW_WORKER_REDIS_URL=redis://redis:6379/0
   DEEPSEEK_API_KEY=...
   CODEREVIEW_DEFAULT_RUN_COST_POINTS=10
   CODEREVIEW_AUTH_JWT_SECRET=change-me
   ```

   > Мы используем уже существующий postgres вне docker-compose, поэтому `host.docker.internal`
   > пробрасывается через `extra_hosts` (см. `docker-compose.yml`).

3. **Собрать/обновить контейнеры**

   ```bash
   docker-compose up -d --build backend worker redis
   docker-compose exec backend bash -c "cd /app/backend && PYTHONPATH=/app alembic upgrade head"
   ```

4. **Reverse proxy**  
   Caddy на Raspberry Pi проксирует `codereview.1cretail.ru` к `192.168.1.76:8200`.  
   TLS завершается на Caddy, backend видит реальный IP через `X-Forwarded-For`.

5. **Готовность**  
   - `curl -I http://127.0.0.1:8200/` → `200 OK` (root выдаёт index.html).  
   - `curl http://127.0.0.1:8200/api/health` → `{"status":"ok","version":...}`.  
   - В Caddy-логах нет `connection refused`.

## Security & monitoring

- `SecurityMiddleware` читает реальный IP (`CODEREVIEW_TRUSTED_PROXY_DEPTH`), ведёт таблицу `access_logs`,
  блокирует IP/CIDR/страны (`CODEREVIEW_BLOCKED_IPS`, `CODEREVIEW_BLOCKED_CIDRS`, `CODEREVIEW_BLOCKED_COUNTRIES`)
  и логирует причину (`block_reason`).
- Геолокация включается, если смонтировать `CODEREVIEW_GEOIP_DB_PATH` (например, MaxMind GeoLite2).
- Логи доступов для админов: `GET /api/admin/access-logs?limit=200`.
- Все вызовы LLM (worker) сохраняются в `ai_findings` + JSON в `artifact_storage`.

## CI

`.github/workflows/ci.yml` запускает pytest для детекторов и собирает UI.

## Дальнейшие шаги

1. Дополнить репозитории, схемы и миграции бизнес-логикой.
2. Подключить очередь (Redis/BullMQ) и горизонтальное масштабирование воркеров.
3. Реализовать LLM-этап, заменив заглушку `LLM disabled`.
4. Расширять список норм/детекторов и autotests.
