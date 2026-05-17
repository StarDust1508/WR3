from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wr3_api.config import get_settings
from wr3_api.middleware.request_id import RequestIdMiddleware
from wr3_api.routes import auth, health, public, scan, subscription, telegram

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("api.startup", env=settings.wr3_env)
    yield
    logger.info("api.shutdown")


app = FastAPI(
    title="wr3 API",
    version="0.1.0",
    description="AI-powered smart contract audit pipeline",
    lifespan=lifespan,
)

# Origins:
#   - localhost:3000 — Next.js dev server when developing locally
#   - https://t.me — Telegram WebApp iframe origin
#   - *.wr3.pages.dev — legacy Cloudflare Pages (kept for grace period)
#   - *.workers.dev — Cloudflare Workers deploys, both prod and preview.
#     The actual production host is currently `wr3.bigmandmitriy777.workers.dev`
#     after the Pages-to-Workers migration. The regex matches any wr3-prefixed
#     workers.dev subdomain so we don't have to bake the personal account
#     name into the API.
# allow_credentials=True is REQUIRED for our cookie/JWT auth, which means
# `allow_origins=["*"]` is illegal — the regex covers all valid origins.
# Middleware execution order is REVERSE of registration. We want
# RequestId to wrap CORS so the access-log line carries the request_id
# even when CORS would have rejected the request — that means RequestId
# is registered LAST and runs FIRST.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://t.me"],
    allow_origin_regex=(
        r"https://("
        r"([a-z0-9-]+\.)?wr3\.pages\.dev"
        r"|wr3(\.[a-z0-9-]+)?\.workers\.dev"
        r"|[a-z0-9-]+\.wr3\.workers\.dev"
        r")"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIdMiddleware)

app.include_router(health.router, prefix="/v1", tags=["health"])
app.include_router(scan.router, prefix="/v1/scan", tags=["scan"])
app.include_router(auth.router, prefix="/v1/auth", tags=["auth"])
app.include_router(telegram.router, prefix="/v1/tg", tags=["telegram"])
app.include_router(public.router, prefix="/v1/public", tags=["public"])
app.include_router(subscription.router, prefix="/v1/subscription", tags=["subscription"])
