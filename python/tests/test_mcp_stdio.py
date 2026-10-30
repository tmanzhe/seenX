"""MCP identity binding, read-only surface, grants, and real stdio lifecycle."""

import asyncio
from contextlib import redirect_stderr
from importlib.util import find_spec
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from seenx.catalog import Catalog
from seenx.mcp_stdio import MCPAdapter, create_server, main


class MCPStartupTests(unittest.TestCase):
    def test_process_refuses_to_start_without_principal(self):
        with tempfile.TemporaryDirectory() as temporary:
            library = Path(temporary) / "unopened-library"
            process = subprocess.run(
                [sys.executable, "-m", "seenx.mcp_stdio", "--library", str(library)],
                input=b"", capture_output=True, timeout=10,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertIn(b"--principal", process.stderr)
            self.assertEqual(process.stdout, b"")
            self.assertFalse(library.exists())

    def test_invalid_identity_and_trusted_mode_are_rejected_before_opening_library(self):
        for flags in ([], ["--principal", ""], ["--principal", " "],
                      ["--principal", "x" * 129], ["--trusted-local"],
                      ["--principal", "assistant-a", "--trusted-local"]):
            with self.subTest(flags=flags), patch.object(sys, "argv", ["seenx-mcp", *flags]):
                with patch("seenx.mcp_stdio.Catalog") as catalog, redirect_stderr(StringIO()):
                    with self.assertRaises(SystemExit) as stopped:
                        main()
                self.assertNotEqual(stopped.exception.code, 0)
                catalog.assert_not_called()


class MCPFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.catalog = Catalog(self.root / "library")
        self.addCleanup(self.catalog.connection.close)
        self.assets = []
        with patch("seenx.catalog.Image.open") as opened, patch("seenx.catalog.ImageOps.exif_transpose") as oriented:
            opened.return_value.__enter__.return_value.format = "PNG"
            opened.return_value.__enter__.return_value.getexif.return_value = {274: 1}
            oriented.return_value.size = (100, 200)
            for name in ("shared", "private"):
                source = self.root / f"{name}.image"
                source.write_bytes(name.encode())
                asset = self.catalog.import_image(source)
                note = self.catalog.add_note(asset["revision_id"], f"Spacing {name}", region=[0.1, 0.2, 0.3, 0.1])
                self.assets.append(({key: asset[key] for key in ("asset_id", "revision_id")}, note))
        self.shared, self.note = self.assets[0]
        self.private, self.private_note = self.assets[1]
        self.adapter = MCPAdapter(self.catalog, principal_id="assistant-a")


class MCPAdapterTests(MCPFixture):
    def test_principal_is_required_even_for_in_process_adapter(self):
        with self.assertRaises(TypeError):
            MCPAdapter(self.catalog)
        for principal in (None, "", " "):
            with self.subTest(principal=principal), self.assertRaises(ValueError):
                MCPAdapter(self.catalog, principal_id=principal)
        self.assertEqual(self.adapter.engine.principal_id, "assistant-a")
        self.assertFalse(self.adapter.engine.trusted_local)

    def test_grants_default_to_deny_and_ungranted_fetch_never_reads_evidence(self):
        self.assertEqual(self.adapter.call("search", {"query": "spacing"})["result"], [])
        self.catalog.access.grant_source("assistant-a", self.shared["asset_id"])
        found = self.adapter.call("search", {"query": "spacing", "limit": 1})["result"]
        self.assertEqual([hit["asset_id"] for hit in found], [self.shared["asset_id"]])
        with patch.object(self.catalog, "get_memory") as read:
            for options in ({}, {"region_id": self.private_note["region_id"]}, {"observation_id": "unknown"}):
                response = self.adapter.call("fetch", {**self.private, **options, "include_image": True})
                self.assertEqual(response["error"]["code"], "access_denied")
            read.assert_not_called()
        for field, value in (("asset_id", self.private["asset_id"]), ("revision_id", self.private["revision_id"])):
            self.assertEqual(self.adapter.call("search", {"query": "spacing", field: value})["result"], [])

    def test_memory_region_and_collection_access_follow_live_revocation(self):
        collection = self.catalog.access.create_collection("Assistant evidence")
        self.catalog.access.add_member(collection, self.shared["asset_id"])
        self.catalog.access.grant_collection("assistant-a", collection)
        memory = self.adapter.call("fetch", self.shared)["result"]
        self.assertEqual(memory["annotations"][0]["id"], self.note["annotation_id"])
        self.assertNotIn("source_path", memory["asset"])
        self.assertNotIn("snapshot_path", memory["revision"])
        region = {**self.shared, "region_id": self.note["region_id"]}
        self.assertEqual(self.adapter.call("fetch", region)["result"]["annotation"]["id"], self.note["annotation_id"])
        self.catalog.access.remove_member(collection, self.shared["asset_id"])
        self.assertEqual(self.adapter.call("fetch", region)["error"]["code"], "access_denied")
        self.catalog.access.add_member(collection, self.shared["asset_id"])
        self.catalog.access.revoke_collection("assistant-a", collection)
        self.assertEqual(self.adapter.call("search", {"query": "spacing"})["result"], [])

    def test_identity_trust_library_and_writes_cannot_be_selected_by_tool_calls(self):
        self.catalog.access.grant_source("assistant-b", self.private["asset_id"])
        for fields in ({"principal_id": "assistant-b"}, {"principal": "assistant-b"},
                       {"trusted_local": True}, {"trusted": True}, {"library": str(self.root)}):
            for name, params in (("search", {"query": "spacing"}), ("fetch", self.private)):
                with self.subTest(name=name, fields=fields):
                    self.assertEqual(self.adapter.call(name, {**params, **fields})["error"]["code"], "invalid_parameters")
        for name in ("import", "remove", "grant", "collection", "engine.info", "memory.search", "region.fetch"):
            self.assertEqual(self.adapter.call(name, {})["error"]["code"], "unknown_tool")

    def test_contract_bounds_and_target_validation_are_preserved(self):
        self.catalog.access.grant_source("assistant-a", self.shared["asset_id"])
        for params in ({"query": "spacing", "limit": 101}, {"query": "x" * 513}):
            self.assertEqual(self.adapter.call("search", params)["error"]["code"], "invalid_parameters")
        for params in ({**self.shared, "region_id": self.note["region_id"], "observation_id": "other"},
                       {"asset_id": self.shared["asset_id"], "region_id": self.note["region_id"]}):
            self.assertEqual(self.adapter.call("fetch", params)["error"]["code"], "invalid_parameters")


@unittest.skipUnless(find_spec("mcp") is not None, 'Install the optional "mcp" extra for SDK/stdio tests')
class MCPProtocolTests(MCPFixture, unittest.IsolatedAsyncioTestCase):
    async def test_stdio_initialize_exact_tools_and_grant_scoped_calls(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "seenx.mcp_stdio", "--library", str(self.catalog.root), "--principal", "assistant-a"],
            env=dict(os.environ),
        )
        async with asyncio.timeout(20):
            async with stdio_client(parameters) as (incoming, outgoing):
                async with ClientSession(incoming, outgoing) as session:
                    initialized = await session.initialize()
                    self.assertIsNotNone(initialized.capabilities.tools)
                    self.assertIsNone(initialized.capabilities.resources)
                    self.assertIsNone(initialized.capabilities.prompts)
                    tools = (await session.list_tools()).tools
                    self.assertEqual(sorted(tool.name for tool in tools), ["fetch", "search"])
                    self.assertTrue(all(tool.annotations.readOnlyHint for tool in tools))
                    empty = await session.call_tool("search", {"query": "spacing"})
                    self.assertEqual(json.loads(empty.content[0].text)["result"], [])
                    denied = await session.call_tool("fetch", self.shared)
                    self.assertTrue(denied.isError)
                    self.assertEqual(json.loads(denied.content[0].text)["error"]["code"], "access_denied")
                    self.catalog.access.grant_source("assistant-a", self.shared["asset_id"])
                    found = await session.call_tool("search", {"query": "spacing"})
                    hits = json.loads(found.content[0].text)["result"]
                    self.assertEqual([hit["asset_id"] for hit in hits], [self.shared["asset_id"]])
                    region = await session.call_tool("fetch", {**self.shared, "region_id": self.note["region_id"]})
                    self.assertFalse(region.isError)
                    self.assertEqual(json.loads(region.content[0].text)["result"]["annotation"]["id"], self.note["annotation_id"])
                    denied = await session.call_tool("fetch", self.private)
                    self.assertTrue(denied.isError)
                    self.catalog.access.revoke_source("assistant-a", self.shared["asset_id"])
                    denied = await session.call_tool("fetch", self.shared)
                    self.assertTrue(denied.isError)

    async def test_image_attachment_is_mcp_image_content_without_duplicate_base64(self):
        import mcp.types as types

        response = {"result": {"image": {"media_type": "image/png", "data": "cG5n", "width": 1, "height": 1}}}
        server = create_server(self.adapter)
        request = types.CallToolRequest(method="tools/call", params=types.CallToolRequestParams(
            name="fetch", arguments={**self.shared, "include_image": True},
        ))
        with patch.object(self.adapter, "call", return_value=response):
            result = (await server.request_handlers[types.CallToolRequest](request)).root
        self.assertFalse(result.isError)
        self.assertEqual(result.content[1].type, "image")
        self.assertEqual(result.content[1].data, "cG5n")
        self.assertNotIn("data", json.loads(result.content[0].text)["result"]["image"])


if __name__ == "__main__":
    unittest.main()
