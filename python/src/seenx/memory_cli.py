"""Import an image and save durable notes against its immutable revision."""

import argparse
import json
from pathlib import Path
import sqlite3
import sys

from PIL.Image import DecompressionBombError

from seenx.catalog import Catalog
from seenx.observability import configure_logging, run_context, stage
from seenx.paths import LIBRARY_ROOT


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, default=LIBRARY_ROOT)
    parser.add_argument("--no-log", action="store_true")
    parser.add_argument("--debug", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    importer = commands.add_parser("import", help="Preserve an image revision; leave its source untouched")
    importer.add_argument("file", type=Path)
    commands.add_parser("list", help="List saved assets and annotation counts")
    getter = commands.add_parser("get", help="Fetch a memory, annotations, and verified snapshot reference")
    getter.add_argument("asset_id")
    getter.add_argument("--revision", help="Fetch an older revision rather than the current one")
    note = commands.add_parser("note", help="Save user-authored context against an image revision")
    note.add_argument("revision_id")
    note.add_argument("--note", default="")
    note.add_argument("--selected-text", default="")
    target = note.add_mutually_exclusive_group()
    target.add_argument("--region", type=float, nargs=4, metavar=("X", "Y", "WIDTH", "HEIGHT"))
    target.add_argument("--point", type=float, nargs=2, metavar=("X", "Y"))
    edit = commands.add_parser("edit", help="Edit note/selected text, preserving its ID and target")
    edit.add_argument("annotation_id")
    edit.add_argument("--note")
    edit.add_argument("--selected-text")
    delete_note = commands.add_parser("delete-note", help="Remove a note and its target; preserve the image")
    delete_note.add_argument("annotation_id")
    remove = commands.add_parser("remove", help="Remove a memory's catalog records; preserve original files")
    remove.add_argument("asset_id")
    args = parser.parse_args()
    try:
        configure_logging(enabled=not args.no_log, debug=args.debug)
        with run_context("memory") as run_id, stage("catalog_operation", operation=args.command):
            print(f"Run ID: {run_id}", file=sys.stderr)
            with Catalog(args.library) as catalog:
                if args.command == "import":
                    result = catalog.import_image(args.file)
                elif args.command == "list":
                    result = catalog.list_memories()
                elif args.command == "get":
                    result = catalog.get_memory(args.asset_id, args.revision)
                elif args.command == "note":
                    result = catalog.add_note(args.revision_id, args.note, args.selected_text, args.region, args.point)
                elif args.command == "edit":
                    if args.note is None and args.selected_text is None:
                        raise ValueError("Provide --note or --selected-text")
                    catalog.edit_note(args.annotation_id, args.note, args.selected_text)
                    result = {"annotation_id": args.annotation_id, "updated": True}
                elif args.command == "delete-note":
                    result = {"removed": catalog.delete_note(args.annotation_id)}
                else:
                    result = {"removed": catalog.remove_memory(args.asset_id)}
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (LookupError, ValueError, OSError, sqlite3.Error, DecompressionBombError) as error:
        parser.exit(1, f"Memory operation failed: {error}\n")


if __name__ == "__main__":
    main()
