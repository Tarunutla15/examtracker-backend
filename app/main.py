import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.ocr import router as ocr_router
from app.core.config import get_settings
from app.core.logging import configure_logging


configure_logging()
logger = logging.getLogger("examtracker.ocr")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="ExamTracker OCR API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(ocr_router)
    logger.info("ExamTracker OCR API initialized with provider=%s", settings.ocr_provider)
    return app


app = create_app()
