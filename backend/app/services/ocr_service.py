"""OCR for scanned/image pages via PaddleOCR (lazy, optional).

PaddleOCR + PaddlePaddle are a heavy, optional install (the ``ocr`` extra). They are
imported lazily and the engine is warm-loaded once, so a deployment that only handles
digital PDFs never pays the cost. If OCR is needed but unavailable, callers get a
clear ``OcrUnavailableError`` (mapped to the ``ocr_failed`` report error_code).
"""

from __future__ import annotations

import io

from app.core.logging import get_logger

logger = get_logger(__name__)

_engine = None  # warm-loaded PaddleOCR instance


class OcrUnavailableError(RuntimeError):
    """Raised when OCR is required but PaddleOCR is not installed/initializable."""


def is_available() -> bool:
    try:
        import paddleocr  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def warm_up() -> bool:
    """Best-effort: initialize the engine at startup so first OCR isn't slow. Never raises."""
    try:
        _get_engine()
        return True
    except OcrUnavailableError:
        logger.info("OCR engine not available (the 'ocr' extra is not installed) — "
                    "digital PDFs still work; image pages will report ocr_failed.")
        return False


def _get_engine():
    global _engine
    if _engine is None:
        try:
            from paddleocr import PaddleOCR
        except Exception as exc:  # noqa: BLE001
            raise OcrUnavailableError(str(exc)) from exc
        try:
            _engine = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        except TypeError:
            # Older/newer PaddleOCR signatures differ; fall back to minimal kwargs.
            _engine = PaddleOCR(lang="en")
    return _engine


def ocr_image_png(png_bytes: bytes) -> tuple[str, float]:
    """OCR a single PNG image. Returns (text, mean_confidence in 0..1)."""
    import numpy as np
    from PIL import Image

    engine = _get_engine()
    image = np.array(Image.open(io.BytesIO(png_bytes)).convert("RGB"))

    try:
        result = engine.ocr(image, cls=True)
    except TypeError:
        result = engine.ocr(image)  # some versions dropped the cls kwarg

    lines: list[str] = []
    confs: list[float] = []
    for page in result or []:
        for entry in page or []:
            # entry == [box, (text, confidence)]
            try:
                text, conf = entry[1]
            except (IndexError, TypeError, ValueError):
                continue
            if text:
                lines.append(str(text))
                confs.append(float(conf))

    mean_conf = (sum(confs) / len(confs)) if confs else 0.0
    return "\n".join(lines), mean_conf
