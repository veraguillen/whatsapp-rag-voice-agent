"""FastAPI entrypoint wiring the WhatsApp webhook router."""

from __future__ import annotations

import logging

from fastapi import FastAPI

from app.routers.whatsapp import router as whatsapp_router

logging.basicConfig(level=logging.INFO)


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""

    application = FastAPI()
    application.include_router(whatsapp_router)
    return application


app = create_app()

__all__ = ["app", "create_app"]
