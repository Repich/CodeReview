#!/bin/bash
set -euo pipefail

container=${1:-codereview-postgres-1}
db_name=${2:-codereview}
user=${3:-codereview}

cat <<SQL | docker exec -i "$container" psql -U "$user" postgres
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$db_name';
DROP DATABASE IF EXISTS $db_name;
CREATE DATABASE $db_name;
SQL
