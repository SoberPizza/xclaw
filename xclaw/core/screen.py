import time

import mss
from PIL import Image

from xclaw.config import SCREENSHOTS_DIR, MAX_SCREENSHOTS


def take_screenshot(region=None) -> dict:
    """Take a screenshot using mss.

    Args:
        region: (x, y, w, h) tuple or None for full screen.

    Returns:
        {"status": "ok", "image_path": "screenshots/screen_xxx.png", "resolution": [w, h]}
    """
    SCREENSHOTS_DIR.mkdir(exist_ok=True)

    with mss.mss() as sct:
        if region:
            x, y, w, h = region
            monitor = {"left": x, "top": y, "width": w, "height": h}
        else:
            monitor = sct.monitors[0]  # entire virtual screen

        sct_img = sct.grab(monitor)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

    timestamp = int(time.time() * 1000)
    filename = f"screen_{timestamp}.png"
    image_path = SCREENSHOTS_DIR / filename
    img.save(str(image_path))

    # Enforce retention limit
    from xclaw.core.cleanup import enforce_max_files
    enforce_max_files(SCREENSHOTS_DIR, "screen_*.png", MAX_SCREENSHOTS)

    return {
        "status": "ok",
        "image_path": image_path.as_posix(),
        "resolution": [img.width, img.height],
    }
