"""CLI core — logging setup and output function."""

import os
import sys
import logging

IS_DEBUG = os.environ.get("DEBUG", "0") == "1"


def setup():
    """CLI initialization: configure DPI awareness and logging."""
    # Per-Monitor DPI Aware — 让 GetSystemMetrics / SendInput 使用物理像素，
    # 与 mss 截图坐标体系一致。必须在任何 user32 调用之前设置。
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except (AttributeError, OSError):
        ctypes.windll.user32.SetProcessDPIAware()

    root = logging.getLogger()
    root.handlers.clear()

    if IS_DEBUG:
        h = logging.StreamHandler(sys.stderr)
        h.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        ))
        root.addHandler(h)
        root.setLevel(logging.DEBUG)
    else:
        root.addHandler(logging.NullHandler())
        root.setLevel(logging.CRITICAL + 1)

        import warnings
        warnings.filterwarnings("ignore")

        # Silence stderr (prevent third-party library noise)
        sys.stderr = open(os.devnull, "w")


def output(text: str):
    """The single output function — this is what the LLM sees."""
    # Use binary write with UTF-8 to avoid GBK encoding errors on Chinese Windows
    sys.__stdout__.buffer.write((str(text) + "\n").encode("utf-8"))
    sys.__stdout__.buffer.flush()
