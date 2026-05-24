"""Unit tests for worker.app.logger — structured logging standard."""
from __future__ import annotations

import logging

import pytest

from worker.app.logger import RunLoggerAdapter, configure_logging, get_logger


class TestGetLogger:
    """get_logger factory function."""

    def test_returns_run_logger_adapter(self):
        log = get_logger("test.module")
        assert isinstance(log, RunLoggerAdapter)

    def test_run_id_truncated_to_8_chars(self):
        run_id = "abcdef1234567890"  # 16-char string
        log = get_logger("test.module", run_id=run_id)
        extra = log.extra
        assert extra["run_id"] == "abcdef12"  # first 8

    def test_none_run_id_uses_placeholder(self):
        log = get_logger("test.module", run_id=None)
        assert log.extra["run_id"] == "--------"

    def test_uuid_run_id_truncated_to_8_chars(self):
        import uuid

        uid = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        log = get_logger("test.module", run_id=uid)
        assert log.extra["run_id"] == "12345678"

    def test_short_run_id_used_as_is(self):
        log = get_logger("test.module", run_id="abc")
        assert log.extra["run_id"] == "abc"

    def test_logger_name_preserved(self):
        log = get_logger("my.special.module")
        assert log.logger.name == "my.special.module"


class TestConfigureLogging:
    """configure_logging setup function."""

    def test_idempotent_multiple_calls(self):
        """Calling configure_logging twice should not raise."""
        # Both calls should complete without exception
        configure_logging(level="WARNING")
        configure_logging(level="WARNING")

    def test_sets_log_level_from_string(self):
        configure_logging(level="DEBUG")
        root = logging.getLogger()
        assert root.level == logging.DEBUG

        configure_logging(level="INFO")
        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_quiet_loggers_suppressed(self):
        configure_logging(level="INFO")
        for name in ("httpx", "httpcore", "urllib3"):
            lg = logging.getLogger(name)
            assert lg.level == logging.WARNING


class TestRunLoggerAdapterProcess:
    """RunLoggerAdapter.process injects run_id into every log record."""

    def test_process_injects_run_id(self):
        log = get_logger("test", run_id="deadbeef")
        msg, kwargs = log.process("hello", {})
        assert msg == "hello"
        assert kwargs["extra"]["run_id"] == "deadbeef"

    def test_process_preserves_existing_extra(self):
        log = get_logger("test", run_id="cafebabe")
        msg, kwargs = log.process("hi", {"extra": {"other_key": "value"}})
        assert kwargs["extra"]["run_id"] == "cafebabe"
        assert kwargs["extra"]["other_key"] == "value"
