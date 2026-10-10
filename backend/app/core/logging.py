"""app/core/logging.py — Structured JSON logging via structlog."""
from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

_PII_KEYS = frozenset(
    {
        "name", "full_name", "aadhaar", "pan", "email", "phone",
        "mobile", "address", "dob", "ip_address",
    }
)


def _drop_pii(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Processor: strip any accidental PII keys from log records."""
    for key in list(event_dict.keys()):
        if key.lower() in _PII_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict


def configure_logging(log_level: str = "INFO", *, json_logs: bool = True) -> None:
    """Configure structlog for structured JSON output.

    Call once at application startup.  In tests call with json_logs=False
    for human-readable output.
    """
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        _drop_pii,
    ]

    if json_logs:
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level.upper())

    # Quieten noisy libraries
    for noisy in ("uvicorn.access", "asyncio", "botocore", "aiobotocore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    return structlog.get_logger(name)  # type: ignore[return-value]
