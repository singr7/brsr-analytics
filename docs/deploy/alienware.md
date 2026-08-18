# Deploy on alienware, fronted by omen

CPU only. No GPU, no app-code change. omen terminates TLS; alienware serves
plain HTTP on **18080** and publishes nothing else to the host.

## 1. Alienware: prepare

```bash
sudo mkdir -p /srv/brsr-analytics/data/{postgres,redis,objects,nginx-extra}
sudo chown -R 10001:10001 /srv/brsr-analytics/data/objects

# nginx refuses to start without this include (it gates /api/admin/).
sudo tee /srv/brsr-analytics/data/nginx-extra/admin-allowlist.conf >/dev/null <<'ACL'
allow 127.0.0.1;
allow <YOUR_LAN_CIDR>;      # e.g. 192.168.1.0/24
ACL

git clone <repo> /srv/brsr-analytics/app && cd /srv/brsr-analytics/app
cp .env.example .env.prod
```

Edit `.env.prod`:

| Key | Value |
|---|---|
| `APP_ENV` | `production` (requires a real `LLM_*` key) or `staging` while testing |
| `POSTGRES_PASSWORD` | `openssl rand -hex 24` |
| `DATABASE_URL` | `postgresql+asyncpg://brsrlens:<pw>@postgres:5432/brsrlens` |
| `REDIS_URL` | `redis://redis:6379/0` |
| `JWT_SECRET` | `openssl rand -hex 32` |
| `AUTH_EXPOSE_VERIFICATION_TOKEN` | `false` |
| `LLM_PROVIDER` / `LLM_API_KEY` / `LLM_NETWORK_ENABLED` | `openai` / real key / `true` |
| `FRONTEND_URL` | `https://brsr-analytics.radpretation.ai` |
| `SMTP_HOST` / `SMTP_PORT` | a real relay — mailhog is not in this stack |
| `OBJECT_STORE_BACKEND` | `local` |

Also set, for compose itself (same file):

```
DOMAIN_NAME=brsr-analytics.radpretation.ai
TRUSTED_PROXY_CIDR=<OMEN_IP>/32
EDGE_PORT=18080
DATA_ROOT=/srv/brsr-analytics/data
ENV_FILE=/srv/brsr-analytics/app/.env.prod
```

## 2. Alienware: build, migrate, start

```bash
cd /srv/brsr-analytics/app
C="docker compose -f infra/deploy/compose.alienware.yml --env-file .env.prod"

$C build                                    # ~10 min first time
$C up -d postgres redis
$C run --rm --no-deps api python -m alembic upgrade head
$C up -d
$C ps
curl -s localhost:18080/healthz             # expect status: ok
```

Firewall: only omen needs the port.

```bash
sudo ufw allow from <OMEN_IP> to any port 18080 proto tcp
```

## 3. Omen: nginx

```bash
sudo cp <repo>/infra/deploy/nginx/omen-brsr-analytics.conf \
        /etc/nginx/sites-available/brsr-analytics.radpretation.ai
sudo sed -i 's/ALIENWARE_IP/<alienware ip>/' \
        /etc/nginx/sites-available/brsr-analytics.radpretation.ai
# fix the ssl_certificate paths to the shared cert, then:
sudo ln -s /etc/nginx/sites-available/brsr-analytics.radpretation.ai \
           /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Do not add HSTS or security headers on omen for this vhost — the alienware edge
already sends them and nginx would emit duplicates.

## 4. Cloudflare

Add `brsr-analytics` → omen's public IP (A record, proxied). SSL mode **Full
(strict)** if the shared cert is a Cloudflare Origin cert or a public cert for
`*.radpretation.ai`.

## 5. Operate

```bash
$C logs -f api worker
$C restart api
git pull && $C build && $C run --rm --no-deps api python -m alembic upgrade head && $C up -d
```

Resource ceiling is ~6.5 GB RAM / 7.5 CPU across the stack (set per service in
`compose.alienware.yml`). Lower `worker`'s `cpus`/`mem_limit` first if the ML
load needs room.
