from __future__ import annotations

from typing import Iterable

def enum_values(enum_cls: type) -> list[str]:
    return [member.value for member in enum_cls]
