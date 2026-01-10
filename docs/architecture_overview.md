# Архитектура CodeReview 1C (MVP)

## Состав
- **Backend (FastAPI + SQLAlchemy + Postgres)**: CRUD по основным сущностям, очередь задач, приём результатов, личный кабинет/кошелёк, выдача статики UI.
- **Worker (Python)**: 11 детекторов, опрос `/review-runs/next-task`, отправка `/review-runs/{id}/results`, LLM-пайплайн (DeepSeek).
- **UI (Vite/React)**: список запусков, карточка запуска, личный кабинет (баланс и транзакции), форма создания run'а. В проде собранная статика лежит в `backend/app/static`.
- **Инфраструктура**: docker compose (redis, backend, worker; Postgres подключаем к существующему инстансу), Alembic миграции, CI (pytest детекторов + UI build), reverse-proxy на Caddy.

## Основные таблицы
- `review_runs` — запуск проверки. Новые поля: `user_id`, `cost_points`.
- `norms`, `findings`, `feedback`, `audit_logs`, `io_logs`, `llm_prompt_versions`, `ai_findings` (описаны в `docs/data_contracts.md`). Для каждого вызова LLM создаётся артефакт `llm_log.json` + запись `IOLog`.
- `ai_findings` — предложения ЛЛМ по новым нормам и их статус подтверждения.
- `user_accounts` — пользователь/личный кабинет.
- `wallets` — баланс в баллах (один кошелёк на пользователя).
- `wallet_transactions` — история списаний/пополнений (`txn_type` = debit/credit, `source` = run_charge/manual/purchase).  
  Enum `wallet_txn_type` используется в Postgres.

## API (ключевые)
- `POST /api/auth/register`, `POST /api/auth/login` — регистрация и получение JWT.
- `POST /api/review-runs` — создаёт run, сохраняет sources, списывает `default_run_cost_points` (10) c кошелька пользователя (определяется по JWT).
- `GET /api/review-runs/next-task` / `POST /api/review-runs/{id}/results` — обмен worker-а с backend.
- `GET /api/findings/export/{run}.jsonl` — выгрузка найденных нарушений (с `code_snippet` и описанием нормы).
- `GET /api/audit/io/{id}/download` — скачивание артефакта из `artifact_storage`.
- `POST /api/users`, `GET /api/users/me` — управление пользователями.
- `GET /api/wallets/me`, `GET /api/wallets/transactions`, `POST /api/wallets/adjust` — баланс, история и ручные начисления.

## Нормы и стандарты
- Актуальный каталог норм лежит в `norms.yaml`. Он включает как детектируемые правила (детекторы worker-а), так и нормы, требующие LLM или ручной проверки.
- Источники: `Система стандартов и методик разработки конфигураций 14_10_2025.pdf`, `Руководство разработчика 8.3`, внутренние чек-листы. Ссылки и идентификаторы (`norm_id`, `source_reference`) зафиксированы в YAML.
- Для каждой нормы мы указываем `section`, `category`, `default_severity`, `automation_hint`, `detector_type`, чтобы backend/worker могли формировать findings и LLM-промты.
- Новые нормы добавляются через обновление `norms.yaml` + документацию (`docs/next_steps.md`) и должны ссылаться на официальные документы.

## Worker
- Реестр 11 детекторов (`worker/app/detectors/critical.py`). Каждый возвращает `DetectorFinding` с `snippet` (несколько строк вокруг нарушения).
- LLM-пайплайн:
  1. Модуль `code_units.py` режет исходный файл на процедуры/функции, помечает диапазоны диффа (если передан `change_map`).
  2. Для каждого unit подтягиваются релевантные нормы (`norms.yaml` → embeddings/ключевые слова, см. `docs/analysis_pipeline.md`).
  3. Worker собирает подсказку (код + контекст + статические findings) и вызывает DeepSeek. Ответы логируются в `artifact_storage/<run>_llm_*.json` и таблицу `ai_findings`.
  4. LLM видит только изменённые строки, но получает до 20 строк контекста вокруг каждого изменения.
- CLI: `python -m worker.app.main --once` для одиночного задания или постоянный опрос.

## UI
- `/runs` — список запусков, форма создания показывает стоимость и блокируется при нехватке баллов. Автопулинг пока run активен.
- `/runs/:id` — карточка запуска: фильтры, журнал, аудит, артефакты, кнопка скачивания JSONL.
- `/account` — личный кабинет (профиль, баланс, транзакции). Для админа доступна форма пополнения кошелька пользователя.
- `/login` — форма входа/регистрации и сохранение Bearer-токена (axios автоматически добавляет `Authorization`).

## Биллинг/баллы
- Настройка `CODEREVIEW_DEFAULT_RUN_COST_POINTS` (по умолчанию 10).
- При создании run'а вызывается `billing.charge_for_run` — создаёт запись в `wallet_transactions`, обновляет `wallet.balance`. При недостатке баллов возвращается 402.
- По умолчанию при миграциях создаётся администратор `admin@localhost / admin123`. Создание run'а и любые защищённые эндпоинты требуют Bearer-токен.

## Как перезапустить локально
1. **Backend**: `uvicorn backend.app.main:app --reload --env-file .env`. Убедитесь, что `.env` содержит `CODEREVIEW_DATABASE_URL` (или экспортируйте `DATABASE_URL`).
2. **Alembic**: `PYTHONPATH=.. DATABASE_URL=postgresql+psycopg://codereview:codereview@localhost:5432/codereview alembic upgrade head`.
3. **Worker**: `python -m worker.app.main --once` (или без `--once`).
4. **UI**: `cd ui && npm install && npm run dev` (использует `VITE_API_BASE` и хранит Bearer-токен в localStorage).
5. **Postgres**: `docker compose up -d postgres` (по умолчанию `codereview/codereview`).

## Диагностика
- Если лицевой баланс не грузится — проверьте `Authorization: Bearer` (токен истёк/невалиден).
- Если JSONL без описания нормы — убедитесь, что `norms.yaml` существует в корне; backend читает его на каждый экспорт.
- Ошибка Alembic `wallet_txn_type already exists` → удалите тип вручную: `DROP TYPE IF EXISTS wallet_txn_type CASCADE;`.
- `fork: Resource temporarily unavailable` при Alembic/uvicorn обычно вызван ограничением среды — лучше запускать команды в обычном системном терминале.
- **Дифф-ревью**: если фронт отправляет `changes` (формат Crucible — пара `old_line/new_line`), backend сохраняет карту диапазонов. Worker проверяет только затронутые строки, но добавляет контекст в промпт.
- **LLM показатели**: каждая подсказка фиксирует `llm_prompt_version` и `engine_version`. Артефакты доступны только администратору (UI → «Диагностика LLM»).

## Развёртывание (prod)

- **UI**: `npm run build`, результат копируем в `backend/app/static`. FastAPI раздаёт `/` и ассеты, так что отдельный nginx внутри docker-compose не нужен.
- **Docker compose**: backend/worker/redis. Postgres живёт отдельно; контейнеры подключаются через `extra_hosts: host.docker.internal:host-gateway`.
- **Миграции**: `docker-compose exec backend bash -c "cd /app/backend && PYTHONPATH=/app alembic upgrade head"`.
- **Reverse proxy**: Raspberry Pi + Caddy → `codereview.1cretail.ru` → `192.168.1.76:8200`. Проксируем `/api/*` на backend, остальное отдаёт статика.
- **Переменные окружения**: `CODEREVIEW_DATABASE_URL`, `CODEREVIEW_WORKER_BACKEND_API_URL`, `DEEPSEEK_API_KEY`, `CODEREVIEW_AUTH_JWT_SECRET`, `CODEREVIEW_DEFAULT_RUN_COST_POINTS`, блок-листы (`CODEREVIEW_BLOCKED_IPS/CIDRS/COUNTRIES`), GeoIP (`CODEREVIEW_GEOIP_DB_PATH`), `CODEREVIEW_TRUSTED_PROXY_DEPTH=1`.

## Безопасность и наблюдаемость

- `SecurityMiddleware`:
  - извлекает реальный IP (`X-Forwarded-For`) и проверяет его по IP/CIDR/странам;
  - при блокировке немедленно отвечает 403 и пишет причину;
  - пишет каждую операцию в `access_logs` (ip, страна, метод, путь, latency, user_agent, user_id/None, block_reason).
- Админ-эндпоинты: `GET /api/admin/access-logs` и `GET /api/admin/llm/logs`.
- Скачивание артефактов (`/api/audit/io/{id}/download`) проверяет владельца run'а.
- На уровне Caddy включены HSTS/Referrer-Policy, статические файлы выдаём только из `backend/app/static`, путь проверяется функцией `_is_within_static`.
