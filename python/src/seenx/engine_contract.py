"""Version-1 read-only contract with owner-bound caller access; no MCP server."""

import base64
import hashlib
from io import BytesIO
import json
import logging
from pathlib import Path
import sqlite3

from PIL import Image, ImageOps

from seenx.catalog import SCHEMA_VERSION, pixel_edge
from seenx.catalog_access import identifier
from seenx.observability import count, event, run_context


PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 65_536
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
METHODS = {"engine.info", "memory.search", "memory.fetch", "region.fetch"}


class EngineError(Exception):
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)


def _identifier(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise EngineError("invalid_parameters", f"{name} must be a nonempty string of at most 128 characters")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise EngineError("invalid_parameters", f"{name} must contain valid Unicode") from None
    return value


def _boolean(params: dict, name: str, default: bool = False) -> bool:
    value = params.get(name, default)
    if not isinstance(value, bool):
        raise EngineError("invalid_parameters", f"{name} must be a boolean")
    return value


def _fields(params: dict, allowed: set, required: set = frozenset()) -> None:
    if set(params) - allowed or required - set(params):
        raise EngineError("invalid_parameters", "Missing required or unsupported parameter fields")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Nonfinite JSON number")


class LimitedImageBuffer(BytesIO):
    def write(self, data):
        if self.tell() + len(data) > MAX_IMAGE_BYTES:
            raise EngineError("resource_limit", "Encoded image exceeds the attachment limit; request a smaller saved region")
        return super().write(data)


class Engine:
    def __init__(self, catalog, *, principal_id: str | None = None, trusted_local: bool = False):
        # Caller identity/trust comes from the host, never request JSON.
        if type(trusted_local) is not bool or (trusted_local and principal_id is not None):
            raise ValueError("Choose either a grant-scoped principal or trusted local access")
        self.catalog = catalog
        self.principal_id = identifier(principal_id) if principal_id is not None else None
        self.trusted_local = trusted_local

    def _memory(self, params: dict) -> dict:
        asset_id = _identifier(params.get("asset_id"), "asset_id")
        revision_id = _identifier(params["revision_id"], "revision_id") if "revision_id" in params else None
        if not self.trusted_local and not self.catalog.access.allows(self.principal_id, asset_id):
            # Refuse before looking at revision IDs, snapshots, notes, or targets.
            raise EngineError("access_denied", "Requested memory is not granted to this caller")
        row = self.catalog.connection.execute("""
            SELECT r.sha256 FROM assets a JOIN revisions r
              ON r.id = coalesce(?, a.current_revision_id) AND r.asset_id = a.id
            WHERE a.id = ?
        """, (revision_id, asset_id)).fetchone()
        if row is None:
            raise LookupError("Memory revision not found")
        if self.catalog.object_path(row["sha256"]).stat().st_size > MAX_SOURCE_BYTES:
            raise EngineError("resource_limit", "Snapshot exceeds the verification size limit")
        memory = self.catalog.get_memory(asset_id, revision_id)
        source_name = Path(memory["asset"].pop("source_path")).name
        memory["asset"]["source_name"] = source_name
        memory["revision"].pop("snapshot_path")
        return memory

    def _image(self, revision_id: str, bounds: dict | None = None) -> dict:
        revision, payload = self.catalog.read_revision_bytes(revision_id)
        if len(payload) > MAX_SOURCE_BYTES or revision["width"] * revision["height"] > MAX_IMAGE_PIXELS:
            raise EngineError("resource_limit", "Image exceeds the decoding size limit")
        with Image.open(BytesIO(payload)) as source:
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise EngineError("resource_limit", "Image exceeds the decoding size limit")
            source.load()
            image = ImageOps.exif_transpose(source)
            if image.size != (revision["width"], revision["height"]):
                raise EngineError("evidence_unavailable", "Image dimensions differ from the saved revision")
            if bounds is not None:
                if bounds["right"] <= bounds["left"] or bounds["bottom"] <= bounds["top"]:
                    raise EngineError("evidence_unavailable", "Saved target has no pixel area")
                image = image.crop(tuple(bounds[key] for key in ("left", "top", "right", "bottom")))
            image = image.convert("RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB")
            with LimitedImageBuffer() as buffer:
                image.save(buffer, format="PNG")
                encoded = buffer.getvalue()
            return {"media_type": "image/png", "encoding": "base64",
                    "width": image.width, "height": image.height,
                    "sha256": hashlib.sha256(encoded).hexdigest(),
                    "data": base64.b64encode(encoded).decode("ascii")}

    def dispatch(self, method: str, params: dict):
        if method == "engine.info":
            _fields(params, set())
            return {"protocol_version": PROTOCOL_VERSION, "catalog_schema_version": SCHEMA_VERSION,
                    "methods": sorted(METHODS), "read_only_requests": True,
                    "limits": {"request_bytes": MAX_REQUEST_BYTES, "response_bytes": MAX_RESPONSE_BYTES,
                               "source_bytes": MAX_SOURCE_BYTES, "image_bytes": MAX_IMAGE_BYTES,
                               "image_pixels": MAX_IMAGE_PIXELS, "search_results": 100}}
        if method == "memory.search":
            _fields(params, {"query", "match", "limit", "asset_id", "revision_id", "current_only"}, {"query"})
            if not isinstance(params["query"], str) or not isinstance(params.get("match", "phrase"), str):
                raise EngineError("invalid_parameters", "query and match must be strings")
            for name in ("asset_id", "revision_id"):
                if name in params:
                    _identifier(params[name], name)
            return self.catalog.search(params["query"], match=params.get("match", "phrase"),
                limit=params.get("limit", 20), asset_id=params.get("asset_id"),
                revision_id=params.get("revision_id"), current_only=_boolean(params, "current_only"),
                principal_id=self.principal_id, trusted_local=self.trusted_local)
        if method == "memory.fetch":
            _fields(params, {"asset_id", "revision_id", "include_image"}, {"asset_id"})
            include_image = _boolean(params, "include_image")
            memory = self._memory(params)
            if include_image:
                memory["image"] = self._image(memory["revision"]["id"])
            return memory
        if method == "region.fetch":
            _fields(params, {"asset_id", "revision_id", "region_id", "observation_id", "include_image"},
                    {"asset_id", "revision_id"})
            include_image = _boolean(params, "include_image")
            if ("region_id" in params) == ("observation_id" in params):
                raise EngineError("invalid_parameters", "Supply exactly one region_id or observation_id")
            memory = self._memory(params)
            context = None
            if "region_id" in params:
                region_id = _identifier(params["region_id"], "region_id")
                note = next((item for item in memory["annotations"] if item["region_id"] == region_id), None)
                if note is not None:
                    context, target = {"annotation": note}, note["target"]
            else:
                observation_id = _identifier(params["observation_id"], "observation_id")
                observation = next((item for run in memory["ocr_runs"] for item in run["observations"]
                                    if item["id"] == observation_id), None)
                if observation is not None:
                    context, target = {"observation": observation}, {"kind": "region", **observation["box"]}
            if context is None:
                raise LookupError("Target not found for this revision")
            width, height = memory["revision"]["width"], memory["revision"]["height"]
            if target["kind"] == "point":
                left = min(width - 1, pixel_edge(target["x"], width))
                top = min(height - 1, pixel_edge(target["y"], height))
                bounds = {"left": left, "top": top, "right": left + 1, "bottom": top + 1}
            else:
                bounds = {"left": pixel_edge(target["x"], width), "top": pixel_edge(target["y"], height),
                          "right": min(width, pixel_edge(target["x"] + target["width"], width, True)),
                          "bottom": min(height, pixel_edge(target["y"] + target["height"], height, True))}
            result = {"asset_id": memory["asset"]["id"], "revision_id": memory["revision"]["id"],
                      "coordinate_space": memory["revision"]["coordinate_space"],
                      "reference_image": {"width": width, "height": height, "sha256": memory["revision"]["sha256"]},
                      "target": target, "pixel_bounds": bounds, **context}
            if include_image:
                result["image"] = self._image(result["revision_id"], bounds)
            return result
        raise EngineError("unknown_method", "Unsupported engine method")

    def handle(self, frame: bytes) -> bytes:
        request_id = None
        with run_context("engine_request") as trace_id:
            try:
                if len(frame) > MAX_REQUEST_BYTES:
                    raise EngineError("request_too_large", "Request exceeds the byte limit")
                try:
                    request = json.loads(frame.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
                except (ValueError, UnicodeError, RecursionError):
                    raise EngineError("invalid_json", "Expected one valid UTF-8 JSON object") from None
                if not isinstance(request, dict) or set(request) != {"version", "id", "method", "params"}:
                    raise EngineError("invalid_request", "Expected version, id, method, and params fields")
                try:
                    request_id = _identifier(request["id"], "id")
                except EngineError:
                    raise EngineError("invalid_request", "id must be a nonempty valid Unicode string of at most 128 characters") from None
                if isinstance(request["version"], bool) or not isinstance(request["version"], int) or request["version"] != PROTOCOL_VERSION:
                    raise EngineError("unsupported_version", "Supported protocol version is 1")
                method, params = request["method"], request["params"]
                if not isinstance(method, str) or method not in METHODS:
                    raise EngineError("unknown_method", "Unsupported engine method")
                if not isinstance(params, dict):
                    raise EngineError("invalid_parameters", "params must be an object")
                event("engine_request", method=method)
                result = self.dispatch(method, params)
                response = {"version": PROTOCOL_VERSION, "id": request_id, "trace_id": trace_id, "result": result}
                try:
                    encoded = json.dumps(response, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
                except (ValueError, TypeError, RecursionError):
                    raise EngineError("internal_error", "Engine produced an invalid response") from None
                if len(encoded) > MAX_RESPONSE_BYTES:
                    raise EngineError("response_too_large", "Response exceeds the byte limit; use bounded search or region fetch")
                count("engine_requests_succeeded")
                event("engine_response", method=method, response_bytes=len(encoded), outcome="ok")
                return encoded
            except EngineError as error:
                code, message = error.code, error.message
            except KeyError:
                code, message = "internal_error", "Stored data was incomplete"
            except LookupError:
                code, message = "not_found", "Requested memory, revision, or target was not found"
            except ValueError:
                code, message = "invalid_parameters", "Invalid query, filter, or parameter value"
            except (OSError, Image.DecompressionBombError):
                code, message = "evidence_unavailable", "Stored image could not be read or verified"
            except sqlite3.Error:
                code, message = "storage_error", "Catalog operation failed"
            except Exception:
                code, message = "internal_error", "Unexpected engine failure"
            count("engine_requests_failed")
            event("engine_response", level=logging.WARNING, outcome="error", code=code)
            return json.dumps({"version": PROTOCOL_VERSION, "id": request_id, "trace_id": trace_id,
                               "error": {"code": code, "message": message}}, separators=(",", ":")).encode()
