"""ASGI entrypoint: ``uvicorn evalplatform.api.main:app``."""

from evalplatform.api.app import create_app

app = create_app()
