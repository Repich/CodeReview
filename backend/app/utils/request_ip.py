from __future__ import annotations

import logging
from ipaddress import ip_address, ip_network, IPv4Address, IPv6Address
from typing import Iterable, Optional

from fastapi import Request

logger = logging.getLogger(__name__)


def extract_client_ip(
    request: Request,
    trusted_proxy_cidrs: Iterable[str],
) -> Optional[IPv4Address | IPv6Address]:
    peer = None
    if request.client and request.client.host:
        try:
            peer = ip_address(request.client.host)
        except ValueError:
            logger.debug("Unable to parse peer IP address from %s", request.client.host)
    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded or not peer or not ip_in_cidrs(peer, trusted_proxy_cidrs):
        return peer

    chain: list[IPv4Address | IPv6Address] = []
    for raw in forwarded.split(","):
        candidate = raw.strip()
        if not candidate:
            continue
        try:
            chain.append(ip_address(candidate))
        except ValueError:
            logger.debug("Unable to parse forwarded IP address from %s", candidate)
    chain.append(peer)
    for candidate in reversed(chain):
        if not ip_in_cidrs(candidate, trusted_proxy_cidrs):
            return candidate
    return chain[0] if chain else peer


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
