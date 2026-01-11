from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_admin, get_db
from backend.app.core.config import get_settings
from backend.app.models.caddy_access_log import CaddyAccessLog
from backend.app.schemas.caddy_logs import CaddyAccessLogRead

router = APIRouter(prefix="/admin/caddy-logs", tags=["admin"])

SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie"}


@router.post("/ingest", status_code=204)
async def ingest_caddy_logs(request: Request, db: Session = Depends(get_db)) -> Response:
    settings = get_settings()
    expected_token = settings.caddy_log_ingest_token
    if not expected_token:
        raise HTTPException(status_code=503, detail="Caddy log ingest is not configured")
    token = _extract_token(request)
    if token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid ingest token")
    body = await request.body()
    entries = _parse_entries(body)
    if not entries:
        return Response(status_code=204)
    records = []
    for entry in entries:
        record = _build_record(entry)
        if record:
            records.append(record)
    if records:
        db.bulk_save_objects(records)
    _prune_old_logs(db, settings.caddy_log_retention_days)
    db.commit()
    return Response(status_code=204)


@router.get("", response_model=list[CaddyAccessLogRead])
def list_caddy_logs(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
    limit: int = Query(200, ge=1, le=500),
    host: str | None = Query(default=None),
    ip: str | None = Query(default=None),
    status: int | None = Query(default=None),
    path_query: str | None = Query(default=None, alias="path"),
) -> list[CaddyAccessLog]:
    query = db.query(CaddyAccessLog).order_by(CaddyAccessLog.created_at.desc())
    if host:
        query = query.filter(CaddyAccessLog.host == host)
    if ip:
        query = query.filter(CaddyAccessLog.remote_ip == ip)
    if status is not None:
        query = query.filter(CaddyAccessLog.status_code == status)
    if path_query:
        query = query.filter(CaddyAccessLog.uri.ilike(f"%{path_query}%"))
    return query.limit(limit).all()


def _extract_token(request: Request) -> str | None:
    token = request.headers.get("x-log-token")
    if token:
        return token.strip()
    auth = request.headers.get("authorization")
    if not auth:
        return None
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip() or None
    return auth.strip() or None


def _parse_entries(body: bytes) -> list[dict[str, Any]]:
    text = body.decode("utf-8", errors="ignore").strip()
    if not text:
        return []
    if text.startswith("["):
        payload = json.loads(text)
        if isinstance(payload, dict):
            return [payload]
        if isinstance(payload, list):
            return [entry for entry in payload if isinstance(entry, dict)]
        return []
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def _build_record(entry: dict[str, Any]) -> CaddyAccessLog | None:
    created_at = _parse_timestamp(entry.get("ts"))
    request = entry.get("request") or {}
    if not isinstance(request, dict):
        request = {}
    headers = request.get("headers") or {}
    if isinstance(headers, dict):
        headers = _sanitize_headers(headers)
    else:
        headers = {}
    status = entry.get("status")
    if status is None and isinstance(entry.get("resp"), dict):
        status = entry["resp"].get("status")
    size = entry.get("size")
    if size is None and isinstance(entry.get("resp"), dict):
        size = entry["resp"].get("size")
    duration = entry.get("duration")
    return CaddyAccessLog(
        created_at=created_at,
        host=_clip_str(request.get("host"), 255),
        method=_clip_str(request.get("method"), 16),
        uri=_clip_str(request.get("uri"), 1000),
        status_code=_int_or_none(status),
        duration_ms=_parse_duration(duration),
        size_bytes=_int_or_none(size),
        remote_ip=_clip_str(request.get("remote_ip") or request.get("client_ip"), 45),
        user_agent=_clip_str(_header_value(headers, "user-agent"), 255),
        referer=_clip_str(_header_value(headers, "referer"), 1000),
        raw={"request": {**request, "headers": headers}, **_strip_request(entry)},
    )


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _parse_duration(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(float(value) * 1000)
    if isinstance(value, str):
        raw = value.strip()
        try:
            if raw.endswith("ms"):
                return int(float(raw[:-2]))
            if raw.endswith("s"):
                return int(float(raw[:-1]) * 1000)
            return int(float(raw))
        except ValueError:
            return None
    return None


def _sanitize_headers(headers: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADERS:
            continue
        sanitized[key] = value
    return sanitized


def _header_value(headers: dict[str, Any], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name.lower():
            if isinstance(value, list) and value:
                return str(value[0])
            if isinstance(value, str):
                return value
            return str(value)
    return None


def _clip_str(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text[:limit]


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _strip_request(entry: dict[str, Any]) -> dict[str, Any]:
    stripped = dict(entry)
    stripped.pop("request", None)
    return stripped


def _prune_old_logs(db: Session, retention_days: int) -> None:
    if retention_days <= 0:
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    db.query(CaddyAccessLog).filter(CaddyAccessLog.created_at < cutoff).delete()
