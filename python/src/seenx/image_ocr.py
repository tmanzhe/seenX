"""Small macOS Vision adapter. No files are written or uploaded."""

from io import BytesIO
from importlib.metadata import version
import math
import platform
import sys

from PIL import ImageOps

COORDINATE_SPACE = "normalized_top_left_exif_corrected"


def vision_box_to_top_left(x: float, y: float, width: float, height: float) -> dict:
    values = (x, y, width, height)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("OCR box coordinates must be finite")
    tolerance = 1e-9
    if min(x, y) < -tolerance or width <= 0 or height <= 0 or x + width > 1 + tolerance or y + height > 1 + tolerance:
        raise ValueError("OCR box must fit inside the normalized image")
    left, right = max(0.0, x), min(1.0, x + width)
    top, bottom = max(0.0, 1 - y - height), min(1.0, 1 - y)
    if right <= left or bottom <= top:
        raise ValueError("OCR box has no area inside the image")
    return {"x": left, "y": top, "width": right - left, "height": bottom - top}


def _recognition_request(Vision):
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setRecognitionLanguages_(["en-US"])
    request.setUsesLanguageCorrection_(True)
    return request


def ocr_configuration() -> dict:
    check_ocr_available()
    import Vision
    import objc

    with objc.autorelease_pool():
        revision = int(_recognition_request(Vision).revision())
    return {"engine": "apple-vision", "request_revision": revision, "adapter_version": 2,
            "os_version": platform.mac_ver()[0], "bridge_version": version("pyobjc-framework-Vision"),
            "languages": ["en-US"], "recognition_level": "accurate", "language_correction": True,
            "coordinate_space": COORDINATE_SPACE}


def check_ocr_available() -> None:
    if sys.platform != "darwin":
        raise RuntimeError("--ocr currently requires macOS")
    try:
        import Vision
        import Foundation
        import objc
    except ImportError as error:
        raise RuntimeError("Install OCR support from the repo root: uv sync --project python --extra ocr") from error


def extract_image_observations(source) -> dict:
    configuration = ocr_configuration()
    import objc
    import Vision
    from Foundation import NSData, NSDictionary

    # Normalize orientation and format in memory, without making another file.
    with BytesIO() as buffer:
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.save(buffer, format="PNG")
        pixels = buffer.getvalue()

    with objc.autorelease_pool():
        data = NSData.dataWithBytes_length_(pixels, len(pixels))
        request = _recognition_request(Vision)
        try:
            options = NSDictionary.dictionary()
            handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(data, options)
            success, error = handler.performRequests_error_([request], None)
        except (ValueError, objc.error) as error:
            raise RuntimeError(f"Vision OCR failed: {error}") from error
        if not success:
            raise RuntimeError(f"Vision OCR failed: {error}")
        observations = []
        for observation in request.results() or []:
            candidates = observation.topCandidates_(1)
            if candidates:
                candidate = candidates[0]
                text = str(candidate.string())
                if not text.strip():
                    continue
                box = observation.boundingBox()
                confidence = float(candidate.confidence())
                try:
                    normalized = vision_box_to_top_left(float(box.origin.x), float(box.origin.y),
                                                       float(box.size.width), float(box.size.height))
                    if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                        raise ValueError("Invalid OCR confidence")
                except ValueError as error:
                    raise RuntimeError("Vision returned an invalid observation") from error
                observations.append({"text": text, "confidence": confidence, "box": normalized})
        return {"configuration": configuration, "width": image.width, "height": image.height,
                "coordinate_space": COORDINATE_SPACE, "observations": observations}


def extract_image_text(source) -> str:
    """Preserve the original string interface used by folder search."""
    return "\n".join(item["text"] for item in extract_image_observations(source)["observations"])
