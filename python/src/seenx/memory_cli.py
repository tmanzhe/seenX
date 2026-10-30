"""Manage durable image memories, annotations, and portable library archives."""

import argparse
import json
from pathlib import Path
import sqlite3
import sys
from zipfile import BadZipFile

from PIL.Image import DecompressionBombError

from seenx.catalog import Catalog
from seenx.library_archive import export_library, restore_library, verify_archive, verify_library
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
    exporter = commands.add_parser("export", help="Export a versioned, unencrypted whole-library ZIP")
    exporter.add_argument("archive", type=Path)
    exporter.add_argument("--mode", choices=["complete", "context-only"], default="complete")
    restore = commands.add_parser("restore", help="Restore an archive into a NEW --library path")
    restore.add_argument("archive", type=Path)
    restore.add_argument("--original-folder", type=Path, help="Resolve context-only originals by SHA-256")
    verify = commands.add_parser("verify", help="Verify an archive, or the existing --library when omitted")
    verify.add_argument("archive", type=Path, nargs="?")
    verify.add_argument("--original-folder", type=Path, help="Report originals resolved by SHA-256 (read-only)")
    commands.add_parser("list", help="List saved assets and annotation counts")
    collection = commands.add_parser("collection-create", help="Create an owner-managed collection")
    collection.add_argument("name")
    for command in ("collection-add", "collection-remove"):
        membership = commands.add_parser(command, help="Change collection membership (affects collection grants)")
        membership.add_argument("collection_id")
        membership.add_argument("asset_id")
    for command in ("grant", "revoke"):
        access = commands.add_parser(command, help="Owner-managed assistant source or collection access")
        access.add_argument("principal_id")
        scope = access.add_mutually_exclusive_group(required=True)
        scope.add_argument("--source", help="Imported-file source ID (the stable asset ID)")
        scope.add_argument("--collection", help="Collection ID")
    search = commands.add_parser("search", help="Search saved notes, selected text, and OCR evidence")
    search.add_argument("--query", required=True)
    search.add_argument("--match", choices=["phrase", "all"], default="phrase")
    search.add_argument("--limit", type=int, default=20)
    search.add_argument("--asset", help="Restrict results to one asset ID")
    search.add_argument("--revision", help="Restrict results to one image revision")
    search.add_argument("--current-only", action="store_true", help="Exclude historical revisions")
    commands.add_parser("reindex", help="Rebuild derived text documents and FTS5 from saved source records")
    getter = commands.add_parser("get", help="Fetch a memory, annotations, and verified snapshot reference")
    getter.add_argument("asset_id")
    getter.add_argument("--revision", help="Fetch an older revision rather than the current one")
    ocr = commands.add_parser("ocr", help="Save text and bounding boxes for an immutable revision (macOS)")
    ocr.add_argument("revision_id")
    note = commands.add_parser("note", help="Save user-authored context against an image revision")
    note.add_argument("revision_id")
    note.add_argument("--note", default="")
    note.add_argument("--selected-text", default="")
    target = note.add_mutually_exclusive_group()
    target.add_argument("--region", type=float, nargs=4, metavar=("X", "Y", "WIDTH", "HEIGHT"))
    target.add_argument("--point", type=float, nargs=2, metavar=("X", "Y"))
    target.add_argument("--observation", help="Quote a saved OCR observation, using its text and region")
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
            if args.command == "export":
                result = export_library(args.library, args.archive, args.mode)
            elif args.command == "restore":
                result = restore_library(args.archive, args.library, args.original_folder)
            elif args.command == "verify":
                result = (verify_archive(args.archive, args.original_folder) if args.archive is not None
                          else verify_library(args.library, args.original_folder))
            else:
                result = _catalog_command(args)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if args.command == "verify" and not result["ok"]:
            raise SystemExit(1)
    except (LookupError, ValueError, OSError, sqlite3.Error, BadZipFile, DecompressionBombError) as error:
        parser.exit(1, f"Memory operation failed: {error}\n")


def _catalog_command(args):
    with Catalog(args.library) as catalog:
        if args.command == "import":
            result = catalog.import_image(args.file)
        elif args.command == "list":
            result = catalog.list_memories()
        elif args.command == "collection-create":
            result = {"collection_id": catalog.access.create_collection(args.name)}
        elif args.command in ("collection-add", "collection-remove"):
            operation = catalog.access.add_member if args.command == "collection-add" else catalog.access.remove_member
            operation(args.collection_id, args.asset_id)
            result = {"collection_id": args.collection_id, "asset_id": args.asset_id, "updated": True}
        elif args.command in ("grant", "revoke"):
            scope = "source" if args.source is not None else "collection"
            target_id = args.source if args.source is not None else args.collection
            getattr(catalog.access, f"{args.command}_{scope}")(args.principal_id, target_id)
            result = {"principal_id": args.principal_id, "scope": scope, "target_id": target_id,
                      "granted": args.command == "grant"}
        elif args.command == "search":
            result = catalog.search(args.query, match=args.match, limit=args.limit,
                                    asset_id=args.asset, revision_id=args.revision,
                                    current_only=args.current_only, trusted_local=True)
        elif args.command == "reindex":
            result = {"indexed_documents": catalog.rebuild_search()}
        elif args.command == "get":
            result = catalog.get_memory(args.asset_id, args.revision, trusted_local=True)
        elif args.command == "ocr":
            result = catalog.recognize_text(args.revision_id)
        elif args.command == "note":
            result = catalog.add_note(args.revision_id, args.note, args.selected_text,
                                      region=args.region, point=args.point, observation_id=args.observation)
        elif args.command == "edit":
            if args.note is None and args.selected_text is None:
                raise ValueError("Provide --note or --selected-text")
            catalog.edit_note(args.annotation_id, args.note, args.selected_text)
            result = {"annotation_id": args.annotation_id, "updated": True}
        elif args.command == "delete-note":
            result = {"removed": catalog.delete_note(args.annotation_id)}
        else:
            result = {"removed": catalog.remove_memory(args.asset_id)}
    return result


if __name__ == "__main__":
    main()
