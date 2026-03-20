import time

import mss
from PIL import Image

from xclaw.config import SCREENSHOTS_DIR


def take_screenshot(region=None) -> dict:
    """Take a screenshot using mss.

    Args:
        region: (x, y, w, h) tuple or None for full screen.

    Returns:
        {"status": "ok", "image_path": "screenshots/screen_xxx.png",
         "resolution": [w, h], "timing": {"grab_ms": ..., "convert_ms": ..., "save_ms": ...}}
    """
    SCREENSHOTS_DIR.mkdir(exist_ok=True)

    t = time.perf_counter_ns()
    with mss.mss() as sct:
        if region:
            x, y, w, h = region
            monitor = {"left": x, "top": y, "width": w, "height": h}
        else:
            monitor = sct.monitors[0]  # entire virtual screen

        sct_img = sct.grab(monitor)
    grab_ms = (time.perf_counter_ns() - t) // 1_000_000

    t = time.perf_counter_ns()
    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
    convert_ms = (time.perf_counter_ns() - t) // 1_000_000

    timestamp = int(time.time() * 1000)
    filename = f"screen_{timestamp}.png"
    image_path = SCREENSHOTS_DIR / filename

    t = time.perf_counter_ns()
    img.save(str(image_path))
    save_ms = (time.perf_counter_ns() - t) // 1_000_000

    _cleanup_screenshots()

    return {
        "status": "ok",
        "image_path": image_path.as_posix(),
        "resolution": [img.width, img.height],
        "timestamp": timestamp,
        "timing": {
            "grab_ms": grab_ms,
            "convert_ms": convert_ms,
            "save_ms": save_ms,
        },
    }


def _cleanup_screenshots(keep: int = 20) -> None:
    """Remove old screenshots, keeping the most recent *keep* files."""
    try:
        files = sorted(SCREENSHOTS_DIR.glob("screen_*.png"))
        for f in files[:-keep]:
            f.unlink(missing_ok=True)
    except OSError:
        pass
