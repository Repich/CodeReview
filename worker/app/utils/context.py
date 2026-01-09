from __future__ import annotations

import re
from typing import Dict

PROC_START_RE = re.compile(r"^\s*(Процедура|Функция)\b", re.IGNORECASE)
PROC_END_RE = re.compile(r"^\s*Конец(Процедуры|Функции)\b", re.IGNORECASE)


def _classify_attribute(line: str) -> str | None:
    """Return 'server', 'client', 'both', or None based on directive."""
    lowered = line.lower()
    has_server = "насервер" in lowered
    has_client = "наклиент" in lowered
    if has_server and has_client:
        return "both"
    if has_server:
        return "server"
    if has_client:
        return "client"
    return None


def compute_line_contexts(content: str) -> Dict[int, str]:
    """Compute execution context for each line of a BSL module."""
    contexts: Dict[int, str] = {}
    pending_context: str | None = None
    current_context = "unspecified"
    for idx, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("&"):
            ctx = _classify_attribute(stripped)
            if ctx:
                pending_context = ctx
        if PROC_START_RE.match(stripped):
            current_context = pending_context or "unspecified"
            pending_context = None
        contexts[idx] = current_context
        if PROC_END_RE.match(stripped):
            current_context = "unspecified"
    if not contexts:
        contexts[1] = "unspecified"
    return contexts

