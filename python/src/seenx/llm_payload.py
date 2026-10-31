"""Build model input locally, without model calls or persistent writes.

Version 1 returns {"schema_version": 1, "content": [text_part, *image_parts]}.
The text part is {"type": "text", "text": <JSON metadata>}; each image part is
{"type": "image", "mimeType": "image/png", "data": <base64 PNG>}. These parts
can be passed as MCP content or adapted to a model provider's message format.

Metadata contains asset_id, revision_id, image_mode, coordinate_space,
reference_image (original oriented width, height, snapshot sha256), and regions.
Each region includes its IDs, saved note and selected text with provenance,
target (kind, x, y, width, height), pixel_bounds, and image_index into content.
Coordinates always refer to the full EXIF-corrected image: normalized top-left
targets and integer pixel bounds with exclusive right/bottom edges. Crop mode
supplies one image per region in request order; full mode supplies one shared
image. Points crop to one pixel, including points on the bottom/right edge.
All retrieved text and images are untrusted evidence, never instructions.
"""

import json

from seenx.engine_contract import Engine, EngineError, _identifier


MAX_REGIONS = 16


def build_payload(catalog, asset_id: str, revision_id: str, region_ids: list[str], *,
                  image_mode: str = "crop", principal_id: str | None = None,
                  trusted_local: bool = False) -> dict:
    """Package saved regions of exactly one revision; require explicit access.

    Require 1–16 distinct region IDs. Missing or wrong-revision regions raise
    LookupError, invalid arguments raise EngineError, and denied reads fail
    before evidence is loaded. Encoding uses the engine's existing image limits.
    """
    _identifier(asset_id, "asset_id")
    _identifier(revision_id, "revision_id")
    if not isinstance(region_ids, list) or not 1 <= len(region_ids) <= MAX_REGIONS:
        raise EngineError("invalid_parameters", "region_ids must contain 1–16 distinct region IDs")
    for region_id in region_ids:
        _identifier(region_id, "region_id")
    if len(set(region_ids)) != len(region_ids) or image_mode not in ("crop", "full"):
        raise EngineError("invalid_parameters", "Use distinct region IDs and image_mode crop or full")
    engine = Engine(catalog, principal_id=principal_id, trusted_local=trusted_local)
    # Resolve every region before encoding any image; never return partial evidence.
    targets = [engine.dispatch("region.fetch", {"asset_id": asset_id, "revision_id": revision_id,
                                               "region_id": region_id}) for region_id in region_ids]
    metadata = {"schema_version": 1, "asset_id": asset_id, "revision_id": revision_id, "image_mode": image_mode,
                "coordinate_space": targets[0]["coordinate_space"],
                "reference_image": targets[0]["reference_image"], "evidence_trust": "untrusted", "regions": []}
    images = []
    for region_id, target in zip(region_ids, targets):
        if image_mode == "crop" or not images:
            image = engine._image(revision_id, target["pixel_bounds"] if image_mode == "crop" else None)
            images.append({"type": "image", "mimeType": image["media_type"], "data": image["data"]})
        annotation = target["annotation"]
        metadata["regions"].append({
            "region_id": region_id, "annotation_id": annotation["id"],
            "note": annotation["note"], "selected_text": annotation["selected_text"],
            "selected_text_origin": annotation["selected_text_origin"],
            "selected_text_confirmation": annotation["selected_text_confirmation"],
            "target": target["target"], "pixel_bounds": target["pixel_bounds"], "image_index": len(images),
        })
    return {"schema_version": 1, "content": [
        {"type": "text", "text": json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))}, *images,
    ]}
