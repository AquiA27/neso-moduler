"""
Structured logging configuration using structlog.

Provides:
- JSON-formatted logs for production
- Colored console logs for development
- Request ID tracking
- Automatic exception logging
- Performance metrics
"""

import logging
import sys
import os
from typing import Any, Dict
import structlog
from structlog.types import EventDict, Processor


def add_app_context(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """Add application context to log entries"""
    event_dict["app"] = os.getenv("APP_NAME", "Neso Asistan API")
    event_dict["env"] = os.getenv("ENV", "dev")
    return event_dict


def add_severity(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """Add severity level for structured logging"""
    if method_name == "warn":
        method_name = "warning"
    event_dict["severity"] = method_name.upper()
    return event_dict


def censor_sensitive_data(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """Censor sensitive data in logs"""
    sensitive_keys = ["password", "token", "secret", "api_key", "authorization"]

    def _censor_dict(d: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively censor dictionary"""
        result = {}
        for key, value in d.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                result[key] = "***CENSORED***"
            elif isinstance(value, dict):
                result[key] = _censor_dict(value)
            elif isinstance(value, list):
                result[key] = [_censor_dict(item) if isinstance(item, dict) else item for item in value]
            else:
                result[key] = value
        return result

    return _censor_dict(event_dict)


def setup_logging(log_level: str = None, json_logs: bool = None) -> None:
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: Whether to output JSON logs (True for production)
    """
    # Get config from environment if not provided
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    if json_logs is None:
        # JSON logs in production, colored console in dev
        json_logs = os.getenv("ENV", "dev") == "prod"

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level),
    )

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("databases").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Shared processors for all configurations
    shared_processors: list[Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        add_severity,
        add_app_context,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        censor_sensitive_data,
    ]

    if json_logs:
        # Production: JSON logs
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Colored console logs
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            ),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


# Performance logging helpers
class LogPerformance:
    """Context manager for logging function performance"""

    def __init__(self, logger: structlog.stdlib.BoundLogger, operation: str):
        self.logger = logger
        self.operation = operation
        self.start_time = None

    def __enter__(self):
        import time
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        duration = time.time() - self.start_time
        if exc_type:
            self.logger.error(
                f"{self.operation} failed",
                duration_seconds=duration,
                exc_info=True,
            )
        else:
            self.logger.info(
                f"{self.operation} completed",
                duration_seconds=duration,
            )
        return False


# Example usage:
# logger = get_logger(__name__)
# logger.info("user_login", username="admin", ip="127.0.0.1")
# with LogPerformance(logger, "database_query"):
#     # ... your code ...
