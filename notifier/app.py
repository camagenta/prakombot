"""FastAPI application factory for the notifier service.

Wires the webhook and health routes into a single FastAPI app.
"""
from fastapi import FastAPI

from .routes.health import handle_healthz
from .routes.webhook import handle_form_submit


def create_app() -> FastAPI:
    app = FastAPI(title="notifier", version="0.1.0")
    app.add_api_route("/healthz", handle_healthz, methods=["GET"])
    app.add_api_route("/webhook/form", handle_form_submit, methods=["POST"])
    return app


app = create_app()
