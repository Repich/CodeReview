# CodeReview 1C

Платформа для автоматизированного code-review 1С:Предприятие. Состоит из backend (FastAPI + Postgres), worker с детекторами и LLM, UI на React и инфраструктуры для развёртывания через Docker.

## Структура

- `backend/` — FastAPI API, модели, миграции.
- `worker/` — очередь задач, детекторы, сервисы LLM.
- `ui/` — React/Vite интерфейс (список запусков, карточка запуска, админка).
- `docs/` — описание сущностей, норм, пайплайна и требований к инфраструктуре.
- `infrastructure/docker/` — Dockerfile'ы и инфраструктурные конфиги.
- `scripts/` — вспомогательные скрипты (create_admin, deploy_refresh, анализ модулей).

## Быстрый старт (локально)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt -r worker/requirements.txt pytest

# если нужен локальный pg
# docker compose up -d postgres

# Сначала заполните .env по образцу .env.example, затем выполните миграции.
cd backend
PYTHONPATH=.. alembic upgrade head
cd ..

# backend
uvicorn backend.app.main:app --reload --env-file .env

# worker
export CODEREVIEW_WORKER_BACKEND_API_URL=http://127.0.0.1:8000/api
python -m worker.app.main --once

# UI dev
cd ui && npm install && npm run dev
```

### Полезные env

Backend (префикс `CODEREVIEW_`):
- `CODEREVIEW_DATABASE_URL` — строка подключения к Postgres.
- `CODEREVIEW_AUTH_JWT_SECRET` — секрет подписи JWT.
- `CODEREVIEW_WORKER_API_TOKEN` — общий service token backend/worker (не менее 32 случайных символов).
- `CODEREVIEW_DEFAULT_RUN_COST_POINTS` — стоимость запуска (по умолчанию 10).
- `CODEREVIEW_ADMIN_LOCAL_ONLY` — ограничить админку локальной сетью (bool).
- `CODEREVIEW_ADMIN_ALLOWED_CIDRS` — список CIDR для админов (JSON-массив строк).
- `CODEREVIEW_REGISTRATION_CAPTCHA_ENABLED` — включить капчу на регистрации (`true/false`, по умолчанию `false`).
- `CODEREVIEW_TURNSTILE_SECRET_KEY` — секрет Turnstile (если включаете капчу).
- `CODEREVIEW_CADDY_LOG_INGEST_TOKEN` — токен приёма логов Caddy.
- `CODEREVIEW_TRUSTED_PROXY_CIDRS` — JSON-массив CIDR доверенных reverse proxy. Заголовок `X-Forwarded-For` от остальных адресов игнорируется.
- `CODEREVIEW_BLOCKED_IPS`, `CODEREVIEW_BLOCKED_CIDRS`, `CODEREVIEW_BLOCKED_COUNTRIES` — блок-листы.
- `CODEREVIEW_GEOIP_DB_PATH` — путь к базе GeoIP (если используете геоблокировку).

Worker (префикс `CODEREVIEW_WORKER_`):
- `CODEREVIEW_WORKER_BACKEND_API_URL` — URL backend API.
- `CODEREVIEW_WORKER_API_TOKEN` — тот же service token, что настроен на backend.
- `CODEREVIEW_WORKER_REDIS_URL` — Redis URL.
- `CODEREVIEW_WORKER_LLM_API_BASE`, `CODEREVIEW_WORKER_LLM_MODEL` — параметры LLM.
- `CODEREVIEW_WORKER_LLM_CONTEXT_GLOB` — glob для доп. контекста LLM.

UI:
- `VITE_TURNSTILE_SITE_KEY` — site key Turnstile (актуально только при включенной капче на backend).

## Администратор

Админ может входить только с локальных адресов (см. `CODEREVIEW_ADMIN_LOCAL_ONLY` и `CODEREVIEW_ADMIN_ALLOWED_CIDRS`).
Создание/обновление админа:

```bash
docker-compose exec backend python /app/scripts/create_admin.py \
  --email admin@company.ru --name 'Admin'
```

## Регистрация и капча

- `POST /api/auth/register` — регистрация.
- По умолчанию капча при регистрации отключена.
- Для включения капчи задайте `CODEREVIEW_REGISTRATION_CAPTCHA_ENABLED=true` и `CODEREVIEW_TURNSTILE_SECRET_KEY`.
- После регистрации начисляется `CODEREVIEW_REGISTRATION_BONUS_POINTS` (по умолчанию 100).
- Есть rate limit: `CODEREVIEW_REGISTRATION_RATE_LIMIT` и `CODEREVIEW_REGISTRATION_RATE_WINDOW_MINUTES`.

## Сборка UI и раздача статики

В проде фронтенд отдаёт backend. UI собирается в Node 20 build stage backend-образа:

```bash
docker-compose build backend
docker-compose up -d backend
```

Проверка: `curl -I http://127.0.0.1:8000/` → `200`.

## Продакшн (домашний сервер)

1) Подготовить Postgres (отдельный контейнер/кластер):
```sql
CREATE DATABASE codereview;
CREATE USER <DB_USER> WITH PASSWORD '<GENERATED_DB_PASSWORD>';
GRANT ALL PRIVILEGES ON DATABASE codereview TO codereview_user;
```

2) `.env` на сервере:
```dotenv
CODEREVIEW_DATABASE_URL=postgresql+psycopg://<DB_USER>:<URL_ENCODED_DB_PASSWORD>@<DB_HOST>:5432/<DB_NAME>
CODEREVIEW_WORKER_BACKEND_API_URL=http://backend:8000/api
CODEREVIEW_WORKER_REDIS_URL=redis://redis:6379/0
CODEREVIEW_AUTH_JWT_SECRET=<GENERATE_WITH_OPENSSL_RAND_HEX_32>
CODEREVIEW_WORKER_API_TOKEN=<GENERATE_WITH_OPENSSL_RAND_HEX_32>
CODEREVIEW_BACKEND_BIND_ADDRESS=<LAN_ADDRESS_USED_BY_REVERSE_PROXY>
CODEREVIEW_TRUSTED_PROXY_CIDRS=["<REVERSE_PROXY_IP>/32"]
DEEPSEEK_API_KEY=<PROVIDER_SECRET>
CODEREVIEW_TURNSTILE_SECRET_KEY=<PROVIDER_SECRET>
CODEREVIEW_CADDY_LOG_INGEST_TOKEN=<GENERATE_WITH_OPENSSL_RAND_HEX_32>
```

3) Сборка и запуск:
```bash
docker-compose up -d --build backend worker redis
```

4) Миграции:
```bash
docker-compose exec backend bash -c "cd /app/backend && PYTHONPATH=/app alembic upgrade head"
```

5) Reverse proxy:
Caddy проксирует публичный HTTPS-домен на `<CODEREVIEW_BACKEND_BIND_ADDRESS>:8200`.

6) Проверки:
- `curl -I http://<CODEREVIEW_BACKEND_BIND_ADDRESS>:8200/` → `200`.
- `curl http://<CODEREVIEW_BACKEND_BIND_ADDRESS>:8200/api/health` → `{"status":"ok"}`.

## Логи Caddy

Логи Caddy пишутся в JSON. Рекомендуемый путь — `/var/log/caddy/*.log`.
Vector на Raspberry Pi читает эти логи и шлёт в backend:
- URL: `POST /api/admin/caddy-logs/ingest`
- Header: `X-Log-Token: <CODEREVIEW_CADDY_LOG_INGEST_TOKEN>`
- Хранение в Postgres: `CODEREVIEW_CADDY_LOG_RETENTION_DAYS` (по умолчанию 30)

## Артефакты и выгрузки

- `artifact_storage/<run_id>_*` — артефакты (LLM JSON, выгрузки).
- `GET /api/findings/export/{review_run_id}.jsonl` — JSONL по находкам.
- `GET /api/review-runs/{id}/llm/logs` — LLM‑логи (только админ).

## Когнитивная сложность

Worker рассчитывает когнитивную сложность по каждой процедуре/функции и сохраняет:
- total / total_loc / avg_per_line
- список процедур с complexity и avg_per_line
Отображается в UI на странице запуска.

## Скрипт обновления на сервере

`scripts/deploy_refresh.sh`:
- `git pull`
- сборка UI внутри multi-stage backend-образа
- пересборка backend/worker
- при `RUN_MIGRATIONS=1` выполняет миграции

Пример:
```bash
RUN_MIGRATIONS=1 ./scripts/deploy_refresh.sh
```

## Документация

См. `docs/README.md` и `agents.md`.
