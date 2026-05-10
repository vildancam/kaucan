from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .config import CHATBOT_LOG_PATH, ensure_runtime_dirs


_LOGGER_READY = False


def configure_logging() -> None:
    global _LOGGER_READY

    if _LOGGER_READY:
        return

    ensure_runtime_dirs()
    handler = RotatingFileHandler(
        CHATBOT_LOG_PATH,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    handler.setFormatter(formatter)

    logger = logging.getLogger("kau_can_bot")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    _LOGGER_READY = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(f"kau_can_bot.{name}")
