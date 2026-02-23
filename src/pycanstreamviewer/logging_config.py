"""Dual logging setup: console + file."""

import logging
import os
from datetime import datetime

from .constants import LOG_FORMAT, LOG_DATE_FORMAT


def setup_logging(log_dir: str | None = None) -> logging.Logger:
    """Configure root logger with console handler and optional file handler.

    Args:
        log_dir: Directory for log files. If None, only console logging is set up.

    Returns:
        The root logger instance.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Prevent duplicate handlers on repeated calls (e.g., during testing)
    if logger.handlers:
        return logger

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_dir is not None:
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_path = os.path.join(log_dir, f"pycanstreamviewer_{timestamp}.log")
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
