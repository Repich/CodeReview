# Личный кабинет и биллинг (MVP)

## Цели
- добавить концепцию пользователя (личный кабинет)
- хранить баланс в "баллах" и историю транзакций
- списывать баллы за каждый запуск code-review, пополнять их при покупке/начислении
- подготовить API/модели для будущих сценариев (подарки, промокоды, тарифы)

## Основные сущности
- `user_accounts`
  - `id` UUID PK
  - `email`, `name`, `auth_provider`, `auth_sub`
  - `status` (active, blocked)
  - `created_at`, `updated_at`
- `wallets`
  - `id` UUID PK
  - `user_id` FK → user_accounts
  - `balance` BIGINT (в баллах)
  - `currency` (для совместимости, пока "points")
  - `updated_at`
- `wallet_transactions`
  - `id` UUID PK
  - `wallet_id` FK
  - `type` (debit, credit)
  - `source` (run_charge, manual_adjustment, purchase, reward, gift)
  - `amount` BIGINT (>0)
  - `context` JSONB (run_id, комментарии, платежный proof)
  - `created_at`
- ссылка `review_runs.user_id` + `cost_points` (сколько списано за запуск)

## Поведение
- при регистрации пользователя создается wallet с нулевым балансом
- endpoint `POST /api/wallets/{id}/adjust` (для админов) + `POST /api/wallets/purchase` (заглушка)
- при `POST /api/review-runs` нужно перед созданием списать стоимость запуска:
  1. определить тариф (пока фикс `10` баллов)
  2. проверить баланс, заблокировать (в транзакции)
  3. создать run c `requested_cost=10`, запись в `wallet_transactions`
  4. если недостаточно — 402 Payment Required
- хранить агрегированный баланс только в `wallets.balance` (обновляется триггером/кодом)

## API (первый этап)
- `GET /api/me` — профиль + баланс
- `GET /api/wallets/transactions?limit=…` — история
- `POST /api/wallets/adjust` — админское начисление/списание
- `POST /api/review-runs` — требует Bearer токен (пользователь определяется по JWT) + списание баллов

## UI (первый этап)
- личный кабинет: отображение имени пользователя, текущего баланса, список последних транзакций
- при создании запуска показывать сколько баллов спишется и текущее значение, disable если < cost

## Следующие этапы
- полноценная аутентификация (OIDC), подарки, промокоды, оплату через эквайринг, автоматический расчёт тарифа по количеству файлов
