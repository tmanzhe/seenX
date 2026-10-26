"""Bounded JSON-lines transport for the trusted local read-only engine contract."""

import argparse
from pathlib import Path
import sqlite3
import sys

from seenx.catalog import Catalog
from seenx.engine_contract import Engine, MAX_REQUEST_BYTES
from seenx.observability import configure_logging, event
from seenx.paths import LIBRARY_ROOT


def serve(engine: Engine, incoming, outgoing) -> None:
    while True:
        frame = incoming.readline(MAX_REQUEST_BYTES + 1)
        if not frame:
            return
        if len(frame) > MAX_REQUEST_BYTES:
            # Drain only this overlong frame; preserve the next request boundary.
            chunk = frame
            while chunk and not chunk.endswith(b"\n"):
                chunk = incoming.readline(MAX_REQUEST_BYTES + 1)
            response = engine.handle(frame)
        elif not frame.strip():
            continue
        else:
            response = engine.handle(frame)
        outgoing.write(response + b"\n")
        outgoing.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, default=LIBRARY_ROOT)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--no-log", action="store_true")
    args = parser.parse_args()
    try:
        configure_logging(enabled=not args.no_log, debug=args.debug)
        with Catalog(args.library) as catalog:
            event("engine_started", protocol_version=1)
            serve(Engine(catalog), sys.stdin.buffer, sys.stdout.buffer)
            event("engine_stopped")
    except BrokenPipeError:
        return
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
        parser.exit(1, f"Engine could not start or continue: {type(error).__name__}\n")


if __name__ == "__main__":
    main()
