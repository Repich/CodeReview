from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError
from starlette.requests import Request

from backend.app.api.deps import _is_valid_worker_token
from backend.app.core.config import Settings
from backend.app.schemas.review_runs import ReviewRunCreate
from backend.app.services import model_lab
from backend.app.utils.request_ip import extract_client_ip


SENTINEL = "CodexSentinelCredential_20260818"


def _request(peer: str, forwarded_for: str | None = None) -> Request:
    headers = []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode("ascii")))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers,
            "client": (peer, 12345),
            "server": ("testserver", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )


def test_worker_token_is_required() -> None:
    assert _is_valid_worker_token("b" * 64)
    assert not _is_valid_worker_token(None)
    assert not _is_valid_worker_token("wrong")


def test_runtime_secrets_reject_public_defaults() -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql+psycopg://user:pass@db/test",
            auth_jwt_secret="insecure-dev-secret",
            worker_api_token="b" * 64,
        )


def test_review_run_create_rejects_runtime_context() -> None:
    with pytest.raises(ValidationError):
        ReviewRunCreate.model_validate(
            {
                "sources": [],
                "context": {
                    "worker_settings_override": {
                        "llm_api_base": "https://attacker.invalid",
                    }
                },
            }
        )


def test_untrusted_peer_cannot_spoof_forwarded_for() -> None:
    request = _request("203.0.113.10", "127.0.0.1")
    assert str(extract_client_ip(request, ["192.168.1.123/32"])) == "203.0.113.10"


def test_trusted_proxy_chain_uses_first_untrusted_hop_from_right() -> None:
    request = _request("192.168.1.123", "127.0.0.1, 203.0.113.10")
    assert str(extract_client_ip(request, ["192.168.1.123/32"])) == "203.0.113.10"


def test_model_lab_source_map_is_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    run = type("Run", (), {"context": {"source_artifact": "source.json"}})()
    db = type("DB", (), {"get": lambda self, model, run_id: run})()
    monkeypatch.setattr(
        model_lab.artifact_service,
        "load_sources",
        lambda path: [
            {
                "path": "CommonModules/Test.bsl",
                "content": f'Пароль = "{SENTINEL}";',
            }
        ],
    )

    source_map = model_lab._load_source_map(db, uuid.uuid4())

    assert SENTINEL not in "\n".join(source_map["CommonModules/Test.bsl"])
