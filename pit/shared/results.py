"""Single results-JSON contract shared by the Convert and Import tools.

Both tools emit the same schema, but each writes its OWN file (passed as
`filename`) — they never share a results file. This keeps the two tools
fully decoupled.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

_KEY_ORDER = ["status", "message", "timestamp", "output_path", "log_file", "summary_file"]


@dataclass
class Result:
    status: str
    message: str
    timestamp: str
    output_path: Optional[str] = None
    log_file: Optional[str] = None
    summary_file: Optional[str] = None

    @classmethod
    def success(cls, message: str, *, output_path: Optional[str] = None,
                summary_file: Optional[str] = None, log_file: Optional[str] = None) -> "Result":
        return cls(
            status="success",
            message=message,
            timestamp=datetime.now().isoformat(),
            output_path=output_path,
            log_file=log_file,
            summary_file=summary_file,
        )

    @classmethod
    def error(cls, message: str, *, log_file: Optional[str] = None) -> "Result":
        return cls(
            status="error",
            message=message,
            timestamp=datetime.now().isoformat(),
            log_file=log_file,
        )

    def to_dict(self) -> dict:
        return {key: getattr(self, key) for key in _KEY_ORDER}


def write_results(result: Result, out_dir: str, filename: str) -> str:
    """Print JSON to stdout (for Excel capture) and write it to out_dir/filename.

    Returns the intended file path. Never raises — a write failure is logged.
    """
    payload = result.to_dict()
    print(json.dumps(payload))

    path = os.path.join(out_dir, filename)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception as exc:  # non-critical: Excel also reads stdout
        logger.error("Failed to write results JSON to %s: %s", path, exc)
    return path
