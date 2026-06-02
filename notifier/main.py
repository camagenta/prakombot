"""Uvicorn entrypoint for the notifier service.

Validates config before starting so we fail fast on missing secrets.
"""
import logging
import sys

from .config import Config
from .app import app


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        cfg = Config()
        cfg.validate()
    except ValueError as e:
        print(f"Config validation failed: {e}", file=sys.stderr)
        return 1

    import uvicorn
    uvicorn.run(
        app,
        host=cfg.webhook_host,
        port=cfg.webhook_port,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
