# Безопасное развёртывание

## Обязательные секреты

Backend и worker не запускаются без следующих значений:

- `CODEREVIEW_DATABASE_URL`;
- `CODEREVIEW_AUTH_JWT_SECRET` — минимум 32 случайных символа;
- `CODEREVIEW_WORKER_API_TOKEN` — минимум 32 случайных символа и одно значение для backend/worker.

Секреты генерируются вне репозитория, например `openssl rand -hex 32`, и хранятся только в локальном `.env` с правами `0600` или во внешнем secret store.

## Сеть

- Redis не публикуется на host-порт.
- Backend по умолчанию привязан к `127.0.0.1:8200`.
- Для отдельного reverse proxy задайте `CODEREVIEW_BACKEND_BIND_ADDRESS` равным LAN-адресу backend и ограничьте доступ firewall’ом.
- В `CODEREVIEW_TRUSTED_PROXY_CIDRS` перечисляются только адреса реальных reverse proxy. Недоверенный `X-Forwarded-For` игнорируется.

## Ротация

После подозрения на утечку отзовите ключи у LLM-провайдеров, смените JWT secret, worker token, пароль БД и ingest-токены. Смена JWT secret завершает все существующие сессии.

## Проверка после запуска

- `/api/review-runs/next-task` без `X-Worker-Token` возвращает `401`;
- отправка результатов без worker token или административного JWT возвращает `401`;
- Redis отсутствует среди опубликованных host-портов;
- прямой поддельный `X-Forwarded-For` не меняет определённый адрес клиента;
- sentinel-секрет отсутствует в LLM prompts, Model Lab prompts, findings и артефактах.
