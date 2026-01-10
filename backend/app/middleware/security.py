from __future__ import annotations

import logging
import time
from ipaddress import ip_network, IPv4Address, IPv6Address
from typing import Iterable, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from backend.app.core.config import get_settings
from backend.app.db.session import SessionLocal
from backend.app.models.access_log import AccessLog
from backend.app.utils.request_ip import extract_client_ip

try:
    import geoip2.database
    from geoip2.errors import AddressNotFoundError
except ImportError:  # pragma: no cover
    geoip2 = None  # type: ignore
    AddressNotFoundError = Exception  # type: ignore

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.settings = get_settings()
        self.blocked_ips = {ip.strip() for ip in self.settings.blocked_ips if ip.strip()}
        self.blocked_networks = self._build_networks(self.settings.blocked_cidrs)
        self.blocked_countries = {code.upper() for code in self.settings.blocked_countries}
        self.trusted_proxy_depth = max(0, self.settings.trusted_proxy_depth)
        self.geo_reader = None
        if self.settings.geoip_db_path and geoip2:
            try:
                self.geo_reader = geoip2.database.Reader(self.settings.geoip_db_path)
                logger.info("GeoIP database loaded from %s", self.settings.geoip_db_path)
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to load GeoIP database: %s", exc)

    def _build_networks(self, cidrs: Iterable[str]) -> list:
        networks = []
        for cidr in cidrs:
            cidr = cidr.strip()
            if not cidr:
                continue
            try:
                networks.append(ip_network(cidr, strict=False))
            except ValueError:
                logger.warning("Invalid CIDR in blocked list: %s", cidr)
        return networks

    async def dispatch(self, request: Request, call_next):
        client_ip_obj = extract_client_ip(request, self.trusted_proxy_depth)
        client_ip = str(client_ip_obj) if client_ip_obj else "unknown"
        country_code = self._lookup_country(client_ip_obj)
        block_reason = self._check_block(client_ip_obj, country_code)
        if block_reason:
            if self.settings.access_log_enabled:
                self._persist_log(
                    user_id=self._resolve_user_id(request),
                    ip_address=client_ip,
                    country_code=country_code,
                    method=request.method,
                    path=request.url.path,
                    status_code=403,
                    duration_ms=0,
                    user_agent=request.headers.get("user-agent"),
                    block_reason=block_reason,
                )
            return JSONResponse(
                status_code=403,
                content={"detail": "Access denied"},
            )

        start_time = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            status_code = getattr(exc, "status_code", 500)
            raise
        finally:
            if self.settings.access_log_enabled:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                self._persist_log(
                    user_id=self._resolve_user_id(request),
                    ip_address=client_ip,
                    country_code=country_code,
                    method=request.method,
                    path=request.url.path,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    user_agent=request.headers.get("user-agent"),
                    block_reason=None,
                )

    def _resolve_user_id(self, request: Request):
        user = getattr(request.state, "current_user", None)
        return getattr(user, "id", None)

    def _lookup_country(self, ip_obj: Optional[IPv4Address | IPv6Address]) -> Optional[str]:
        if not ip_obj or not self.geo_reader:
            return None
        try:
            result = self.geo_reader.country(str(ip_obj))
            if result and result.country and result.country.iso_code:
                return result.country.iso_code.upper()
        except AddressNotFoundError:
            return None
        except Exception as exc:  # pragma: no cover
            logger.debug("GeoIP lookup failed: %s", exc)
        return None

    def _check_block(self, ip_obj, country_code: Optional[str]) -> Optional[str]:
        if not ip_obj:
            return None
        if str(ip_obj) in self.blocked_ips:
            return "ip_blocklist"
        for network in self.blocked_networks:
            if ip_obj in network:
                return "network_blocklist"
        if self.blocked_countries and country_code:
            if country_code.upper() in self.blocked_countries:
                return f"country_{country_code.lower()}"
        return None

    def _persist_log(
        self,
        *,
        user_id,
        ip_address: str,
        country_code: Optional[str],
        method: str,
        path: str,
        status_code: int,
        duration_ms: int,
        user_agent: Optional[str],
        block_reason: Optional[str],
    ) -> None:
        session = SessionLocal()
        try:
            log_entry = AccessLog(
                user_id=user_id,
                ip_address=ip_address,
                country_code=country_code,
                method=method,
                path=path[:512],
                status_code=status_code,
                duration_ms=duration_ms,
                user_agent=(user_agent or "")[:255] or None,
                block_reason=block_reason,
            )
            session.add(log_entry)
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.warning("Failed to persist access log: %s", exc)
        finally:
            session.close()
