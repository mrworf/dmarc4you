"""Bootstrap logging with user-facing levels VERBOSE|INFO|WARN|ERROR."""

import logging
import sys

from backend.config.schema import LogLevel

_LEVEL_MAP = {
    "VERBOSE": logging.DEBUG,
    "INFO": logging.INFO,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
}


def configure_logging(log_level: LogLevel) -> None:
    """Configure root logger to stdout with given level."""
    level = _LEVEL_MAP.get(log_level, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
