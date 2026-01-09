# Deployment & Security Guide

This document summarizes how to publish the CodeReview 1C stack to the internet while keeping
tenant isolation and observability under control. The guide assumes the following topology:

```
Internet → Keenetic Router (DNAT 80/443) → Raspberry Pi (Caddy, TLS termination) → Ubuntu server (Docker)
```

The backend, worker, UI build and Postgres live inside Docker containers on the Ubuntu host. Caddy
on the Raspberry Pi is the only exposed component and proxies traffic based on the `Host` header.

## 1. Docker Compose (backend + worker)

Create `docker-compose.prod.yml` on the Ubuntu server:

```yaml
version: "3.9"
services:
  backend:
    build:
      context: .
      dockerfile: docker/Dockerfile.backend
    image: codereview-backend:latest
    restart: unless-stopped
    env_file:
      - .env
    environment:
      CODEREVIEW_DATABASE_URL: postgresql+psycopg://codereview:codereview@postgres:5432/codereview
      CODEREVIEW_DEBUG: "0"
    depends_on:
      - postgres
    expose:
      - "8000"              # reverse proxy will access the container via the bridge network
    networks:
      - internal

  worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.worker
    image: codereview-worker:latest
    restart: unless-stopped
    env_file:
      - .env
    depends_on:
      - backend
      - postgres
    networks:
      - internal

  postgres:
    image: postgres:15
    restart: unless-stopped
    environment:
      POSTGRES_DB: codereview
      POSTGRES_USER: codereview
      POSTGRES_PASSWORD: strong-password
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - internal

volumes:
  pgdata:

networks:
  internal:
    driver: bridge
```

Notes:

- The UI is built with `npm run build` and published as static assets by Caddy (see below).
- Do **not** publish container ports to the host; only `expose` them so that Caddy can reverse-proxy
  via the Docker network or the host loopback.
- Run database migrations inside the `backend` container:
  `docker compose run --rm backend alembic upgrade head`.

## 2. Reverse proxy (Caddy) snippet

On the Raspberry Pi add a new server block, e.g. `codereview.1cretail.ru`:

```
codereview.1cretail.ru {
    encode gzip

    # Static UI build (copied from ui/dist to /srv/codereview-ui)
    root * /srv/codereview-ui
    file_server

    # API reverse proxy
    @api path /api/*
    handle @api {
        reverse_proxy 192.168.1.76:8080 {
            header_up X-Forwarded-For {remote_host}
            header_up X-Forwarded-Proto {scheme}
        }
    }

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        Content-Security-Policy "default-src 'self'; frame-ancestors 'none'; base-uri 'self';"
        X-Frame-Options "DENY"
        Referrer-Policy "no-referrer"
    }

    # Optional: simple rate limit by IP
    rate_limit {
        zone api 20r/s burst 40
        key {remote_ip}
        matcher remote_path /api/*
    }
}
```

- Copy the UI build (`ui/dist`) to `/srv/codereview-ui` and restart Caddy.
- All API traffic is tunneled to the backend container via LAN, TLS terminates on Caddy.

## 3. Security-specific environment variables

The backend exposes several knobs (defaults shown):

```
CODEREVIEW_ACCESS_LOG_ENABLED=true
CODEREVIEW_TRUSTED_PROXY_DEPTH=1            # number of proxies that append to X-Forwarded-For (Caddy ⇒ 1)
CODEREVIEW_BLOCKED_IPS=203.0.113.5,198.51.100.7
CODEREVIEW_BLOCKED_CIDRS=192.0.2.0/24,2001:db8::/32
CODEREVIEW_BLOCKED_COUNTRIES=CN,RU,BY
CODEREVIEW_GEOIP_DB_PATH=/var/geoip/GeoLite2-Country.mmdb
```

How it works:

- Each request goes through `SecurityMiddleware`. It extracts the real client IP from the
  `X-Forwarded-For` header, applies IP/CIDR/country blocklists and logs the request to `access_logs`.
- GeoIP lookups are optional; download the [MaxMind GeoLite2 Country](https://dev.maxmind.com/geoip/geoip2/geolite2/)
  database manually and mount it into the backend container. When the path is missing the system simply
  does not perform country checks.
- If a request is blocked the middleware returns HTTP 403 before the handler executes and records the
  rejection reason (`block_reason` column).

## 4. Access logging & monitoring

- Every API call results in an entry inside the `access_logs` table with timestamp, IP, country code,
  HTTP method, path, status code, latency and user agent. The log also records the authenticated user
  (if present).
- Administrators can inspect logs via the new endpoint:
  `GET /api/admin/access-logs?limit=200&ip=203.0.113.5` (bearer token required). The output contains
  the user email (if known) and any block reason.
- Combine this with existing `audit_logs` to see what each user did with CodeReview.

### Blocking abusive sources

- To block a single IP add it to `CODEREVIEW_BLOCKED_IPS` and restart the backend container.
- To block an IP range add a CIDR to `CODEREVIEW_BLOCKED_CIDRS`.
- To block entire regions list ISO3166-1 alpha-2 country codes in `CODEREVIEW_BLOCKED_COUNTRIES`.
- All block decisions are logged and visible through `/api/admin/access-logs`.

## 5. Admin roles

- Admin accounts are **not** granted through the UI. Update the `user_accounts.role` column manually,
  e.g.: `UPDATE user_accounts SET role='admin' WHERE email='you@example.com';`
- Only administrators can access `/api/admin/*` routes. All other users are restricted to their own
  runs and artifacts.

## 6. Operational checklist

1. Build UI and copy the static assets to the directory served by Caddy.
2. `docker compose pull` (or `build`) on the Ubuntu host, run migrations, restart services.
3. Confirm that `/api/health` reports the new version.
4. Inspect `/api/admin/access-logs?limit=50` after opening the site to ensure that IP detection works.
5. Schedule nightly backups of Postgres (`pg_dump`) and the `artifact_storage` directory.
6. Monitor Caddy logs + backend logs (they include `missing_source_artifact`, worker start events, etc).

Following the steps above ensures that:

- each tenant sees only their own data,
- every request is logged and can be attributed,
- suspicious IPs or regions can be blocked centrally,
- TLS termination and reverse proxying stay outside the Docker host, hardening the attack surface.
