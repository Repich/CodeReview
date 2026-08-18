from __future__ import annotations

import uuid

from worker.app.main import serialize_result
from worker.app.models import AnalysisResult, DetectorFinding
from worker.app.services.redaction import redact_bsl_source_text, redact_text


SENTINEL = "CodexSentinelCredential_20260818"


def test_regular_literal_and_comment_are_redacted() -> None:
    source = f'Пароль = "{SENTINEL}"; // backup password={SENTINEL}'
    redacted, _ = redact_bsl_source_text(source)
    assert SENTINEL not in redacted
    assert "<REDACTED>" in redacted
    assert "<REDACTED_COMMENT>" in redacted


def test_query_text_keeps_syntax_but_redacts_credentials() -> None:
    source = f'Запрос.Текст = "ВЫБРАТЬ 1; Password={SENTINEL}; UID=service-user";'
    redacted, _ = redact_text(source)
    assert "ВЫБРАТЬ 1" in redacted
    assert SENTINEL not in redacted
    assert "service-user" not in redacted


def test_uri_credentials_are_redacted() -> None:
    source = f'Строка = "https://service:{SENTINEL}@example.test/api";'
    redacted, _ = redact_bsl_source_text(source)
    assert SENTINEL not in redacted


def test_serialized_findings_do_not_duplicate_secret() -> None:
    finding = DetectorFinding(
        norm_id="SECURITY_PASSWORD_STORAGE_NO_PLAINTEXT",
        detector_id="detector.password_plaintext",
        severity="critical",
        message="Plain password",
        recommendation="Use a secret store",
        file_path="CommonModules/Test.bsl",
        line=1,
        context={"line": f'Пароль = "{SENTINEL}";'},
        snippet=f'1: Пароль = "{SENTINEL}";',
    )
    result = AnalysisResult(
        review_run_id=uuid.uuid4(),
        findings=[finding],
        engine_version="test",
        detectors_version="test",
        norms_version="test",
        duration_ms=1,
    )

    payload = serialize_result(result)
    serialized = str(payload)

    assert SENTINEL not in serialized
