#!/usr/bin/env python3
"""X-Claw cross-platform model downloader.

Total download: ~1.3 GB

macOS: uv run --extra mac python scripts/download_models.py
Win:   uv run --extra win python scripts/download_models.py
"""

import os
import platform
import subprocess
import sys
from pathlib import Path

# Uncomment for Chinese users:
# os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

OMNIPARSER_REPO = "microsoft/OmniParser-v2.0"
OMNIPARSER_FILES = [
    "icon_detect/model.pt",
    "icon_detect/model.yaml",
    "icon_detect/train_args.yaml",
    "icon_caption/config.json",
    "icon_caption/generation_config.json",
    "icon_caption/model.safetensors",
]


def download_omniparser(dest_dir: Path, progress_callback=None) -> bool:
    """Download OmniParser V2 models to *dest_dir*.

    *progress_callback*, if provided, is called as ``cb(file_index, total, filename)``
    before each file download starts.

    Returns True on success.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    total = len(OMNIPARSER_FILES)

    for idx, f in enumerate(OMNIPARSER_FILES):
        if progress_callback:
            progress_callback(idx, total, f)
        else:
            print(f"  ↓ {f}")

        subprocess.run(
            [
                sys.executable, "-m", "huggingface_hub", "download",
                OMNIPARSER_REPO, f, "--local-dir", str(dest_dir),
            ],
            check=True,
        )

    # Rename icon_caption → icon_caption_florence
    src = dest_dir / "icon_caption"
    dst = dest_dir / "icon_caption_florence"
    if src.exists() and not dst.exists():
        src.rename(dst)
        if not progress_callback:
            print(f"  Renamed {src.name} → {dst.name}")

    if progress_callback:
        progress_callback(total, total, "done")
    return True


def init_paddleocr() -> bool:
    """Trigger PaddleOCR first-run model download. Returns True on success."""
    try:
        from paddleocr import PaddleOCR
        PaddleOCR(use_angle_cls=True, lang="ch", use_gpu=False, show_log=True)
        return True
    except ImportError:
        print("  paddleocr not installed. Run: uv sync --extra mac (or --extra win)")
        return False


def verify_models(model_dir: Path) -> bool:
    """Check that required model files exist in *model_dir*. Returns True if all present."""
    checks = {
        "YOLO": model_dir / "icon_detect" / "model.pt",
        "Florence-2": model_dir / "icon_caption_florence" / "model.safetensors",
    }
    all_ok = True
    for name, path in checks.items():
        if path.exists():
            mb = path.stat().st_size / (1024 * 1024)
            print(f"  ✅ {name}: {mb:.1f} MB")
        else:
            print(f"  ❌ {name}: MISSING at {path}")
            all_ok = False
    return all_ok


# ── Default target when running as script ──

MODELS = Path(__file__).parent.parent / "models"


def main():
    MODELS.mkdir(exist_ok=True)

    print("=" * 60)
    print("  X-Claw Model Downloader")
    print(f"  Platform: {platform.system()} {platform.machine()}")
    print(f"  Target:   {MODELS}")
    print("=" * 60)

    # 1. OmniParser V2
    print(f"\n📦 OmniParser V2 (~1.12 GB)")
    download_omniparser(MODELS)

    # 2. PaddleOCR
    print("\n📦 PaddleOCR v4 (auto-download on first use)")
    if init_paddleocr():
        print("  ✅ PaddleOCR ready")

    # 3. Verify
    print("\n🔍 Verification:")
    if verify_models(MODELS):
        print("\n✅ All models ready!")
    else:
        print("\n⚠️  Some models are missing. Check the output above.")


if __name__ == "__main__":
    main()
