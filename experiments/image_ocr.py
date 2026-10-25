"""Small macOS Vision adapter. No files are written or uploaded."""

from io import BytesIO
import sys

from PIL import ImageOps


def check_ocr_available() -> None:
    if sys.platform != "darwin":
        raise RuntimeError("--ocr currently requires macOS")
    try:
        import Vision
        import Foundation
        import objc
    except ImportError as error:
        raise RuntimeError('Install OCR support: python -m pip install -e ".[ocr]"') from error


def extract_image_text(source) -> str:
    check_ocr_available()
    import objc
    import Vision
    from Foundation import NSData, NSDictionary

    # Normalize orientation and format in memory, without making another file.
    with BytesIO() as buffer:
        ImageOps.exif_transpose(source).convert("RGB").save(buffer, format="PNG")
        pixels = buffer.getvalue()

    with objc.autorelease_pool():
        data = NSData.dataWithBytes_length_(pixels, len(pixels))
        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        request.setRecognitionLanguages_(["en-US"])
        request.setUsesLanguageCorrection_(True)
        try:
            options = NSDictionary.dictionary()
            handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(data, options)
            success, error = handler.performRequests_error_([request], None)
        except (ValueError, objc.error) as error:
            raise RuntimeError(f"Vision OCR failed: {error}") from error
        if not success:
            raise RuntimeError(f"Vision OCR failed: {error}")
        lines = []
        for observation in request.results() or []:
            candidates = observation.topCandidates_(1)
            if candidates:
                lines.append(str(candidates[0].string()))
        return "\n".join(lines)
