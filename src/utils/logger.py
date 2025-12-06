"""
Unified logging for the entire pipeline.

All components (ETL, enrichment, export, scripts) use the same logger
to create a cohesive audit trail in a single log file.
"""

import logging
import sys
from pathlib import Path


def get_logger(name: str, log_file: str = "logs/workflow.log", mode: str = 'a') -> logging.Logger:
    """
    Get a unified logger for any pipeline component.

    Logs to both console and log file for real-time monitoring
    and persistent audit trail.

    Args:
        name: Logger name (typically __name__)
        log_file: Path to log file
        mode: File mode - 'a' to append, 'w' to overwrite

    Returns:
        Configured logger instance
    """
    log_path = Path(log_file)
    log_path.parent.mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler = logging.FileHandler(log_file, mode=mode)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
