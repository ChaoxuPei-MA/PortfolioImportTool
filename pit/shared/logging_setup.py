"""Centralized logging configuration for both tools."""
from __future__ import annotations

import logging
import sys

_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"


def setup_logging(log_path: str) -> str:
    root = logging.getLogger()
    # Idempotent: remove handlers from any prior setup in this process.
    for handler in list(root.handlers):
        root.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    formatter = logging.Formatter(_FORMAT)

    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)
    return log_path
