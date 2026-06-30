from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.config import settings
from app.database import init_db
from app.utils.logger import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting VPN Reseller Platform API")
    await init_db()
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="VPN Reseller Management Platform",
    description="Enterprise VPN Reseller Platform with 3x-ui Integration",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_exception", path=request.url.path)
    return JSONResponse(status_code=500, content={"detail": "خطای داخلی سرور"})


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.APP_NAME}
