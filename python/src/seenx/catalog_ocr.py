"""Immutable OCR observations for catalog revisions; model output stays unverified."""

import hashlib
from io import BytesIO
import json
import math
from uuid import uuid4

from PIL import Image

from seenx.catalog import target_geometry, timestamp
from seenx.image_ocr import COORDINATE_SPACE, extract_image_observations, ocr_configuration
from seenx.observability import event, stage


def configuration_identity(configuration: dict) -> tuple[str, str]:
    if not isinstance(configuration, dict) or not isinstance(configuration.get("engine"), str) or not configuration["engine"].strip():
        raise ValueError("OCR configuration must identify its engine")
    encoded = json.dumps(configuration, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest(), encoded


def read_ocr_run(connection, run_id: str) -> dict:
    run = connection.execute("SELECT * FROM ocr_runs WHERE id = ?", (run_id,)).fetchone()
    if run is None:
        raise LookupError("OCR run not found")
    result = dict(run)
    result["configuration"] = json.loads(result.pop("configuration_json"))
    result["coordinate_space"] = COORDINATE_SPACE
    rows = connection.execute("SELECT * FROM text_observations WHERE run_id = ? ORDER BY position", (run_id,)).fetchall()
    observations = []
    for row in rows:
        observation = dict(row)
        observation["box"] = {key: observation.pop(key) for key in ("x", "y", "width", "height")}
        observations.append(observation)
    result["observations"] = observations
    return result


def revision_ocr_runs(connection, revision_id: str) -> list:
    rows = connection.execute("SELECT id FROM ocr_runs WHERE revision_id = ? ORDER BY created_at, id", (revision_id,)).fetchall()
    return [read_ocr_run(connection, row["id"]) for row in rows]


def persist_observations(catalog, revision_id: str, result: dict) -> dict:
    connection = catalog.connection
    revision = connection.execute("SELECT * FROM revisions WHERE id = ?", (revision_id,)).fetchone()
    if revision is None:
        raise LookupError("Image revision not found")
    if not isinstance(result, dict):
        raise ValueError("OCR result must be a record")
    if result.get("coordinate_space") != COORDINATE_SPACE:
        raise ValueError("OCR observations use an incompatible coordinate system")
    if (result.get("width"), result.get("height")) != (revision["width"], revision["height"]):
        raise ValueError("OCR dimensions do not match the orientation-corrected revision")
    key, configuration_json = configuration_identity(result.get("configuration"))
    observations = result.get("observations")
    if not isinstance(observations, list):
        raise ValueError("OCR observations must be a list")
    prepared = []
    for observation in observations:
        if not isinstance(observation, dict):
            raise ValueError("OCR observation must be a record")
        text, confidence = observation.get("text"), observation.get("confidence")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Each OCR observation needs nonempty text")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("OCR confidence must be finite and between zero and one")
        box = observation.get("box")
        if not isinstance(box, dict) or not {"x", "y", "width", "height"} <= box.keys():
            raise ValueError("OCR observation needs a complete bounding box")
        _, x, y, width, height = target_geometry(region=[box["x"], box["y"], box["width"], box["height"]])
        prepared.append((text, confidence, x, y, width, height))
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute("SELECT id FROM ocr_runs WHERE revision_id = ? AND configuration_key = ?",
                                      (revision_id, key)).fetchone()
        reused = existing is not None
        run_id = existing["id"] if existing else uuid4().hex
        if not reused:
            connection.execute("INSERT INTO ocr_runs VALUES (?, ?, ?, ?, ?)",
                               (run_id, revision_id, key, configuration_json, timestamp()))
            for position, values in enumerate(prepared):
                connection.execute("""INSERT INTO text_observations
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ocr', 'unverified')""",
                    (uuid4().hex, run_id, position, *values))
    saved = read_ocr_run(connection, run_id)
    event("catalog_ocr_saved", revision_id=revision_id, ocr_run_id=run_id,
          observations=len(saved["observations"]), reused=reused)
    return {**saved, "reused": reused}


def recognize_revision(catalog, revision_id: str, configuration: dict | None = None, extractor=None) -> dict:
    revision, payload = catalog.read_revision_bytes(revision_id, trusted_local=True)
    expected = ocr_configuration() if configuration is None else configuration
    key, _ = configuration_identity(expected)
    existing = catalog.connection.execute("SELECT id FROM ocr_runs WHERE revision_id = ? AND configuration_key = ?",
                                          (revision_id, key)).fetchone()
    if existing is not None:
        event("catalog_ocr_reused", revision_id=revision_id, ocr_run_id=existing["id"])
        return {**read_ocr_run(catalog.connection, existing["id"]), "reused": True}
    extractor = extract_image_observations if extractor is None else extractor
    with stage("catalog_ocr", revision_id=revision_id):
        with Image.open(BytesIO(payload)) as source:
            result = extractor(source)
    actual_key, _ = configuration_identity(result["configuration"])
    if actual_key != key:
        raise ValueError("OCR configuration changed during recognition; refusing inconsistent provenance")
    return persist_observations(catalog, revision["id"], result)
