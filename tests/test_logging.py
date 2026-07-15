import logging

from app.core.logging import configure_logging


def test_configure_logging_suppresses_http_client_request_urls() -> None:
    loggers = [logging.getLogger(name) for name in ("httpx", "httpcore")]
    original_levels = [logger.level for logger in loggers]
    try:
        configure_logging("INFO")
        assert all(logger.level == logging.WARNING for logger in loggers)
    finally:
        for logger, level in zip(loggers, original_levels, strict=True):
            logger.setLevel(level)
