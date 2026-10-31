"""Native annotation requests persist evidence; all fixtures are local synthetic pixels."""

import base64
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from seenx.catalog import Catalog
from seenx.catalog_ocr import persist_observations
from seenx.engine_contract import Engine, WRITE_METHODS
from seenx.image_ocr import COORDINATE_SPACE
from seenx.llm_payload import build_payload
from seenx.mcp_stdio import MCPAdapter


class AnnotationBridgeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "fixture.png"
        Image.new("RGB", (100, 80), (12, 34, 56)).save(self.source)
        self.catalog = Catalog(self.root / "library")
        self.addCleanup(self.catalog.connection.close)
        imported = self.catalog.import_image(self.source)
        self.ids = {key: imported[key] for key in ("asset_id", "revision_id")}
        self.engine = Engine(self.catalog, trusted_local=True, allow_writes=True)

    def request(self, method, params=None, *, engine=None):
        frame = json.dumps({"version": 1, "id": "native", "method": method, "params": params or {}}).encode()
        return json.loads((engine or self.engine).handle(frame))

    def create(self, **changes):
        return self.request("annotation.create", {**self.ids, "note": "Keep café spacing\nline two",
                                                 "region": [.1, .2, .3, .4], **changes})

    def memory(self, catalog=None):
        return (catalog or self.catalog).get_memory(**self.ids, trusted_local=True)

    def test_draw_edit_delete_persist_across_reopen_and_update_search(self):
        original = self.source.read_bytes()
        created = self.create()["result"]
        note, = self.memory()["annotations"]
        self.assertEqual(note["id"], created["annotation_id"])
        self.assertEqual(note["pixel_bounds"], {"left": 10, "top": 16, "right": 40, "bottom": 48})
        self.assertEqual(note["origin"], "user")
        self.assertEqual(note["confirmation"], "confirmed")
        with Catalog(self.catalog.root) as reopened:
            engine = Engine(reopened, trusted_local=True, allow_writes=True)
            self.assertEqual(self.memory(reopened)["annotations"], [note])
            edited = self.request("annotation.update", {**self.ids, "annotation_id": note["id"],
                "note": "Revised region", "region": [.5, .5, .5, .5]}, engine=engine)
            self.assertEqual(edited["result"], created)
            self.assertEqual(reopened.search("café", trusted_local=True), [])
            hit, = reopened.search("Revised", trusted_local=True)
            self.assertEqual(hit["region_id"], created["region_id"])
            self.assertEqual(hit["target"]["width"], .5)
        with Catalog(self.catalog.root) as reopened:
            saved, = self.memory(reopened)["annotations"]
            self.assertEqual(saved["note"], "Revised region")
            self.assertEqual(saved["pixel_bounds"], {"left": 50, "top": 40, "right": 100, "bottom": 80})
            engine = Engine(reopened, trusted_local=True, allow_writes=True)
            deleted = self.request("annotation.delete", {**self.ids, "annotation_id": note["id"]}, engine=engine)
            self.assertEqual(deleted["result"], created)
        with Catalog(self.catalog.root) as reopened:
            self.assertEqual(self.memory(reopened)["annotations"], [])
            self.assertEqual(reopened.search("Revised", trusted_local=True), [])
            self.assertEqual(reopened.connection.execute("SELECT count(*) FROM regions").fetchone()[0], 0)
        self.assertEqual(self.source.read_bytes(), original)

    def test_note_only_and_geometry_only_edits_preserve_other_fields_and_ocr_provenance(self):
        run = persist_observations(self.catalog, self.ids["revision_id"], {
            "configuration": {"engine": "mock"}, "width": 100, "height": 80, "coordinate_space": COORDINATE_SPACE,
            "observations": [{"text": "Quoted text", "confidence": .9,
                              "box": {"x": .1, "y": .2, "width": .3, "height": .4}}],
        })
        saved = self.catalog.add_note(self.ids["revision_id"], "Original", observation_id=run["observations"][0]["id"])
        params = {**self.ids, "annotation_id": saved["annotation_id"]}
        self.assertIn("result", self.request("annotation.update", {**params, "note": "Edited"}))
        self.assertIn("result", self.request("annotation.update", {**params, "region": [0, 0, 1, 1]}))
        note, = self.memory()["annotations"]
        self.assertEqual(note["note"], "Edited")
        self.assertEqual(note["selected_text"], "Quoted text")
        self.assertEqual(note["selected_text_origin"], "ocr")
        self.assertEqual(note["selected_text_confirmation"], "unverified")
        self.assertEqual(note["quoted_observation_id"], run["observations"][0]["id"])

    def test_invalid_drafts_never_partially_change_annotations_or_index(self):
        created = self.create()["result"]
        before = self.memory()["annotations"]
        invalid = ({"note": None}, {"note": []}, {"note": "  "}, {"region": None}, {"region": "bad"},
                   {"region": [0, 0, 0, .5]}, {"region": [-.1, 0, .5, .5]}, {"region": [.8, 0, .3, 1]},
                   {"region": [0, True, .5, .5]}, {"region": [0, 0, "wide", .5]}, {"region": []})
        for changes in invalid:
            with self.subTest(changes=changes):
                self.assertEqual(self.create(**changes)["error"]["code"], "invalid_parameters")
                update = {**self.ids, "annotation_id": created["annotation_id"], "note": "Changed", **changes}
                self.assertEqual(self.request("annotation.update", update)["error"]["code"], "invalid_parameters")
                self.assertEqual(self.memory()["annotations"], before)
        self.assertEqual(len(self.catalog.search("café", trusted_local=True)), 1)
        self.assertEqual(self.catalog.search("Changed", trusted_local=True), [])

    def test_missing_unknown_and_identity_fields_are_rejected_before_writes(self):
        created = self.create()["result"]
        cases = {
            "annotation.create": {**self.ids, "note": "New", "region": [0, 0, 1, 1]},
            "annotation.update": {**self.ids, "annotation_id": created["annotation_id"], "note": "New"},
            "annotation.delete": {**self.ids, "annotation_id": created["annotation_id"]},
        }
        before = self.memory()["annotations"]
        for method, params in cases.items():
            for key in params:
                with self.subTest(method=method, missing=key):
                    self.assertEqual(self.request(method, {k: v for k, v in params.items() if k != key})
                                     ["error"]["code"], "invalid_parameters")
            for field in ("principal_id", "trusted_local", "allow_writes", "path", "selected_text"):
                self.assertEqual(self.request(method, {**params, field: "override"})["error"]["code"], "invalid_parameters")
        self.assertEqual(self.memory()["annotations"], before)

    def test_foreign_asset_revision_and_annotation_cannot_be_mutated(self):
        created = self.create()["result"]
        Image.new("RGB", (100, 80), "red").save(self.source)
        newer = self.catalog.import_image(self.source)
        other = self.root / "other.png"
        Image.new("RGB", (100, 80), "green").save(other)
        foreign = self.catalog.import_image(other)
        for ids in ({**self.ids, "revision_id": newer["revision_id"]},
                    {**self.ids, "asset_id": foreign["asset_id"]}):
            for method in ("annotation.update", "annotation.delete"):
                params = {**ids, "annotation_id": created["annotation_id"]}
                if method.endswith("update"):
                    params["note"] = "Wrong revision"
                self.assertEqual(self.request(method, params)["error"]["code"], "not_found")
        self.assertEqual(len(self.memory()["annotations"]), 1)
        self.assertEqual(self.create(asset_id=foreign["asset_id"])["error"]["code"], "not_found")

    def test_unknown_or_deleted_annotation_is_not_found_and_session_recovers(self):
        created = self.create()["result"]
        params = {**self.ids, "annotation_id": created["annotation_id"]}
        self.assertIn("result", self.request("annotation.delete", params))
        for method in ("annotation.delete", "annotation.update"):
            self.assertEqual(self.request(method, {**params, **({"note": "Retry"} if method.endswith("update") else {})})
                             ["error"]["code"], "not_found")
        self.assertIn("result", self.create())

    def test_write_capabilities_require_host_opt_in_and_cannot_be_enabled_by_grants_or_mcp(self):
        for options in ({}, {"principal_id": "assistant"}, {"trusted_local": True}):
            engine = Engine(self.catalog, **options)
            info = self.request("engine.info", engine=engine)["result"]
            self.assertTrue(info["read_only_requests"])
            self.assertTrue(WRITE_METHODS.isdisjoint(info["methods"]))
            for method in WRITE_METHODS:
                self.assertEqual(self.request(method, {**self.ids, "allow_writes": True}, engine=engine)["error"]["code"], "unknown_method")
        for options in ({}, {"principal_id": "assistant"}):
            with self.assertRaises(ValueError):
                Engine(self.catalog, allow_writes=True, **options)
        info = self.request("engine.info")["result"]
        self.assertFalse(info["read_only_requests"])
        self.assertTrue(WRITE_METHODS.issubset(info["methods"]))
        adapter = MCPAdapter(self.catalog, principal_id="assistant")
        for method in WRITE_METHODS:
            self.assertEqual(adapter.call(method, self.ids)["error"]["code"], "unknown_tool")

    def test_copy_payload_uses_saved_edits_and_exact_crop_pixels_with_no_writes(self):
        created = self.create()["result"]
        self.assertIn("result", self.request("annotation.update", {**self.ids, "annotation_id": created["annotation_id"],
            "note": "Saved for LLM", "region": [.5, .5, .5, .5]}))
        before = self.memory()["annotations"]
        for mode, dimensions in (("crop", (50, 40)), ("full", (100, 80))):
            params = {**self.ids, "region_ids": [created["region_id"]], "image_mode": mode}
            payload = self.request("payload.build", params)["result"]
            self.assertEqual(payload, build_payload(self.catalog, **params, trusted_local=True))
            metadata = json.loads(payload["content"][0]["text"])
            self.assertEqual(metadata["regions"][0]["note"], "Saved for LLM")
            self.assertEqual(metadata["evidence_trust"], "untrusted")
            self.assertEqual(metadata["regions"][0]["pixel_bounds"], {"left": 50, "top": 40, "right": 100, "bottom": 80})
            with Image.open(BytesIO(base64.b64decode(payload["content"][1]["data"]))) as image:
                self.assertEqual(image.size, dimensions)
                self.assertEqual(image.getpixel((0, 0)), (12, 34, 56))
        self.assertEqual(self.memory()["annotations"], before)
        with patch("seenx.engine_contract.MAX_RESPONSE_BYTES", 512):
            self.assertEqual(self.request("payload.build", params)["error"]["code"], "response_too_large")

    def test_stdio_write_opt_in_survives_process_restart(self):
        def run(method, params, *flags):
            frame = json.dumps({"version": 1, "id": "native", "method": method, "params": params}) + "\n"
            process = subprocess.run([sys.executable, "-B", "-m", "seenx.engine_stdio", "--library", str(self.catalog.root),
                                      "--no-log", *flags], input=frame, text=True, capture_output=True, timeout=15)
            return process
        params = {**self.ids, "note": "From native process", "region": [0, 0, 1, 1]}
        denied = run("annotation.create", params, "--trusted-local")
        self.assertEqual(json.loads(denied.stdout)["error"]["code"], "unknown_method")
        invalid = run("annotation.create", params, "--allow-writes")
        self.assertNotEqual(invalid.returncode, 0)
        self.assertEqual(invalid.stdout, "")
        created = run("annotation.create", params, "--trusted-local", "--allow-writes")
        self.assertEqual(created.returncode, 0, created.stderr)
        self.assertIn("result", json.loads(created.stdout))
        fetched = run("memory.fetch", self.ids, "--trusted-local")
        self.assertEqual(json.loads(fetched.stdout)["result"]["annotations"][0]["note"], "From native process")
