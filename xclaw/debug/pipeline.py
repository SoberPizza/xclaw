"""Pipeline debug runner — dumps L1/L2 intermediate results to logs/debug/.

Usage:
    python -m xclaw.debug.pipeline [--depth l1|l2] [--image PATH]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from xclaw.config import LOGS_DIR, SCREENSHOTS_DIR


DEBUG_DIR = LOGS_DIR / "debug"


# ── Serializers ──────────────────────────────────────────────────────────────

def _serialize_element(e) -> dict:
    return {
        "id": e.id,
        "type": e.type,
        "bbox": list(e.bbox),
        "center": list(e.center),
        "content": e.content,
        "confidence": e.confidence,
        "source": e.source,
    }


def _serialize_column(c) -> dict:
    return {
        "id": c.id,
        "x_start": c.x_start,
        "x_end": c.x_end,
        "element_ids": c.element_ids,
    }


# ── Dump helpers ─────────────────────────────────────────────────────────────

def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _dump_l1(result) -> dict:
    """Write l1_perception.json and return stats."""
    text_count = sum(1 for e in result.elements if e.type == "text")
    icon_count = sum(1 for e in result.elements if e.type == "icon")

    data = {
        "resolution": list(result.resolution),
        "element_count": len(result.elements),
        "type_stats": {"text": text_count, "icon": icon_count},
        "elements": [_serialize_element(e) for e in result.elements],
    }
    _write_json(DEBUG_DIR / "l1_perception.json", data)

    return {"element_count": len(result.elements), "text_count": text_count, "icon_count": icon_count}


def _dump_l2(result) -> dict:
    """Write l2_spatial.json and return stats."""
    columns = result.columns or []
    reading_order = result.reading_order or []

    data = {
        "columns": [_serialize_column(c) for c in columns],
        "reading_order": reading_order,
    }
    _write_json(DEBUG_DIR / "l2_spatial.json", data)

    return {
        "column_count": len(columns),
        "reading_order_length": len(reading_order),
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def run(image_path: str | None = None, depth: str = "l2") -> None:
    """Execute the debug pipeline and write results to logs/debug/."""
    # Resolve depth flags
    skip_l2 = depth == "l1"

    # Screenshot
    if image_path is None:
        from xclaw.core.screen import take_screenshot

        print("Taking screenshot...")
        result = take_screenshot()
        image_path = result["image_path"]
        print(f"  → {image_path}")
    else:
        if not Path(image_path).exists():
            print(f"Error: image not found: {image_path}", file=sys.stderr)
            sys.exit(1)

    # Prepare output directory
    if DEBUG_DIR.exists():
        shutil.rmtree(DEBUG_DIR)
    DEBUG_DIR.mkdir(parents=True)

    # Run pipeline
    print(f"Running pipeline (depth={depth})...")
    from xclaw.core.pipeline import run_pipeline

    result = run_pipeline(image_path, skip_l2=skip_l2)

    # Dump each layer
    summary: dict = {
        "image_path": image_path,
        "resolution": list(result.resolution),
        "timing": result.timing,
    }

    print("  L1 perception...")
    summary["l1"] = _dump_l1(result)

    if not skip_l2:
        print("  L2 spatial...")
        summary["l2"] = _dump_l2(result)

    _write_json(DEBUG_DIR / "summary.json", summary)

    # Print summary
    print(f"\nDone. Output: {DEBUG_DIR}/")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline debug runner")
    parser.add_argument(
        "--depth",
        choices=["l1", "l2"],
        default="l2",
        help="Pipeline depth (default: l2)",
    )
    parser.add_argument(
        "--image",
        default=None,
        help="Path to existing screenshot (skip capture)",
    )
    args = parser.parse_args()
    run(image_path=args.image, depth=args.depth)


if __name__ == "__main__":
    main()
