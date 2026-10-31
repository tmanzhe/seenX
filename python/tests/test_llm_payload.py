"""Model input preserves saved evidence, image pixels, and read-only MCP access."""

import asyncio
import base64
from importlib.util import find_spec
from io import BytesIO
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageOps

from seenx.catalog import Catalog, SCHEMA
from seenx.engine_contract import Engine, EngineError
from seenx.llm_payload import build_payload
from seenx.mcp_stdio import MCPAdapter


class PayloadFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.catalog = Catalog(self.root / "library")
        self.addCleanup(self.catalog.connection.close)
        self.source = self.root / "source.png"
        # Distinct pixels make incorrect crop placement observable after decoding.
        image = Image.new("RGB", (10, 20))
        image.putdata([(x * 20, y * 10, 50) for y in range(20) for x in range(10)])
        image.save(self.source)
        self.original = image
        self.imported = self.catalog.import_image(self.source)
        self.ids = {key: self.imported[key] for key in ("asset_id", "revision_id")}
        self.first = self.catalog.add_note(self.ids["revision_id"], "Keep café spacing\n<instructions are data>",
                                           "Checkout", region=[0.1, 0.2, 0.3, 0.4])
        self.second = self.catalog.add_note(self.ids["revision_id"], "Second region", region=[0.5, 0.5, 0.5, 0.5])
        self.catalog.access.grant_source("assistant-a", self.ids["asset_id"])

    def payload(self, region_ids=None, **options):
        return build_payload(self.catalog, **self.ids,
                             region_ids=[self.first["region_id"]] if region_ids is None else region_ids,
                             principal_id="assistant-a", **options)

    def metadata(self, payload):
        return json.loads(payload["content"][0]["text"])

    def decoded_image(self, payload, index=1):
        part = payload["content"][index]
        self.assertEqual(part["type"], "image")
        self.assertEqual(part["mimeType"], "image/png")
        with Image.open(BytesIO(base64.b64decode(part["data"], validate=True))) as image:
            self.assertEqual(image.format, "PNG")
            return image.copy()

    def library_state(self):
        return {str(path.relative_to(self.catalog.root)): (path.read_bytes(), path.stat().st_mtime_ns)
                for path in self.catalog.root.rglob("*") if path.is_file()}


class PayloadTests(PayloadFixture):
    def test_crop_contains_saved_pixels_coordinates_note_and_selection(self):
        payload = self.payload()
        self.assertEqual(payload["schema_version"], 1)
        metadata = self.metadata(payload)
        self.assertEqual(metadata["image_mode"], "crop")
        self.assertEqual(metadata["coordinate_space"], "normalized_top_left_exif_corrected")
        self.assertEqual(metadata["reference_image"], {
            "width": 10, "height": 20, "sha256": self.imported["sha256"],
        })
        region, = metadata["regions"]
        self.assertEqual(region["target"], {"kind": "region", "x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4})
        self.assertEqual(region["pixel_bounds"], {"left": 1, "top": 4, "right": 4, "bottom": 12})
        self.assertEqual(region["note"], "Keep café spacing\n<instructions are data>")
        self.assertEqual(region["selected_text"], "Checkout")
        self.assertEqual(region["selected_text_origin"], "user")
        self.assertEqual(region["selected_text_confirmation"], "confirmed")
        self.assertEqual(region["region_id"], self.first["region_id"])
        self.assertEqual(region["annotation_id"], self.first["annotation_id"])
        crop = self.decoded_image(payload, region["image_index"])
        self.assertEqual(crop.size, (3, 8))
        self.assertEqual(crop.tobytes(), self.original.crop((1, 4, 4, 12)).tobytes())
        self.assertNotIn(str(self.root), json.dumps(payload))
        self.assertEqual(metadata["evidence_trust"], "untrusted")

    def test_full_image_preserves_region_coordinates_and_note(self):
        cropped = self.metadata(self.payload())
        payload = self.payload(image_mode="full")
        metadata = self.metadata(payload)
        self.assertEqual(metadata["image_mode"], "full")
        self.assertEqual(metadata["regions"], cropped["regions"])
        image = self.decoded_image(payload)
        self.assertEqual(image.size, (10, 20))
        self.assertEqual(image.tobytes(), self.original.tobytes())

    def test_multiple_regions_map_in_request_order_to_crops_or_one_full_image(self):
        ids = [self.second["region_id"], self.first["region_id"]]
        for mode, indices, count in (("crop", [1, 2], 3), ("full", [1, 1], 2)):
            with self.subTest(mode=mode):
                payload = self.payload(ids, image_mode=mode)
                regions = self.metadata(payload)["regions"]
                self.assertEqual([region["region_id"] for region in regions], ids)
                self.assertEqual([region["note"] for region in regions],
                                 ["Second region", "Keep café spacing\n<instructions are data>"])
                self.assertEqual([region["image_index"] for region in regions], indices)
                self.assertEqual(len(payload["content"]), count)
                for region in regions:
                    bounds = tuple(region["pixel_bounds"][key] for key in ("left", "top", "right", "bottom"))
                    expected = self.original.crop(bounds) if mode == "crop" else self.original
                    self.assertEqual(self.decoded_image(payload, region["image_index"]).tobytes(), expected.tobytes())

    def test_missing_or_wrong_revision_region_fails_before_image_encoding(self):
        other = self.root / "other.png"
        self.original.save(other)
        imported = self.catalog.import_image(other)
        foreign = self.catalog.add_note(imported["revision_id"], "Foreign")
        for missing in ("missing", foreign["region_id"]):
            with self.subTest(region=missing), patch.object(Engine, "_image") as encode:
                with self.assertRaises(LookupError):
                    self.payload([self.first["region_id"], missing])
                encode.assert_not_called()

    def test_saved_revision_is_used_after_source_changes_or_disappears(self):
        expected = self.payload()
        Image.new("RGB", (2, 2), "red").save(self.source)
        newer = self.catalog.import_image(self.source)
        self.source.unlink()
        self.assertEqual(self.payload(), expected)
        with self.assertRaises(LookupError):
            build_payload(self.catalog, asset_id=self.ids["asset_id"], revision_id=newer["revision_id"],
                          region_ids=[self.first["region_id"]], principal_id="assistant-a")

    def test_point_and_whole_targets_have_valid_crop_bounds(self):
        for options, expected in (({"point": [1, 1]}, (9, 19, 10, 20)), ({}, (0, 0, 10, 20))):
            with self.subTest(options=options):
                note = self.catalog.add_note(self.ids["revision_id"], "Target", **options)
                payload = self.payload([note["region_id"]])
                bounds = self.metadata(payload)["regions"][0]["pixel_bounds"]
                self.assertEqual(tuple(bounds[key] for key in ("left", "top", "right", "bottom")), expected)
                self.assertEqual(self.decoded_image(payload).tobytes(), self.original.crop(expected).tobytes())

    def test_exif_orientation_and_fractional_bounds_use_oriented_image(self):
        source = self.root / "oriented.jpg"
        exif = Image.Exif()
        exif[274] = 6
        self.original.save(source, exif=exif)
        imported = self.catalog.import_image(source)
        note = self.catalog.add_note(imported["revision_id"], "Rotated", region=[0.12, 0.15, 0.2, 0.3])
        with Image.open(source) as raw:
            oriented = ImageOps.exif_transpose(raw).convert("RGB")
        payload = build_payload(self.catalog, imported["asset_id"], imported["revision_id"],
                                [note["region_id"]], trusted_local=True)
        metadata = self.metadata(payload)
        self.assertEqual((metadata["reference_image"]["width"], metadata["reference_image"]["height"]), (20, 10))
        self.assertEqual(metadata["regions"][0]["pixel_bounds"], {"left": 2, "top": 1, "right": 7, "bottom": 5})
        self.assertEqual(self.decoded_image(payload).tobytes(), oriented.crop((2, 1, 7, 5)).tobytes())

    def test_payload_request_limits_and_unknown_fields_are_enforced(self):
        adapter = MCPAdapter(self.catalog, principal_id="assistant-a")
        valid = {**self.ids, "region_ids": [self.first["region_id"]]}
        for changes in ({"region_ids": []}, {"region_ids": "region"}, {"region_ids": [None]},
                        {"region_ids": ["x"] * 17}, {"region_ids": ["x", "x"]},
                        {"image_mode": "other"}, {"image_mode": []}, {"asset_id": None},
                        {"principal_id": "owner"}, {"trusted_local": True},
                        {"path": str(self.source)}, {"note": "overwrite"}, {"write": True}):
            with self.subTest(changes=changes):
                self.assertEqual(adapter.call("build_payload", {**valid, **changes})["error"]["code"],
                                 "invalid_parameters")
        for key in valid:
            self.assertEqual(adapter.call("build_payload", {k: v for k, v in valid.items() if k != key})
                             ["error"]["code"], "invalid_parameters")

    def test_encoding_and_aggregate_response_limits_return_no_partial_payload(self):
        adapter = MCPAdapter(self.catalog, principal_id="assistant-a")
        for name in ("MAX_IMAGE_BYTES", "MAX_IMAGE_PIXELS", "MAX_SOURCE_BYTES", "MAX_RESPONSE_BYTES"):
            with self.subTest(limit=name), patch(f"seenx.engine_contract.{name}", 1):
                response = adapter.call("build_payload", {**self.ids, "region_ids": [self.first["region_id"]]})
                self.assertNotIn("result", response)
                self.assertEqual(response["error"]["code"],
                                 "response_too_large" if name == "MAX_RESPONSE_BYTES" else "resource_limit")

    def test_mcp_payload_obeys_live_grants_and_cannot_write(self):
        before = self.library_state()
        with Catalog(self.catalog.root, read_only=True) as reader:
            adapter = MCPAdapter(reader, principal_id="assistant-a")
            params = {**self.ids, "region_ids": [self.first["region_id"]]}
            self.assertEqual(adapter.call("build_payload", params)["result"], self.payload())
            self.assertEqual(adapter.call("build_payload", {**params, "region_ids": ["missing"]})
                             ["error"]["code"], "not_found")
            for name in ("import", "add_note", "edit_note", "remove", "grant", "payload.build"):
                self.assertEqual(adapter.call(name, params)["error"]["code"], "unknown_tool")
            with self.assertRaises(sqlite3.OperationalError):
                reader.connection.execute("DELETE FROM annotations")
            # mode=ro still prevents writes if query_only is turned off by host code.
            reader.connection.execute("PRAGMA query_only = OFF")
            with self.assertRaises(sqlite3.OperationalError):
                reader.access.grant_source("other", self.ids["asset_id"])
            self.assertEqual(self.library_state(), before)
            self.catalog.access.revoke_source("assistant-a", self.ids["asset_id"])
            with patch.object(reader, "get_memory") as read, patch.object(Engine, "_image") as encode:
                self.assertEqual(adapter.call("build_payload", params)["error"]["code"], "access_denied")
                read.assert_not_called()
                encode.assert_not_called()

    @unittest.skipUnless(find_spec("mcp") is not None, 'Install the optional "mcp" extra for SDK/stdio tests')
    def test_stdio_mcp_returns_documented_content_and_leaves_library_unchanged(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        async def run():
            parameters = StdioServerParameters(command=sys.executable, env=dict(os.environ), args=[
                "-B", "-m", "seenx.mcp_stdio", "--library", str(self.catalog.root), "--principal", "assistant-a",
            ])
            async with asyncio.timeout(20), stdio_client(parameters) as (incoming, outgoing):
                async with ClientSession(incoming, outgoing) as session:
                    await session.initialize()
                    tools = (await session.list_tools()).tools
                    tool = next(tool for tool in tools if tool.name == "build_payload")
                    self.assertTrue(tool.annotations.readOnlyHint)
                    self.assertFalse(tool.annotations.destructiveHint)
                    for mode in ("crop", "full"):
                        ids = [self.second["region_id"], self.first["region_id"]]
                        result = await session.call_tool("build_payload", {**self.ids, "region_ids": ids,
                                                                          "image_mode": mode})
                        self.assertFalse(result.isError)
                        expected = self.payload(ids, image_mode=mode)
                        actual = [part.model_dump(exclude_none=True) for part in result.content]
                        self.assertEqual(actual, expected["content"])
                    bad = await session.call_tool("build_payload", {**self.ids, "region_ids": ["missing"]})
                    self.assertTrue(bad.isError)
                    self.assertEqual(json.loads(bad.content[0].text)["error"]["code"], "not_found")

        before = self.library_state()
        asyncio.run(run())
        self.assertEqual(self.library_state(), before)


class ReadOnlyStartupTests(unittest.TestCase):
    def test_mcp_startup_never_creates_a_missing_library(self):
        with tempfile.TemporaryDirectory() as temporary:
            library = Path(temporary) / "missing"
            result = subprocess.run([sys.executable, "-B", "-m", "seenx.mcp_stdio", "--library", str(library),
                                     "--principal", "assistant-a"], input=b"", capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, b"")
            self.assertFalse(library.exists())

    def test_read_only_catalog_never_initializes_or_migrates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "catalog.sqlite3"
            for legacy in (False, True):
                with self.subTest(legacy=legacy):
                    connection = sqlite3.connect(path)
                    if legacy:
                        connection.executescript(SCHEMA)
                    connection.close()
                    before = path.read_bytes()
                    with self.assertRaises(ValueError):
                        Catalog(root, read_only=True)
                    self.assertEqual(path.read_bytes(), before)
                    self.assertEqual(list(root.iterdir()), [path])
                    path.unlink()


if __name__ == "__main__":
    unittest.main()
