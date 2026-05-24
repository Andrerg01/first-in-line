"""Structured logging helpers for the worker.

Standard usage
--------------
At the top of any worker module::

    from worker.app.logger import get_logger
    log = get_logger(__name__)

Within a function that has a ``run_id``::

    log = get_logger(__name__, run_id=run_id)
    log.info("Searching: %r", query)
    # emits: 2026-05-24 01:00:00,000 INFO     [run:a1b2c3d4] worker.app.pipeline Searching: 'grand opening'

``get_logger`` returns a ``logging.LoggerAdapter`` whose ``extra`` dict is
merged into the ``LogRecord``.  This means ``run_id`` is available in custom
``Formatter`` patterns.  When no ``run_id`` is supplied the placeholder
``"--------"`` is used so column widths stay constant.

configure_logging()
-------------------
Call once from the CLI entry point before any logging takes place.  It sets
the root level, attaches a ``StreamHandler`` with the project-standard format,
and suppresses noisy third-party loggers.

Logging levels by component
----------------------------
* ``ERROR``   – unrecoverable failures that abort a run or a step.
* ``WARNING`` – recoverable problems (duplicate skipped, fetch 4xx, rate limit).
* ``INFO``    – normal lifecycle events (run created, query started, doc stored).
* ``DEBUG``   – verbose internals (HTTP request details, timing breakdown).
"""

from __future__ import annotations

import logging
import os
import uuid

_DEFAULT_FORMAT = (
    "%(asctime)s %(levelname)-8s [run:%(run_id)8s] %(name)s %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Loggers we want to quieten in production to avoid noise.
_QUIET_LOGGERS = (
    "httpx",
    "httpcore",
    "urllib3",
)


class RunLoggerAdapter(logging.LoggerAdapter):
    """LoggerAdapter that injects ``run_id`` into every log record.

    ``extra["run_id"]`` is a short hex string (8 chars) derived from the
    UUID supplied at construction time.  If no UUID is supplied the value
    ``"--------"`` is used as a constant-width placeholder.
    """

    def process(
        self, msg: object, kwargs: dict
    ) -> tuple[object, dict]:
        """Merge run_id into the extra dict before the record is emitted."""
        extra = kwargs.setdefault("extra", {})
        extra.setdefault("run_id", self.extra.get("run_id", "--------"))
        return msg, kwargs


def get_logger(
    name: str,
    *,
    run_id: uuid.UUID | str | None = None,
) -> RunLoggerAdapter:
    """Return a ``RunLoggerAdapter`` for *name* that stamps every record with *run_id*.

    Args:
        name: Logger name — typically ``__name__`` of the calling module.
        run_id: UUID of the current discovery run.  When ``None`` the
            placeholder ``"--------"`` is used.

    Returns:
        A ``RunLoggerAdapter`` wrapping the standard library logger for *name*.
    """
    base = logging.getLogger(name)
    short_id = str(run_id)[:8] if run_id is not None else "--------"
    return RunLoggerAdapter(base, {"run_id": short_id})


def configure_logging(level: str | None = None) -> None:
    """Configure root logging for the worker process.

    This should be called once from the CLI entry point before any log
    messages are emitted.  Subsequent calls are idempotent (handler is not
    added twice).

    Args:
        level: Log level string (``"DEBUG"``, ``"INFO"``, ``"WARNING"``,
            ``"ERROR"``).  Falls back to the ``LOG_LEVEL`` environment
            variable and then to ``"INFO"``.
    """
    resolved_level = (
        level
        or os.environ.get("LOG_LEVEL", "INFO")
    ).upper()

    root = logging.getLogger()
    root.setLevel(resolved_level)

    # Avoid duplicate handlers if called more than once (e.g., in tests).
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(fmt=_DEFAULT_FORMAT, datefmt=_DATE_FORMAT)
        )
        root.addHandler(handler)

    # Suppress noisy library loggers unless we're at DEBUG.
    if resolved_level != "DEBUG":
        for name in _QUIET_LOGGERS:
            logging.getLogger(name).setLevel(logging.WARNING)
