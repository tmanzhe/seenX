"""Local JSON events, run correlation, counters, and timers. No network export."""

from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from time import perf_counter
from uuid import uuid4


from seenx.paths import LOG_PATH
LOGGER = logging.getLogger("seenx")
LOGGER.addHandler(logging.NullHandler())
LOGGER.propagate = False
CURRENT_RUN = ContextVar("seenx_run", default=None)
PRIVATE_FIELDS = {"query", "path", "text", "record", "embedding", "error", "message"}


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "schema_version": 1,
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
            **record.event_fields,
        }, allow_nan=False)


def configure_logging(enabled: bool = True, debug: bool = False,
                      path: Path = LOG_PATH, max_bytes: int = 1_048_576,
                      backups: int = 3) -> None:
    for handler in list(LOGGER.handlers):
        LOGGER.removeHandler(handler)
        handler.close()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=max_bytes, backupCount=backups,
                                      encoding="utf-8")
        handler.setFormatter(JsonFormatter())
    else:
        handler = logging.NullHandler()
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.DEBUG if debug else logging.INFO)


def event(name: str, level: int = logging.INFO, **fields) -> None:
    state = CURRENT_RUN.get()
    safe = {key: value for key, value in fields.items() if key not in PRIVATE_FIELDS}
    LOGGER.log(level, name, extra={"event_fields": {
        "run_id": state["id"] if state else None, **safe,
    }})


def count(name: str, amount: int = 1) -> None:
    state = CURRENT_RUN.get()
    if state is not None:
        state["counters"][name] += amount


def file_id(path: Path | str) -> str:
    state = CURRENT_RUN.get()
    salt = state["id"] if state else "unscoped"
    return hashlib.sha256(f"{salt}:{path}".encode()).hexdigest()[:16]


@contextmanager
def run_context(command: str):
    state = {"id": uuid4().hex, "counters": Counter(), "stages_ms": Counter()}
    token = CURRENT_RUN.set(state)
    started = perf_counter()
    event("run_started", command=command)
    try:
        yield state["id"]
    except BaseException as error:
        event("run_failed", level=logging.ERROR, error_type=type(error).__name__,
              duration_ms=round((perf_counter() - started) * 1000, 3),
              counters=dict(state["counters"]), stages_ms=dict(state["stages_ms"]))
        raise
    else:
        event("run_finished", duration_ms=round((perf_counter() - started) * 1000, 3),
              counters=dict(state["counters"]), stages_ms=dict(state["stages_ms"]))
    finally:
        CURRENT_RUN.reset(token)


def observed_search(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        if CURRENT_RUN.get() is not None:
            return function(*args, **kwargs)
        with run_context(function.__name__):
            return function(*args, **kwargs)
    return wrapped


@contextmanager
def stage(name: str, **fields):
    started = perf_counter()
    outcome = "ok"
    event("stage_started", level=logging.DEBUG, stage=name, **fields)
    try:
        yield
    except BaseException as error:
        outcome = "error"
        count("stage_errors")
        event("stage_failed", level=logging.ERROR, stage=name,
              error_type=type(error).__name__, **fields)
        raise
    finally:
        duration = round((perf_counter() - started) * 1000, 3)
        state = CURRENT_RUN.get()
        if state is not None:
            state["stages_ms"][name] += duration
        event("stage_finished", stage=name, outcome=outcome, duration_ms=duration, **fields)
