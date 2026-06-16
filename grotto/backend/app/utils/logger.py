"""
logger.py

Logging utilities with colored console output and structured JSON file logging.

Provides a unified logging setup with dual output formats:
- Console: Colored output with ANSI color codes for easy reading
- Files: Structured JSON logs with automatic rotation (10MB max, 5 backups)

Separate error logs are created automatically for ERROR and CRITICAL level messages.

Example:
    from app.utils.logger import setup_logger

    # Create a logger for your module
    logger = setup_logger(__name__)

    # Use standard logging methods
    logger.debug("Debugging information")
    logger.info("General information")
    logger.warning("Warning message")
    logger.error("Error occurred", exc_info=True)

    # Logs appear in console with colors and in JSON files
"""

import json
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import CURRENT_LOGGING_CONFIG


class CustomFormatter(logging.Formatter):
    """
    Custom formatter with ANSI color codes for console output.

    Applies different colors to log messages based on severity level:
    - DEBUG: Grey
    - INFO: Blue
    - WARNING: Yellow
    - ERROR: Red
    - CRITICAL: Bold Red

    The colored output only appears in console; file logs use JSON format.
    """

    # Color codes
    grey = "\x1b[38;21m"
    blue = "\x1b[38;5;39m"
    yellow = "\x1b[38;5;226m"
    red = "\x1b[38;5;196m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    format_str = (
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    )

    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: blue + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset,
    }

    def format(self, record):
        """
        Format a log record with appropriate color coding.

        Args:
            record: LogRecord instance to format.

        Returns:
            Formatted and colored log string.
        """
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured file logging.

    Outputs log records as JSON objects with consistent structure:
    - timestamp: ISO 8601 format
    - level: Log level name (DEBUG, INFO, etc.)
    - name: Logger name
    - message: Log message
    - module: Module name
    - function: Function name
    - line: Line number
    - exception: Stack trace (if exception occurred)

    Makes logs easily parseable by log aggregation tools.
    """

    def format(self, record):
        """
        Format a log record as a JSON string.

        Args:
            record: LogRecord instance to format.

        Returns:
            JSON-formatted log string.
        """
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record)


def setup_logger(
    name: str,
    log_level: str = CURRENT_LOGGING_CONFIG["log_level"],
    log_dir: Path = CURRENT_LOGGING_CONFIG["log_dir"],
) -> logging.Logger:
    """
    Set up a logger with both console and file handlers.

    Creates a logger with:
    - Colored console output using CustomFormatter
    - JSON file logging with automatic rotation (10MB max, 5 backups)
    - Separate error log file for ERROR and CRITICAL messages

    Args:
        name: Name of the logger (typically __name__ from calling module).
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                   Defaults to value from application config.
        log_dir: Directory for log files. If None, only console logging is used.
                Defaults to value from application config.

    Returns:
        Configured Logger instance ready for use.

    Example:
        >>> logger = setup_logger(__name__)
        >>> logger.info("Application started")
        >>> logger.error("Something went wrong", exc_info=True)

        # Creates files:
        # - logs/dev/__main__.log (all logs)
        # - logs/dev/__main__.error.log (errors only)
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    logger.handlers = []

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(CustomFormatter())
    logger.addHandler(console_handler)

    # File Handler (if log_dir is provided)
    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        # Regular log file
        file_handler = RotatingFileHandler(
            filename=log_dir / f"{name}.log",
            maxBytes=10485760,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(JSONFormatter())
        logger.addHandler(file_handler)

        # Error log file
        error_handler = RotatingFileHandler(
            filename=log_dir / f"{name}.error.log",
            maxBytes=10485760,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(JSONFormatter())
        logger.addHandler(error_handler)

    return logger
