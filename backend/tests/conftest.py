from __future__ import annotations

import os


os.environ.setdefault(
    "CODEREVIEW_DATABASE_URL",
    "postgresql+psycopg://test_user:test_password@127.0.0.1:5432/test_db",
)
os.environ.setdefault("CODEREVIEW_AUTH_JWT_SECRET", "a" * 64)
os.environ.setdefault("CODEREVIEW_WORKER_API_TOKEN", "b" * 64)
