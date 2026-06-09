from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

from app.core.config import settings
from app.core.database import init_db

logger = structlog.get_logger()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    if not api_key or api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting NYC Apartment Searcher")
    await init_db()

    from app.jobs.scheduler import start_scheduler, stop_scheduler
    scheduler = await start_scheduler()

    # Start Telegram bot if configured
    telegram_app = None
    if settings.telegram_bot_token:
        try:
            from app.services.telegram_service import create_telegram_app
            telegram_app = await create_telegram_app()
            logger.info("Telegram bot started")
        except Exception as e:
            logger.error("Failed to start Telegram bot", error=str(e))

    yield

    if telegram_app:
        await telegram_app.stop()
    stop_scheduler(scheduler)
    logger.info("Shutting down")


app = FastAPI(title="NYC Apartment Searcher", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.leads import router as leads_router
from app.api.config_api import router as config_router
from app.api.stats import router as stats_router
from app.api.webhooks import router as webhooks_router

app.include_router(leads_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])
app.include_router(config_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])
app.include_router(stats_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])
app.include_router(webhooks_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
