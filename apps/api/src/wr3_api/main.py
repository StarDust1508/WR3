from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wr3_api.config import get_settings
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
#   - https://*.pages.dev — Cloudflare Pages deployments of the Mini App
#   - https://t.me — Telegram WebApp iframe origin
# Using `allow_origin_regex` so we cover preview deploys like
# https://abc123.wr3.pages.dev that get generated for every CF Pages branch.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://t.me"],
    allow_origin_regex=r"https://([a-z0-9-]+\.)?wr3\.pages\.dev",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/v1", tags=["health"])
app.include_router(scan.router, prefix="/v1/scan", tags=["scan"])
app.include_router(auth.router, prefix="/v1/auth", tags=["auth"])
app.include_router(telegram.router, prefix="/v1/tg", tags=["telegram"])
app.include_router(public.router, prefix="/v1/public", tags=["public"])
app.include_router(subscription.router, prefix="/v1/subscription", tags=["subscription"])
