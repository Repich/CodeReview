from __future__ import annotations

import logging
from ipaddress import ip_address, ip_network, IPv4Address, IPv6Address
from typing import Iterable, Optional

from fastapi import Request

logger = logging.getLogger(__name__)


def extract_client_ip(request: Request, trusted_proxy_depth: int) -> Optional[IPv4Address | IPv6Address]:
    forwarded = request.headers.get("x-forwarded-for")
    candidate = None
    if forwarded:
        parts = [part.strip() for part in forwarded.split(",") if part.strip()]
        if parts:
            index = -1 - max(trusted_proxy_depth, 0)
            if abs(index) <= len(parts):
                candidate = parts[index]
            else:
                candidate = parts[0]
    elif request.client and request.client.host:
        candidate = request.client.host
    if not candidate:
        return None
    try:
        return ip_address(candidate)
    except ValueError:
        logger.debug("Unable to parse IP address from %s", candidate)
        return None


def ip_in_cidrs(ip_obj: IPv4Address | IPv6Address, cidrs: Iterable[str]) -> bool:
    for cidr in cidrs:
        cidr = cidr.strip()
        if not cidr:
            continue
        try:
            network = ip_network(cidr, strict=False)
        except ValueError:
            logger.warning("Invalid CIDR in allowed list: %s", cidr)
            continue
        if ip_obj in network:
            return True
    return False
