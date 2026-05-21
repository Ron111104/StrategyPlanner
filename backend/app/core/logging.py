"""Structured logging configuration for ZQ Strategy Planning Platform.

Uses structlog for structured, context-rich logging with JSON output
for production and colored console output for development.
"""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structlog and stdlib logging for the application.

    In production (log_level != DEBUG), output is JSON for structured log ingestion.
    In development (DEBUG), output is human-readable colored console.

    Args:
        log_level: Logging level string (e.g. 'DEBUG', 'INFO', 'WARNING').
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    is_development = numeric_level == logging.DEBUG

    # Shared processors for all environments
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if is_development:
        # Development: colored console output
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(
            colors=True,
        )
    else:
        # Production: JSON output
        shared_processors.append(
            structlog.processors.format_exc_info,
        )
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to use structlog's formatter
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(numeric_level)

    # Suppress noisy third-party loggers
    for noisy_logger in ("httpx", "httpcore", "uvicorn.access", "asyncio"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a named structlog bound logger.

    Args:
        name: Logger name (typically __name__ of the calling module).

    Returns:
        A bound structlog logger instance.
    """
    return structlog.get_logger(name)
