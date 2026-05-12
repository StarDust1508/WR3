from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wr3_api.config import get_settings
from wr3_api.routes import auth, health, scan, telegram

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/v1", tags=["health"])
app.include_router(scan.router, prefix="/v1/scan", tags=["scan"])
app.include_router(auth.router, prefix="/v1/auth", tags=["auth"])
app.include_router(telegram.router, prefix="/v1/tg", tags=["telegram"])
