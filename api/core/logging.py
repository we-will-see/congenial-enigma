import logging
import sys

import structlog

from api.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(stream=sys.stdout, level=settings.log_level.upper(), format="%(message)s")
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if settings.log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(settings.log_level.upper())),
        cache_logger_on_first_use=True,
    )
