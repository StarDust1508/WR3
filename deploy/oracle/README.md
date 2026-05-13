# wr3 production deploy — Oracle Cloud Always Free

This brings wr3 backend off your Mac mini and onto a free 24/7 server. The
target is **Oracle Cloud Always Free Ampere** (4 OCPU ARM + 24 GB RAM +
200 GB storage). That's the most generous free tier on the market; nothing
in wr3's stack stresses it.

What ends up running on Oracle:
- Postgres 16 + pgvector (primary DB, replaces local Mac PG)
- Redis 7 (broker + cache, replaces local Mac Redis)
- FastAPI (`wr3-api.service`, port 8001 internal)
- Celery worker (`wr3-worker.service` — runs scan pipeline, scrapers, watcher)
- Celery beat (`wr3-beat.service` — fires `refresh_incidents` and
  `refresh_watched_contracts` every 6 hours)
- Aderyn / Slither / Wake / Foundry / solc-select toolchain

CF Workers (lander + Mini App) stay where they are. The only change there
is updating `WR3_API_URL` to point at your Oracle host (via tunnel).

---

## Step 1 — Sign up & provision the VM

1. Create an Oracle Cloud account: <https://signup.cloud.oracle.com/>
   (free, no credit card hold required by 2026, but they sometimes ask for
   a card just for fraud-prevention — won't be charged on Always Free tier).
2. Region: pick the one closest to you. **Ashburn (us-east-1)**,
   **Frankfurt (eu-frankfurt-1)** and **Tokyo (ap-tokyo-1)** typically
   have Ampere capacity available; some regions are exhausted.
3. **Create Compute Instance** with these settings:
   - **Image:** Canonical Ubuntu 24.04 (ARM64)
   - **Shape:** `VM.Standard.A1.Flex`, 4 OCPU, 24 GB RAM (max free tier)
   - **VCN:** Default + create new public subnet
   - **SSH key:** upload your public key (`~/.ssh/id_ed25519.pub` or similar)
4. After it's running, note the **public IP**.

## Step 2 — Open ports in OCI security list

By default Oracle blocks everything. In the VM's VCN → Security List →
add Ingress Rules:

| Source | Protocol | Port | Purpose |
|---|---|---|---|
| 0.0.0.0/0 | TCP | 22 | SSH (consider restricting to your IP) |
| 0.0.0.0/0 | TCP | 443 | HTTPS via Cloudflare Tunnel — see Step 5 |

**Don't** open 8001 publicly — the API stays internal, traffic flows in
via Cloudflare Tunnel.

## Step 3 — Run the installer

```bash
ssh ubuntu@<public-ip>
curl -sSL https://raw.githubusercontent.com/StarDust1508/WR3/main/deploy/oracle/install.sh | bash
```

The script installs every dependency and is **idempotent** — safe to
re-run. It takes ~5-10 minutes on the Ampere VM (Aderyn cargo-build is
the longest stretch).

## Step 4 — Configure secrets

Edit `/home/ubuntu/wr3/apps/api/.env`. The installer wrote a template
with random `NEXTAUTH_SECRET` and `TELEGRAM_WEBHOOK_SECRET` — those are
fine to keep. You need to fill in:

- `NAVYAI_API_KEY` (your api.navy key)
- `ETHERSCAN_API_KEY` (free at <https://etherscan.io/apis>)
- `TELEGRAM_BOT_TOKEN` (from @BotFather)
- `NEXT_PUBLIC_SITE_URL` (your Cloudflare Workers URL or custom domain)

Then change the Postgres and Redis passwords to match what's in `.env`:

```bash
# Postgres
sudo -u postgres psql -c "ALTER USER wr3 WITH PASSWORD 'YOUR_REAL_DB_PASSWORD';"

# Redis (edit /etc/redis/redis.conf, change requirepass line, then restart)
sudo sed -i 's/^requirepass .*/requirepass YOUR_REAL_REDIS_PASSWORD/' /etc/redis/redis.conf
sudo systemctl restart redis-server
```

Update `DATABASE_URL` and `REDIS_URL` in `.env` to use those passwords.

## Step 5 — Cloudflare Tunnel (public HTTPS without opening 443 to the world)

Cloudflare Tunnel is the cleanest free way to put a private host behind a
public DNS name with TLS — no Let's Encrypt cron, no certbot, no IPs in
DNS, no exposed origin.

1. In Cloudflare dashboard → **Zero Trust → Networks → Tunnels** →
   **Create a tunnel** (Cloudflared).
2. Name it `wr3-api`. Copy the install command Cloudflare gives you and
   run it on the Oracle VM.
3. Configure a Public Hostname:
   - **Subdomain:** `api` · **Domain:** your CF zone
   - **Service:** `http://localhost:8001`
4. Update CF Workers env var `WR3_API_URL` to `https://api.yourdomain.com`.

If you don't have a domain yet: get one at Cloudflare Registrar
(~$10/year for `.com`).

## Step 6 — Start services

```bash
sudo systemctl enable --now wr3-api wr3-worker wr3-beat

# Verify
sudo systemctl status wr3-api wr3-worker wr3-beat
curl http://localhost:8001/v1/health
# After CF Tunnel is up:
curl https://api.yourdomain.com/v1/health
```

Watch logs in real time:

```bash
journalctl -u wr3-api -u wr3-worker -u wr3-beat -f
```

## Step 7 — Migrate data from Mac (optional)

If you want to bring your existing scans / subscriptions / incidents:

```bash
# On Mac
pg_dump -h localhost -U bubble3 wr3 > /tmp/wr3.dump.sql
scp /tmp/wr3.dump.sql ubuntu@<public-ip>:/tmp/

# On Oracle VM
PGPASSWORD=YOUR_DB_PASSWORD psql -h localhost -U wr3 -d wr3 < /tmp/wr3.dump.sql
```

If you start fresh, the alembic migrations have already run as part of
`install.sh` — no data, no problem.

---

## Operations

### Update to latest main

```bash
cd ~/wr3
git pull
(cd apps/api && uv sync && uv run alembic upgrade head)
(cd packages/audit-engine && uv sync)
sudo systemctl restart wr3-api wr3-worker wr3-beat
```

### Resource ceiling check

```bash
htop          # CPU + RAM, expect <30% steady, spikes during scans
df -h         # disk, watch /var/lib/postgresql growth
journalctl --disk-usage   # journal can balloon — rotate via journald.conf
```

### Common failures

- **"Slither returns 0 findings"** — usually solc version mismatch. The
  wrappers auto-detect pragma and set SOLC_VERSION, but if you scanned an
  exotic pragma (e.g. 0.6.x) install matching solc: `solc-select install 0.6.12`.
- **"Aderyn panics with `data did not match any variant`"** — known
  Aderyn 0.1.9 bug on some legacy contracts. Updating to a newer Aderyn
  fixes it: `cargo install aderyn --force`.
- **Celery beat doesn't fire** — check `journalctl -u wr3-beat`; the
  scheduler is at /tmp/celerybeat-schedule (gets recreated each restart
  thanks to PrivateTmp).

### Backups

Daily Postgres dump to a CF R2 bucket via cron:

```cron
0 3 * * * /home/ubuntu/wr3/deploy/oracle/backup.sh
```

(Backup script not yet shipped — bring-your-own for now, this is the
known TODO from TZ §10.1.)
