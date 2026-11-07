"""Logging configuration for Railway Passenger Help Desk."""

import logging
import re
import sys
from pathlib import Path
from helpdesk.config import config


class SensitiveDataFilter(logging.Filter):
    """Filter that masks API keys and sensitive tokens in log records."""

    PATTERNS = [
        (re.compile(r"AIza[0-9A-Za-z-_]{35}"), "***REDACTED_API_KEY***"),
        (re.compile(r"(api[_-]?key\s*[:=]\s*)[^\s,;]+", re.IGNORECASE), r"\1***REDACTED***"),
        (re.compile(r"(token\s*[:=]\s*)[^\s,;]+", re.IGNORECASE), r"\1***REDACTED***"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, repl in self.PATTERNS:
                record.msg = pattern.sub(repl, record.msg)
        if record.args:
            args_list = list(record.args) if isinstance(record.args, tuple) else record.args
            if isinstance(args_list, list):
                for i, arg in enumerate(args_list):
                    if isinstance(arg, str):
                        for pattern, repl in self.PATTERNS:
                            args_list[i] = pattern.sub(repl, arg)
                record.args = tuple(args_list)
        return True


def setup_logger(name: str = "helpdesk", log_file: str = "helpdesk.log") -> logging.Logger:
    """Set up and return a configured logger."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    log_path = config.logs_dir / log_file

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    mask_filter = SensitiveDataFilter()
    file_handler.addFilter(mask_filter)
    console_handler.addFilter(mask_filter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


logger = setup_logger()
