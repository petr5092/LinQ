"""Application logging configuration."""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from . import config

LOGGER_NAME = "linq"
MAX_LOG_BYTES = 5 * 1024 * 1024
LOG_BACKUPS = 3


def configure_logging(path=None, level=logging.INFO):
    log_path = path or os.path.join(config.DATA_DIR, "linq.log")
    directory = os.path.dirname(os.path.abspath(log_path))
    os.makedirs(directory, exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler = RotatingFileHandler(log_path, maxBytes=MAX_LOG_BYTES, backupCount=LOG_BACKUPS,
                                       encoding="utf-8")
    console_handler = logging.StreamHandler(sys.stdout)
    for handler in (file_handler, console_handler):
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def shutdown_logging():
    logger = logging.getLogger(LOGGER_NAME)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.flush()
        handler.close()
