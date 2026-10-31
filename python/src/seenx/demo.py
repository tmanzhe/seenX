"""Run an offline save, search, and MCP payload demo with a synthetic image."""

import asyncio
import base64
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile

from PIL import Image

from seenx.catalog import Catalog


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


async def run_demo(root: Path) -> None:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    source = root / "sample.png"
    image = Image.new("RGB", (100, 80))
    image.putdata([(x * 2, y * 3, 50) for y in range(80) for x in range(100)])
    image.save(source)
    library = root / "library"
    with Catalog(library) as catalog:
        saved = catalog.import_image(source)
        note = catalog.add_note(saved["revision_id"], "Keep checkout spacing", "Checkout",
                                region=[0.1, 0.2, 0.3, 0.4])
        catalog.access.grant_source("demo-assistant", saved["asset_id"])
    source.unlink()
    print("Saved: synthetic 100x80 image + region note; original removed.")

    parameters = StdioServerParameters(command=sys.executable, args=[
        "-B", "-m", "seenx.mcp_stdio", "--library", str(library), "--principal", "demo-assistant",
    ])
    async with asyncio.timeout(30), stdio_client(parameters) as (incoming, outgoing):
        async with ClientSession(incoming, outgoing) as session:
            await session.initialize()
            names = sorted(tool.name for tool in (await session.list_tools()).tools)
            check(names == ["build_payload", "fetch", "search"], "Unexpected MCP tools")
            print(f"MCP tools: {', '.join(names)}")
            result = await session.call_tool("search", {"query": "checkout spacing"})
            check(not result.isError, "Search failed")
            hits = json.loads(result.content[0].text)["result"]
            check(len(hits) == 1 and hits[0]["asset_id"] == saved["asset_id"], "Saved note not found")
            print(f"Search: {len(hits)} hit; note=Keep checkout spacing")

            ids = {key: saved[key] for key in ("asset_id", "revision_id")}
            result = await session.call_tool("fetch", {**ids, "region_id": note["region_id"]})
            check(not result.isError, "Region fetch failed")
            region = json.loads(result.content[0].text)["result"]
            bounds = {"left": 10, "top": 16, "right": 40, "bottom": 48}
            check(region["pixel_bounds"] == bounds, "Saved bounds changed")
            print("Fetch: saved region bounds=(10, 16, 40, 48)")

            params = {**ids, "region_ids": [note["region_id"]]}
            for mode in ("crop", "full"):
                result = await session.call_tool("build_payload", {**params, "image_mode": mode})
                check(not result.isError and len(result.content) == 2, "Payload build failed")
                metadata = json.loads(result.content[0].text)
                target, = metadata["regions"]
                check(metadata["schema_version"] == 1 and metadata["evidence_trust"] == "untrusted",
                      "Unexpected payload metadata")
                check(target["note"] == "Keep checkout spacing" and target["selected_text"] == "Checkout"
                      and target["pixel_bounds"] == bounds and target["region_id"] == note["region_id"],
                      "Payload lost saved context")
                part = result.content[target["image_index"]]
                check(part.type == "image" and part.mimeType == "image/png", "Expected PNG content")
                expected = image.crop((10, 16, 40, 48)) if mode == "crop" else image
                with Image.open(BytesIO(base64.b64decode(part.data, validate=True))) as decoded:
                    check(decoded.size == expected.size and decoded.tobytes() == expected.tobytes(),
                          "Payload pixels differ from the saved image")
                    print(f"Payload {mode}: schema=1; PNG={decoded.width}x{decoded.height}; pixels verified")

            with Catalog(library) as catalog:
                catalog.access.revoke_source("demo-assistant", saved["asset_id"])
            result = await session.call_tool("build_payload", params)
            check(result.isError and json.loads(result.content[0].text)["error"]["code"] == "access_denied",
                  "Revoked access still returned evidence")
            print("After grant revoke: access_denied")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="seenx-demo-") as temporary:
        asyncio.run(run_demo(Path(temporary)))
    print("PASS: offline demo; no model calls; temporary library removed.")


if __name__ == "__main__":
    main()
