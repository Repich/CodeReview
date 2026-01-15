#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "==> git pull"
git pull

echo "==> build UI"
pushd ui >/dev/null
npm ci
npm run build
popd >/dev/null

echo "==> sync static"
rm -rf backend/app/static
mkdir -p backend/app/static
cp -r ui/dist/* backend/app/static/

if [[ "${RUN_MIGRATIONS:-}" == "1" ]]; then
  echo "==> build backend + worker images"
  docker-compose build backend worker

  echo "==> run migrations"
  docker-compose run --rm backend bash -c "cd /app/backend && PYTHONPATH=/app alembic upgrade head"

  echo "==> start backend + worker containers"
  docker-compose up -d backend worker
  echo "==> done"
  exit 0
fi

echo "==> rebuild backend + worker containers"
docker-compose up -d --build backend worker

echo "==> done"
