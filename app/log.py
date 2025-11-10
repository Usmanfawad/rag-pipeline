"""
Logging configuration for the RAG Pipeline server.

This module provides centralized logging configuration with:
- Console and file output
- Rotating file handlers to manage log file sizes
- Structured formatting with timestamps
- Different log levels for development and production
- Request/response logging for API endpoints
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime
from typing import Optional


# Create logs directory if it doesn't exist
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

# Log file paths
ACCESS_LOG_FILE = LOGS_DIR / "access.log"
ERROR_LOG_FILE = LOGS_DIR / "error.log"
APP_LOG_FILE = LOGS_DIR / "app.log"

# Log format
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support for console output."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record):
        # Add color to levelname
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        
        return super().format(record)


def setup_logger(
    name: str,
    level: int = logging.INFO,
    log_to_file: bool = True,
    log_to_console: bool = True,
    colored_console: bool = True
) -> logging.Logger:
    """
    Set up a logger with console and/or file handlers.
    
    Args:
        name: Name of the logger
        level: Logging level (default: INFO)
        log_to_file: Whether to log to file (default: True)
        log_to_console: Whether to log to console (default: True)
        colored_console: Whether to use colored output in console (default: True)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        
        if colored_console:
            console_formatter = ColoredFormatter(LOG_FORMAT, datefmt=DATE_FORMAT)
        else:
            console_formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
        
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    # File handler with rotation
    if log_to_file:
        file_handler = RotatingFileHandler(
            APP_LOG_FILE,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


def setup_access_logger() -> logging.Logger:
    """
    Set up logger specifically for HTTP access logs.
    
    Returns:
        Configured access logger
    """
    logger = logging.getLogger("access")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    
    # Access log file handler
    access_handler = RotatingFileHandler(
        ACCESS_LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    access_handler.setLevel(logging.INFO)
    
    # Simplified format for access logs
    access_format = "%(asctime)s | %(message)s"
    access_formatter = logging.Formatter(access_format, datefmt=DATE_FORMAT)
    access_handler.setFormatter(access_formatter)
    logger.addHandler(access_handler)
    
    # Also log to console with color
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = ColoredFormatter(access_format, datefmt=DATE_FORMAT)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    logger.propagate = False
    return logger


def setup_error_logger() -> logging.Logger:
    """
    Set up logger specifically for errors and critical issues.
    
    Returns:
        Configured error logger
    """
    logger = logging.getLogger("error")
    logger.setLevel(logging.ERROR)
    logger.handlers.clear()
    
    # Error log file handler
    error_handler = RotatingFileHandler(
        ERROR_LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    error_handler.setFormatter(error_formatter)
    logger.addHandler(error_handler)
    
    # Also log errors to console
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.ERROR)
    console_formatter = ColoredFormatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    logger.propagate = False
    return logger


def configure_uvicorn_logging():
    """Configure uvicorn logging to use our logging setup."""
    # Configure uvicorn's access logger
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.handlers.clear()
    
    access_handler = RotatingFileHandler(
        ACCESS_LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    access_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | ACCESS | %(message)s",
            datefmt=DATE_FORMAT
        )
    )
    uvicorn_access.addHandler(access_handler)
    
    # Configure uvicorn's error logger
    uvicorn_error = logging.getLogger("uvicorn.error")
    uvicorn_error.handlers.clear()
    
    error_handler = RotatingFileHandler(
        ERROR_LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setFormatter(
        logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    )
    uvicorn_error.addHandler(error_handler)


# Initialize loggers
app_logger = setup_logger("rag_pipeline", level=logging.INFO)
access_logger = setup_access_logger()
error_logger = setup_error_logger()


def log_request(method: str, path: str, status_code: int, duration_ms: float, client_ip: Optional[str] = None):
    """
    Log an HTTP request.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        path: Request path
        status_code: Response status code
        duration_ms: Request duration in milliseconds
        client_ip: Client IP address (optional)
    """
    client_info = f"[{client_ip}]" if client_ip else ""
    message = f"{method} {path} -> {status_code} ({duration_ms:.2f}ms) {client_info}"
    
    if status_code >= 500:
        error_logger.error(message)
    elif status_code >= 400:
        access_logger.warning(message)
    else:
        access_logger.info(message)


def log_startup():
    """Log server startup information."""
    app_logger.info("=" * 80)
    app_logger.info("RAG Pipeline Server Starting")
    app_logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    app_logger.info(f"Logs Directory: {LOGS_DIR.absolute()}")
    app_logger.info("=" * 80)


def log_shutdown():
    """Log server shutdown information."""
    app_logger.info("=" * 80)
    app_logger.info("RAG Pipeline Server Shutting Down")
    app_logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    app_logger.info("=" * 80)


# Configure uvicorn logging on module import
configure_uvicorn_logging()


# Example usage for other modules
def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Module name (typically __name__)
    
    Returns:
        Logger instance
    """
    return setup_logger(name, level=logging.INFO)

