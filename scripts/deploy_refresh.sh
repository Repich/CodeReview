#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

build_services() {
  if docker-compose build "$@"; then
    return
  fi
  echo "==> BuildKit failed; retry with the classic builder"
  DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 docker-compose build "$@"
}

echo "==> git pull"
git pull

if [[ "${RUN_MIGRATIONS:-}" == "1" ]]; then
  echo "==> build backend + worker images"
  build_services backend worker

  echo "==> run migrations"
  docker-compose run --rm backend bash -c "cd /app/backend && PYTHONPATH=/app alembic upgrade head"

  echo "==> start backend + worker containers"
  docker-compose up -d backend worker
  echo "==> done"
  exit 0
fi

echo "==> rebuild backend + worker containers"
build_services backend worker
docker-compose up -d backend worker

echo "==> done"
