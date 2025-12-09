"""Structured logging configuration for LLM Poker Arena."""

import logging
import sys
from datetime import datetime, timezone
from typing import Any


class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured log messages."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with structured fields."""
        # Base fields
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Format as key=value pairs for readability
        parts = [f"{k}={v}" for k, v in log_data.items() if v is not None]
        return " | ".join(parts)


class ContextLogger(logging.LoggerAdapter):
    """Logger adapter that supports adding context fields to log messages."""

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Process the log message and add extra fields."""
        extra = kwargs.get("extra", {})
        extra["extra_fields"] = {**self.extra, **extra.get("extra_fields", {})}
        kwargs["extra"] = extra
        return msg, kwargs


def setup_logging(
    level: int = logging.INFO,
    format_style: str = "structured",
) -> None:
    """
    Set up logging configuration for the application.

    Args:
        level: Logging level (default: INFO)
        format_style: "structured" for key=value, "simple" for standard format
    """
    root_logger = logging.getLogger("llm_poker")
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if format_style == "structured":
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)


def get_logger(name: str, **context: Any) -> ContextLogger:
    """
    Get a logger instance with optional context fields.

    Args:
        name: Logger name (usually __name__)
        **context: Context fields to include in all log messages

    Returns:
        ContextLogger instance

    Example:
        logger = get_logger(__name__, model="gpt-4o", hand_id="abc123")
        logger.info("Starting hand")  # Includes model and hand_id
    """
    base_logger = logging.getLogger(f"llm_poker.{name}")
    return ContextLogger(base_logger, context)


# Initialize logging on import
setup_logging()
