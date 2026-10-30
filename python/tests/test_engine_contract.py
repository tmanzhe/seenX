"""Versioned engine boundaries and framing; no image generation or model downloads."""

import base64
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from seenx.catalog import Catalog
from seenx.catalog_ocr import persist_observations
from seenx.engine_contract import Engine, MAX_REQUEST_BYTES
from seenx.engine_stdio import main as engine_main, serve
from seenx.image_ocr import COORDINATE_SPACE
from seenx.observability import configure_logging


class FakeImage:
    """Exercise the encoding path without creating a bitmap fixture."""
    def __init__(self, width=100, height=200):
        self.width, self.height = width, height
        self.size = (width, height)
        self.info = {}

    def load(self):
        pass

    def getbands(self):
        return ("R", "G", "B")

    def convert(self, mode):
        return self

    def crop(self, bounds):
        left, top, right, bottom = bounds
        return FakeImage(right - left, bottom - top)

    def save(self, destination, format):
        destination.write(b"encoded-existing-pixels")


class EngineFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "source.image"
        self.source.write_bytes(b"placeholder")
        self.catalog = Catalog(self.root / "library")
        self.addCleanup(self.catalog.connection.close)
        self.imported = self.import_source(self.source)
        self.note = self.catalog.add_note(self.imported["revision_id"], "Keep this spacing", region=[0.1, 0.2, 0.3, 0.1])
        self.engine = Engine(self.catalog, trusted_local=True)

    def import_source(self, path):
        with patch("seenx.catalog.Image.open") as opened, patch("seenx.catalog.ImageOps.exif_transpose") as oriented:
            opened.return_value.__enter__.return_value.format = "PNG"
            opened.return_value.__enter__.return_value.getexif.return_value = {274: 1}
            oriented.return_value.size = (100, 200)
            return self.catalog.import_image(path)

    def frame(self, method="engine.info", params=None, **overrides):
        request = {"version": 1, "id": "request-1", "method": method, "params": {} if params is None else params}
        return json.dumps({**request, **overrides}).encode()

    def request(self, method="engine.info", params=None, **overrides):
        return json.loads(self.engine.handle(self.frame(method, params, **overrides)))


class CatalogReadAccessTests(EngineFixture):
    def test_ungranted_direct_fetches_refuse_before_snapshot_reads(self):
        with patch.object(self.catalog, "object_path") as snapshot:
            for principal_id in ("assistant-a", "assistant-b"):
                with self.assertRaises(PermissionError):
                    self.catalog.get_memory(self.imported["asset_id"], principal_id=principal_id)
                with self.assertRaises(PermissionError):
                    self.catalog.read_revision_bytes(self.imported["revision_id"], principal_id=principal_id)
            with self.assertRaises(PermissionError):
                self.catalog.get_memory("unknown", principal_id="assistant-a")
            with self.assertRaises(PermissionError):
                self.catalog.read_revision_bytes("unknown", principal_id="assistant-a")
            snapshot.assert_not_called()

    def test_direct_fetches_apply_source_and_collection_grants_and_revocation(self):
        for scope in ("source", "collection"):
            with self.subTest(scope=scope):
                target = self.imported["asset_id"]
                if scope == "collection":
                    target = self.catalog.access.create_collection("Shared")
                    self.catalog.access.add_member(target, self.imported["asset_id"])
                getattr(self.catalog.access, f"grant_{scope}")("assistant-a", target)
                self.assertEqual(len(self.catalog.search("spacing", principal_id="assistant-a")), 1)
                memory = self.catalog.get_memory(self.imported["asset_id"], principal_id="assistant-a")
                self.assertEqual(memory["annotations"][0]["id"], self.note["annotation_id"])
                _, payload = self.catalog.read_revision_bytes(self.imported["revision_id"], principal_id="assistant-a")
                self.assertEqual(payload, b"placeholder")
                with self.assertRaises(PermissionError):
                    self.catalog.get_memory(self.imported["asset_id"], principal_id="assistant-b")
                getattr(self.catalog.access, f"revoke_{scope}")("assistant-a", target)
                self.assertEqual(self.catalog.search("spacing", principal_id="assistant-a"), [])
                with self.assertRaises(PermissionError):
                    self.catalog.get_memory(self.imported["asset_id"], principal_id="assistant-a")
                with self.assertRaises(PermissionError):
                    self.catalog.read_revision_bytes(self.imported["revision_id"], principal_id="assistant-a")

    def test_explicit_trusted_reads_retain_owner_access(self):
        memory = self.catalog.get_memory(self.imported["asset_id"], trusted_local=True)
        self.assertEqual(memory["annotations"][0]["id"], self.note["annotation_id"])
        _, payload = self.catalog.read_revision_bytes(self.imported["revision_id"], trusted_local=True)
        self.assertEqual(payload, b"placeholder")


class EngineContractTests(EngineFixture):
    def test_info_and_search_have_stable_ids_and_trace_correlation(self):
        info = self.request()
        self.assertEqual(info["version"], 1)
        self.assertEqual(info["id"], "request-1")
        self.assertEqual(len(info["trace_id"]), 32)
        self.assertTrue(info["result"]["read_only_requests"])
        found = self.request("memory.search", {"query": "keep this spacing"})["result"]
        self.assertEqual(found[0]["annotation_id"], self.note["annotation_id"])
        self.assertEqual(found[0]["revision_id"], self.imported["revision_id"])

    def test_metadata_does_not_return_internal_filesystem_paths(self):
        response = self.request("memory.fetch", {"asset_id": self.imported["asset_id"]})
        self.assertEqual(response["result"]["asset"]["source_name"], "source.image")
        self.assertNotIn(str(self.root), json.dumps(response))
        self.assertNotIn("snapshot_path", response["result"]["revision"])
        self.assertNotIn("image", response["result"])

    def test_region_fetch_is_bound_to_the_saved_revision_and_target(self):
        params = {"asset_id": self.imported["asset_id"], "revision_id": self.imported["revision_id"],
                  "region_id": self.note["region_id"]}
        result = self.request("region.fetch", params)["result"]
        self.assertEqual(result["pixel_bounds"], {"left": 10, "top": 40, "right": 40, "bottom": 60})
        self.assertEqual(result["annotation"]["id"], self.note["annotation_id"])
        self.assertEqual(result["reference_image"], {"width": 100, "height": 200, "sha256": self.imported["sha256"]})
        self.source.write_bytes(b"changed source")
        changed = self.import_source(self.source)
        invalid = self.request("region.fetch", {**params, "revision_id": changed["revision_id"]})
        self.assertEqual(invalid["error"]["code"], "not_found")

    def test_other_asset_cannot_fetch_a_revision_or_region_it_does_not_own(self):
        other = self.root / "other.image"
        other.write_bytes(b"different")
        imported = self.import_source(other)
        response = self.request("memory.fetch", {"asset_id": imported["asset_id"],
                                                "revision_id": self.imported["revision_id"]})
        self.assertEqual(response["error"]["code"], "not_found")

    def test_observation_fetch_preserves_unverified_provenance(self):
        saved = persist_observations(self.catalog, self.imported["revision_id"], {
            "configuration": {"engine": "test"}, "width": 100, "height": 200,
            "coordinate_space": COORDINATE_SPACE,
            "observations": [{"text": "Recognized text", "confidence": 0.9,
                              "box": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.1}}],
        })
        params = {"asset_id": self.imported["asset_id"], "revision_id": self.imported["revision_id"],
                  "observation_id": saved["observations"][0]["id"]}
        result = self.request("region.fetch", params)["result"]
        self.assertEqual(result["observation"]["confirmation"], "unverified")
        self.assertEqual(result["pixel_bounds"]["top"], 40)
        invalid = self.request("region.fetch", {**params, "region_id": self.note["region_id"]})
        self.assertEqual(invalid["error"]["code"], "invalid_parameters")

    def test_point_at_image_edge_maps_to_one_valid_pixel(self):
        point = self.catalog.add_note(self.imported["revision_id"], "Point", point=[1, 1])
        result = self.request("region.fetch", {"asset_id": self.imported["asset_id"],
            "revision_id": self.imported["revision_id"], "region_id": point["region_id"]})["result"]
        self.assertEqual(result["pixel_bounds"], {"left": 99, "top": 199, "right": 100, "bottom": 200})

    def test_image_attachment_and_crop_keep_explicit_dimensions_and_encoding(self):
        fake = FakeImage()
        with patch("seenx.engine_contract.Image.open") as opened, patch("seenx.engine_contract.ImageOps.exif_transpose", return_value=fake):
            opened.return_value.__enter__.return_value = fake
            result = self.request("region.fetch", {"asset_id": self.imported["asset_id"],
                "revision_id": self.imported["revision_id"], "region_id": self.note["region_id"], "include_image": True})["result"]
        self.assertEqual((result["image"]["width"], result["image"]["height"]), (30, 20))
        self.assertEqual(base64.b64decode(result["image"]["data"]), b"encoded-existing-pixels")
        self.assertEqual(result["image"]["media_type"], "image/png")

    def test_source_pixel_and_encoded_image_limits_fail_without_partial_images(self):
        params = {"asset_id": self.imported["asset_id"], "include_image": True}
        with patch("seenx.engine_contract.MAX_SOURCE_BYTES", 2):
            self.assertEqual(self.request("memory.fetch", params)["error"]["code"], "resource_limit")
        with patch("seenx.engine_contract.MAX_IMAGE_PIXELS", 1):
            self.assertEqual(self.request("memory.fetch", params)["error"]["code"], "resource_limit")
        fake = FakeImage()
        with patch("seenx.engine_contract.Image.open") as opened, patch("seenx.engine_contract.ImageOps.exif_transpose", return_value=fake):
            opened.return_value.__enter__.return_value = fake
            with patch("seenx.engine_contract.MAX_IMAGE_BYTES", 2):
                self.assertEqual(self.request("memory.fetch", params)["error"]["code"], "resource_limit")

    def test_response_limit_is_enforced_before_writing(self):
        self.catalog.edit_note(self.note["annotation_id"], note="private " * 1000)
        with patch("seenx.engine_contract.MAX_RESPONSE_BYTES", 1024):
            response = self.request("memory.fetch", {"asset_id": self.imported["asset_id"]})
        self.assertEqual(response["error"]["code"], "response_too_large")
        self.assertNotIn("private", json.dumps(response))

    def test_no_arbitrary_path_or_crop_arguments_are_accepted(self):
        for method, params in (("memory.fetch", {"asset_id": self.imported["asset_id"], "path": "/etc/passwd"}),
                               ("region.fetch", {"asset_id": self.imported["asset_id"], "revision_id": self.imported["revision_id"],
                                                 "region_id": self.note["region_id"], "bounds": [0, 0, 1, 1]})):
            with self.subTest(method=method):
                self.assertEqual(self.request(method, params)["error"]["code"], "invalid_parameters")

    def test_invalid_parameter_types_and_unknown_writes_are_rejected(self):
        for params in ({"query": []}, {"query": "spacing", "match": []},
                       {"query": "spacing", "limit": True}, {"query": "spacing", "current_only": "false"}):
            with self.subTest(params=params):
                self.assertEqual(self.request("memory.search", params)["error"]["code"], "invalid_parameters")
        self.assertEqual(self.request("asset.import", {"path": "/tmp/image"})["error"]["code"], "unknown_method")
        self.assertEqual(self.request("memory.fetch", {"asset_id": self.imported["asset_id"], "revision_id": None})["error"]["code"], "invalid_parameters")

    def test_malformed_envelopes_json_and_versions_do_not_crash_the_engine(self):
        for frame, code in ((b"{", "invalid_json"), (b"[]", "invalid_request"),
                            (b'{"id":"a","id":"b"}', "invalid_json"),
                            (b'{"x":NaN}', "invalid_json"), (self.frame().decode().encode('utf-16'), "invalid_json")):
            with self.subTest(frame=frame):
                self.assertEqual(json.loads(self.engine.handle(frame))["error"]["code"], code)
        self.assertEqual(self.request(version=2)["error"]["code"], "unsupported_version")
        self.assertEqual(self.request(version=True)["error"]["code"], "unsupported_version")
        self.assertEqual(self.request(id=12)["error"]["code"], "invalid_request")
        self.assertEqual(self.request(id="\ud800")["error"]["code"], "invalid_request")
        self.assertIn("result", self.request())

    def test_storage_and_unexpected_errors_do_not_expose_exception_messages(self):
        for error, expected in ((OSError("private-path-sentinel"), "evidence_unavailable"),
                                (PermissionError("private-path-sentinel"), "evidence_unavailable"),
                                (sqlite3.OperationalError("private-path-sentinel"), "storage_error"),
                                (RuntimeError("private-path-sentinel"), "internal_error")):
            with self.subTest(error=type(error).__name__), patch.object(self.catalog, "get_memory", side_effect=error):
                response = self.request("memory.fetch", {"asset_id": self.imported["asset_id"]})
                self.assertEqual(response["error"]["code"], expected)
                self.assertNotIn("private-path-sentinel", json.dumps(response))
        self.assertIn("result", self.request())

    def test_request_diagnostics_do_not_save_query_notes_ids_or_paths(self):
        log = self.root / "events.jsonl"
        configure_logging(path=log, debug=True)
        self.addCleanup(configure_logging, enabled=False)
        self.catalog.edit_note(self.note["annotation_id"], note="secret-note-sentinel")
        self.request("memory.search", {"query": "private-query-sentinel"}, id="private-id-sentinel")
        self.request("memory.fetch", {"asset_id": self.imported["asset_id"]})
        contents = log.read_text()
        for private in ("secret-note-sentinel", "private-query-sentinel", "private-id-sentinel", str(self.root)):
            self.assertNotIn(private, contents)
        self.assertTrue(any(json.loads(line)["event"] == "engine_response" for line in contents.splitlines()))

    def test_oversized_frame_is_drained_without_losing_the_next_request(self):
        incoming = BytesIO(b" " * (MAX_REQUEST_BYTES + 10) + b"\n" + self.frame(id="next") + b"\n")
        outgoing = BytesIO()
        serve(self.engine, incoming, outgoing)
        replies = [json.loads(line) for line in outgoing.getvalue().splitlines()]
        self.assertEqual(len(replies), 2)
        self.assertEqual(replies[0]["error"]["code"], "request_too_large")
        self.assertEqual(replies[1]["id"], "next")
        self.assertIn("result", replies[1])

    def test_framing_keeps_stdout_json_only_and_accepts_eof_after_last_frame(self):
        incoming = BytesIO(b"\n" + self.frame(id="one") + b"\n" + self.frame(id="two"))
        outgoing = BytesIO()
        serve(self.engine, incoming, outgoing)
        replies = [json.loads(line) for line in outgoing.getvalue().splitlines()]
        self.assertEqual([reply["id"] for reply in replies], ["one", "two"])


class EngineGrantTests(EngineFixture):
    def setUp(self):
        super().setUp()
        self.engine = Engine(self.catalog, principal_id="assistant-a")
        other = self.root / "private.image"
        other.write_bytes(b"private snapshot")
        self.private = self.import_source(other)
        self.private_note = self.catalog.add_note(self.private["revision_id"], "Keep this spacing private-sentinel")

    def test_default_and_ungranted_principals_deny_all_evidence(self):
        for engine in (Engine(self.catalog), self.engine, Engine(self.catalog, principal_id="assistant-b")):
            self.engine = engine
            self.assertEqual(self.request("memory.search", {"query": "spacing"})["result"], [])
            response = self.request("memory.fetch", {"asset_id": self.imported["asset_id"]})
            self.assertEqual(response["error"]["code"], "access_denied")
        # A grant to a named principal never authorizes an anonymous caller.
        self.catalog.access.grant_source("assistant-a", self.imported["asset_id"])
        self.engine = Engine(self.catalog)
        self.assertEqual(self.request("memory.search", {"query": "spacing"})["result"], [])

    def test_source_grant_allows_search_memory_and_saved_region(self):
        self.catalog.access.grant_source("assistant-a", self.imported["asset_id"])
        hits = self.request("memory.search", {"query": "spacing"})["result"]
        self.assertEqual([hit["asset_id"] for hit in hits], [self.imported["asset_id"]])
        memory = self.request("memory.fetch", {"asset_id": self.imported["asset_id"]})["result"]
        self.assertEqual(memory["annotations"][0]["id"], self.note["annotation_id"])
        region = self.request("region.fetch", {**self.imported_ids(), "region_id": self.note["region_id"]})
        self.assertEqual(region["result"]["annotation"]["id"], self.note["annotation_id"])

    def imported_ids(self):
        return {key: self.imported[key] for key in ("asset_id", "revision_id")}

    def test_source_revoke_removes_search_and_fetch_on_existing_session(self):
        self.catalog.access.grant_source("assistant-a", self.imported["asset_id"])
        self.assertIn("result", self.request("memory.fetch", self.imported_ids()))
        self.catalog.access.revoke_source("assistant-a", self.imported["asset_id"])
        self.assertEqual(self.request("memory.search", {"query": "spacing"})["result"], [])
        self.assertEqual(self.request("memory.fetch", self.imported_ids())["error"]["code"], "access_denied")
        self.assertEqual(self.request("region.fetch", {**self.imported_ids(), "region_id": self.note["region_id"]})
                         ["error"]["code"], "access_denied")

    def test_ungranted_memory_and_region_ids_are_refused_before_evidence_reads(self):
        self.catalog.access.grant_source("assistant-a", self.imported["asset_id"])
        private_ids = {key: self.private[key] for key in ("asset_id", "revision_id")}
        cases = [("memory.fetch", {**private_ids, "include_image": True}),
                 ("region.fetch", {**private_ids, "region_id": self.private_note["region_id"], "include_image": True}),
                 ("region.fetch", {**private_ids, "observation_id": "guessed-observation", "include_image": True}),
                 ("memory.fetch", {"asset_id": "unknown-asset"})]
        with patch.object(self.catalog, "get_memory") as read, patch.object(self.engine, "_image") as image:
            for method, params in cases:
                response = self.request(method, params)
                self.assertEqual(response["error"]["code"], "access_denied")
                self.assertNotIn("private-sentinel", json.dumps(response))
            read.assert_not_called()
            image.assert_not_called()

    def test_search_filters_never_override_grants_and_limit_applies_after_authorization(self):
        self.catalog.edit_note(self.note["annotation_id"], note="spacing " + "filler " * 100)
        for _ in range(105):
            self.catalog.add_note(self.private["revision_id"], "spacing")
        self.catalog.access.grant_source("assistant-a", self.imported["asset_id"])
        for options in ({}, {"match": "all"}, {"current_only": True}, {"limit": 1}):
            response = self.request("memory.search", {"query": "spacing", **options})
            self.assertEqual([hit["asset_id"] for hit in response["result"]], [self.imported["asset_id"]])
            self.assertNotIn("private-sentinel", json.dumps(response))
        for options in ({"asset_id": self.private["asset_id"]}, {"revision_id": self.private["revision_id"]}):
            self.assertEqual(self.request("memory.search", {"query": "spacing", **options})["result"], [])

    def test_search_grants_cover_notes_selected_text_and_ocr_without_leaking_private_fields(self):
        for imported in (self.imported, self.private):
            self.catalog.add_note(imported["revision_id"], selected_text="spacing selection")
            persist_observations(self.catalog, imported["revision_id"], {
                "configuration": {"engine": "test"}, "width": 100, "height": 200,
                "coordinate_space": COORDINATE_SPACE,
                "observations": [{"text": "spacing recognized", "confidence": 0.9,
                                  "box": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.1}}],
            })
        self.catalog.access.grant_source("assistant-a", self.imported["asset_id"])
        hits = self.request("memory.search", {"query": "spacing"})["result"]
        self.assertEqual({hit["matched_field"] for hit in hits}, {"note", "selected_text", "ocr"})
        self.assertEqual({hit["asset_id"] for hit in hits}, {self.imported["asset_id"]})

    def test_principal_and_trust_cannot_be_supplied_in_wire_parameters(self):
        self.catalog.access.grant_source("assistant-b", self.private["asset_id"])
        for options in ({"principal_id": "assistant-b"}, {"trusted_local": True}):
            self.assertEqual(self.request("memory.search", {"query": "spacing", **options})["error"]["code"],
                             "invalid_parameters")
        self.assertEqual(self.request("memory.search", {"query": "spacing"})["result"], [])
        self.assertEqual(self.request("grant", {})["error"]["code"], "unknown_method")

    def test_collection_grant_membership_removal_and_revoke_are_live(self):
        collection = self.catalog.access.create_collection("Shared")
        self.catalog.access.add_member(collection, self.imported["asset_id"])
        self.catalog.access.grant_collection("assistant-a", collection)
        self.assertIn("result", self.request("memory.fetch", self.imported_ids()))
        self.assertEqual(len(self.request("memory.search", {"query": "spacing"})["result"]), 1)
        self.catalog.access.remove_member(collection, self.imported["asset_id"])
        self.assertEqual(self.request("memory.fetch", self.imported_ids())["error"]["code"], "access_denied")
        # Membership is dynamic: adding an asset to a granted collection authorizes it.
        self.catalog.access.add_member(collection, self.private["asset_id"])
        self.assertEqual(self.request("memory.search", {"query": "spacing"})["result"][0]["asset_id"],
                         self.private["asset_id"])
        self.catalog.access.revoke_collection("assistant-a", collection)
        self.assertEqual(self.request("memory.search", {"query": "spacing"})["result"], [])
        self.assertEqual(self.request("memory.fetch", {"asset_id": self.private["asset_id"]})["error"]["code"],
                         "access_denied")

    def test_grants_are_principal_specific_and_alternative_grants_form_a_union(self):
        collection = self.catalog.access.create_collection("Shared")
        self.catalog.access.add_member(collection, self.imported["asset_id"])
        self.catalog.access.grant_collection("assistant-a", collection)
        self.catalog.access.grant_source("assistant-a", self.imported["asset_id"])
        self.catalog.access.revoke_source("assistant-a", self.imported["asset_id"])
        self.assertIn("result", self.request("memory.fetch", self.imported_ids()))
        self.engine = Engine(self.catalog, principal_id="assistant-b")
        self.assertEqual(self.request("memory.fetch", self.imported_ids())["error"]["code"], "access_denied")

    def test_grants_persist_across_reopen_and_cover_all_source_revisions(self):
        self.catalog.access.grant_source("assistant-a", self.imported["asset_id"])
        collection = self.catalog.access.create_collection("Shared")
        self.catalog.access.add_member(collection, self.private["asset_id"])
        self.catalog.access.grant_collection("assistant-a", collection)
        self.source.write_bytes(b"changed source")
        current = self.import_source(self.source)
        self.assertEqual(current["asset_id"], self.imported["asset_id"])
        with Catalog(self.catalog.root) as reopened:
            self.engine = Engine(reopened, principal_id="assistant-a")
            for params in (self.imported_ids(), {"asset_id": current["asset_id"]},
                           {"asset_id": self.private["asset_id"]}):
                self.assertIn("result", self.request("memory.fetch", params))
            reopened.access.revoke_source("assistant-a", self.imported["asset_id"])
        self.engine = Engine(self.catalog, principal_id="assistant-a")
        self.assertEqual(self.request("memory.fetch", self.imported_ids())["error"]["code"], "access_denied")

    def test_trusted_local_app_retains_whole_library_access_without_grants(self):
        self.engine = Engine(self.catalog, trusted_local=True)
        self.assertEqual(len(self.request("memory.search", {"query": "spacing"})["result"]), 2)
        self.assertIn("result", self.request("memory.fetch", {"asset_id": self.private["asset_id"]}))

    def test_stdio_launch_binds_access_without_request_supplied_identity(self):
        self.catalog.access.grant_source("assistant-a", self.imported["asset_id"])
        for flags, expected in (([], []), (["--principal", "assistant-a"], [self.imported["asset_id"]]),
                                (["--principal", "assistant-b"], []),
                                (["--trusted-local"], [self.imported["asset_id"], self.private["asset_id"]])):
            outgoing = BytesIO()
            arguments = ["seenx-engine", "--library", str(self.catalog.root), "--no-log", *flags]
            with self.subTest(flags=flags), patch.object(sys, "argv", arguments):
                with patch("seenx.engine_stdio.sys.stdin") as incoming_stream, patch("seenx.engine_stdio.sys.stdout") as outgoing_stream:
                    incoming_stream.buffer = BytesIO(self.frame("memory.search", {"query": "spacing"}))
                    outgoing_stream.buffer = outgoing
                    engine_main()
            response = json.loads(outgoing.getvalue())
            self.assertEqual({hit["asset_id"] for hit in response["result"]}, set(expected))


if __name__ == "__main__":
    unittest.main()
