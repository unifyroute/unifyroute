"""
UnifyRoute — Centralized Logging Configuration
================================================
Call `setup_logging()` once at application startup (typically in the launcher).
All other modules simply use `logging.getLogger(__name__)` as usual.
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


_CONFIGURED = False

# Default log directory relative to project root
_DEFAULT_LOG_DIR = "logs"

# Format: timestamp [LEVEL_CHAR] logger.name — message
_LOG_FORMAT = "%(asctime)s [%(levelname).1s] %(name)s — %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    log_dir: str | None = None,
    level: str | None = None,
) -> None:
    """
    Configure application-wide logging.

    - Console handler (stdout) for all logs at the configured level.
    - Rotating file handler  ``logs/app.log``  for application logs.
    - Rotating file handler  ``logs/access.log``  for uvicorn access logs only.
    - Noisy third-party libraries suppressed to WARNING.

    Safe to call multiple times — repeated calls are no-ops.

    Args:
        log_dir:  Directory for log files.  Falls back to ``LOG_DIR`` env var,
                  then ``logs/`` relative to the working directory.
        level:    Root log level.  Falls back to ``LOG_LEVEL`` env var,
                  then ``INFO``.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    # ── Resolve settings ──────────────────────────────────────────────
    log_dir = log_dir or os.environ.get("LOG_DIR", _DEFAULT_LOG_DIR)
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    level_name = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    log_level = getattr(logging, level_name, logging.INFO)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)

    # ── Console handler (stdout) — only when running interactively ──────
    # When the CLI daemonizes the server, stdout is redirected to app.log.
    # Adding a console handler in that case would duplicate every line in
    # the same file (once from the file handler, once from console → file).
    if sys.stdout.isatty():
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)

    # ── Application file handler (logs/app.log) ───────────────────────
    app_file_handler = RotatingFileHandler(
        str(log_path / "app.log"),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    app_file_handler.setFormatter(formatter)
    app_file_handler.setLevel(log_level)

    # ── Access file handler (logs/access.log) ─────────────────────────
    access_file_handler = RotatingFileHandler(
        str(log_path / "access.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    access_file_handler.setFormatter(formatter)
    access_file_handler.setLevel(logging.INFO)

    # ── Root logger — receives everything via propagation ─────────────
    root = logging.getLogger()
    root.setLevel(log_level)
    # Remove any pre-existing handlers (uvicorn/litellm may add their own)
    root.handlers.clear()
    if sys.stdout.isatty():
        root.addHandler(console_handler)
    root.addHandler(app_file_handler)

    # ── Access logs go to their own file only ─────────────────────────
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers.clear()
    access_logger.addHandler(access_file_handler)
    access_logger.propagate = False  # don't clutter the app log

    # ── Suppress noisy third-party loggers ────────────────────────────
    _noisy_loggers = [
        "apscheduler",
        "apscheduler.executors",
        "apscheduler.executors.default",
        "apscheduler.scheduler",
        "httpx",
        "httpcore",
        "hpack",
        "watchdog",
        "litellm",
        "openai",
        "filelock",
    ]
    for name in _noisy_loggers:
        logging.getLogger(name).setLevel(logging.WARNING)

    # ── Prevent uvicorn's default handlers from duplicating entries ────
    # When the CLI redirects stdout → app.log, uvicorn's own handlers
    # write to the same destination as the root file handler. Clear them
    # and let propagation route through our single file handler instead.
    for uvi_name in ("uvicorn", "uvicorn.error"):
        uvi_logger = logging.getLogger(uvi_name)
        uvi_logger.handlers.clear()
        uvi_logger.propagate = True

    # ── Confirm ───────────────────────────────────────────────────────
    logger = logging.getLogger("unifyroute.logging")
    logger.info(
        "Logging configured: level=%s, app_log=%s, access_log=%s",
        level_name,
        log_path / "app.log",
        log_path / "access.log",
    )
