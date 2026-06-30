import logging
import os

import pytest

from pit.shared.logging_setup import setup_logging


@pytest.fixture(autouse=True)
def _restore_root_logger():
    yield
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass


def test_setup_creates_log_file_and_writes(tmp_path):
    log_path = str(tmp_path / "pit.log")
    returned = setup_logging(log_path)
    assert returned == log_path
    logging.getLogger("x").info("hello-line")
    logging.shutdown()
    assert os.path.exists(log_path)
    with open(log_path, encoding="utf-8") as f:
        content = f.read()
    assert "hello-line" in content
    assert " - INFO - " in content


def test_setup_is_idempotent_no_duplicate_handlers(tmp_path):
    log_path = str(tmp_path / "pit.log")
    setup_logging(log_path)
    setup_logging(log_path)
    file_handlers = [h for h in logging.getLogger().handlers
                     if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 1
