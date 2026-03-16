"""OmniParser wrapper with standardized output."""

import sys
import json
import base64
from pathlib import Path

from xclaw.config import OMNIPARSER_DIR, OMNIPARSER_CONFIG, LOGS_DIR
from xclaw.core.perception.ocr import patch_paddleocr
from xclaw.core.perception.types import RawElement


class ScreenParser:
    """Thin wrapper around OmniParser with standardized output."""

    def __init__(self):
        patch_paddleocr()

        omniparser_dir = str(OMNIPARSER_DIR)
        if omniparser_dir not in sys.path:
            sys.path.insert(0, omniparser_dir)

        from util.omniparser import Omniparser

        self._parser = Omniparser(OMNIPARSER_CONFIG)

    def parse_raw(self, image_path: str) -> tuple[list[RawElement], tuple[int, int]]:
        """Parse a screenshot into RawElement list + resolution.

        This is the pipeline-friendly interface used by L2/L3.

        Returns:
            (elements, (width, height))
        """
        from PIL import Image

        img = Image.open(image_path)
        w, h = img.size

        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("ascii")

        _labeled_img, parsed_content_list = self._parser.parse(image_base64)

        elements = []
        for i, item in enumerate(parsed_content_list):
            bx1, by1, bx2, by2 = item["bbox"]
            x1 = int(bx1 * w)
            y1 = int(by1 * h)
            x2 = int(bx2 * w)
            y2 = int(by2 * h)
            cx = int((bx1 + bx2) / 2 * w)
            cy = int((by1 + by2) / 2 * h)

            elements.append(
                RawElement(
                    id=i,
                    type=item.get("type", "unknown"),
                    bbox=(x1, y1, x2, y2),
                    center=(cx, cy),
                    content=item.get("content", ""),
                )
            )

        return elements, (w, h)

    def parse(self, image_path: str) -> dict:
        """Parse a screenshot and return standardized element list (legacy format).

        Returns:
            {
                "status": "ok",
                "image_path": image_path,
                "elements": [...],
                "resolution": [width, height],
            }
        """
        elements, (w, h) = self.parse_raw(image_path)

        result = {
            "status": "ok",
            "image_path": image_path,
            "elements": [
                {
                    "id": e.id,
                    "type": e.type,
                    "bbox": list(e.bbox),
                    "center": list(e.center),
                    "content": e.content,
                }
                for e in elements
            ],
            "resolution": [w, h],
        }

        LOGS_DIR.mkdir(exist_ok=True)
        img_p = Path(image_path)
        json_path = LOGS_DIR / img_p.with_suffix(".json").name
        json_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        return result
