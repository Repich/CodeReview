# Архитектура CodeReview 1C (MVP)

## Состав
- **Backend (FastAPI + SQLAlchemy + Postgres)**: CRUD по основным сущностям, очередь задач, приём результатов, личный кабинет/кошелёк.
- **Worker (Python)**: 11 детекторов, опрос `/review-runs/next-task`, отправка `/review-runs/{id}/results`, стабы LLM.
- **UI (Vite/React)**: список запусков, карточка запуска, личный кабинет (баланс и транзакции), форма создания run'а.
- **Инфраструктура**: docker compose (postgres, redis, backend, worker, nginx), Alembic миграции, CI (pytest детекторов + UI build).

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
- `Analyzer` добавляет заглушку LLM и формирует payload в формате `data_contracts.md`.
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
