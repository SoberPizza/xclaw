"""Stub out PaddleOCR to prevent OmniParser from loading the real (noisy) package."""

import sys
import types

_installed = False


def install_paddleocr_stub():
    """Inject a fake 'paddleocr' module so OmniParser's module-level
    `from paddleocr import PaddleOCR; paddle_ocr = PaddleOCR(...)` becomes a no-op.
    Must be called BEFORE OmniParser is imported."""
    global _installed
    if _installed:
        return
    _installed = True

    if "paddleocr" in sys.modules:
        return  # real package already loaded, too late

    class _PaddleOCRStub:
        """Drop-in stub: constructor accepts anything, .ocr() returns empty."""
        def __init__(self, *a, **kw):
            pass
        def ocr(self, *a, **kw):
            return [[]]

    mod = types.ModuleType("paddleocr")
    mod.PaddleOCR = _PaddleOCRStub
    sys.modules["paddleocr"] = mod
