#!/usr/bin/env python3
"""X-Claw cross-platform model downloader.

Total download: ~1.5 GB (YOLO ~40MB + SigLIP 2 ~1.4GB + PaddleOCR auto-download)

macOS: uv run --extra mac python scripts/download_models.py
Win:   uv run --extra win python scripts/download_models.py
"""

import hashlib
import os
import platform
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download, snapshot_download

# Uncomment for Chinese users:
# os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

OMNIPARSER_REPO = "microsoft/OmniParser-v2.0"
OMNIPARSER_FILES = [
    "icon_detect/model.pt",
    "icon_detect/model.yaml",
    "icon_detect/train_args.yaml",
]

SIGLIP_REPO = "google/siglip2-base-patch16-224"

# SHA256 prefix manifest — warn-only, does not block loading.
# Compute with: python -c "import hashlib; print(hashlib.sha256(open(f,'rb').read()).hexdigest()[:16])"
# Set to None for files where the hash is not yet known.
MODEL_MANIFEST: dict[str, dict] = {
    "icon_detect/model.pt": {"min_size_mb": 20},
    "icon_detect/model.yaml": {"min_size_mb": 0.001},
    "icon_classify_siglip/model.safetensors": {"min_size_mb": 500},
}


def _sha256_prefix(path: Path, prefix_len: int = 16) -> str:
    """Return the first *prefix_len* hex chars of a file's SHA256."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:prefix_len]


def _download_with_retry(
    download_fn,
    max_retries: int = 3,
    label: str = "",
) -> None:
    """Call *download_fn* with exponential-backoff retry."""
    import time

    for attempt in range(max_retries):
        try:
            download_fn()
            return
        except Exception:
            if attempt == max_retries - 1:
                raise
            wait = (2 ** attempt) * 2  # 2s, 4s, 8s
            desc = f" ({label})" if label else ""
            print(f"  ⚠ Download failed{desc}, retrying in {wait}s... ({attempt + 1}/{max_retries})")
            time.sleep(wait)


def download_omniparser(dest_dir: Path, progress_callback=None) -> bool:
    """Download OmniParser V2 models + SigLIP 2 to *dest_dir*.

    *progress_callback*, if provided, is called as ``cb(file_index, total, filename)``
    before each file download starts.

    Returns True on success.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    total = len(OMNIPARSER_FILES) + 1  # +1 for SigLIP 2

    for idx, f in enumerate(OMNIPARSER_FILES):
        if progress_callback:
            progress_callback(idx, total, f)
        else:
            print(f"  ↓ {f}")

        _download_with_retry(
            lambda f=f: hf_hub_download(
                OMNIPARSER_REPO, f, local_dir=str(dest_dir),
            ),
            label=f,
        )

    # Download SigLIP 2 B/16
    idx = len(OMNIPARSER_FILES)
    if progress_callback:
        progress_callback(idx, total, "SigLIP-2")
    else:
        print(f"  ↓ SigLIP 2 B/16 (icon classifier)")

    siglip_dir = dest_dir / "icon_classify_siglip"
    _download_with_retry(
        lambda: snapshot_download(
            SIGLIP_REPO, local_dir=str(siglip_dir),
        ),
        label="SigLIP-2",
    )

    if progress_callback:
        progress_callback(total, total, "done")
    return True


def init_paddleocr() -> bool:
    """Trigger PaddleOCR first-run model download. Returns True on success."""
    try:
        from paddleocr import PaddleOCR
        PaddleOCR(use_textline_orientation=True, lang="ch", device="cpu")
        return True
    except ImportError as e:
        print(f"  paddleocr init failed: {e}")
        print("  Run: uv sync --extra mac (or --extra win)")
        return False
    except Exception as e:
        print(f"  paddleocr init failed: {e}")
        return False


def export_yolo_onnx(model_dir: Path) -> bool:
    """Export YOLO .pt to .onnx if not already present. Returns True on success."""
    pt_path = model_dir / "icon_detect" / "model.pt"
    onnx_path = model_dir / "icon_detect" / "model.onnx"

    if onnx_path.exists():
        mb = onnx_path.stat().st_size / (1024 * 1024)
        print(f"  ✅ ONNX already exists: {mb:.1f} MB")
        return True

    if not pt_path.exists():
        print("  ⚠ YOLO .pt not found, skipping ONNX export")
        return False

    try:
        from ultralytics import YOLO

        print("  Exporting .pt → .onnx ...")
        model = YOLO(str(pt_path))
        model.export(format="onnx", imgsz=640, simplify=True, opset=17)

        # ultralytics may produce the file next to .pt with a different name
        if not onnx_path.exists():
            exported = list(pt_path.parent.glob("*.onnx"))
            if exported:
                exported[0].rename(onnx_path)

        if onnx_path.exists():
            mb = onnx_path.stat().st_size / (1024 * 1024)
            print(f"  ✅ ONNX export complete: {mb:.1f} MB")
            return True
        else:
            print("  ⚠ ONNX export produced no file")
            return False
    except Exception as e:
        print(f"  ⚠ ONNX export failed: {e}")
        return False


def verify_models(model_dir: Path) -> bool:
    """Check that required model files exist in *model_dir*.

    Validates file existence, minimum size, and SHA256 prefix (if known).
    Returns True if all critical checks pass.
    """
    checks = {
        "YOLO": model_dir / "icon_detect" / "model.pt",
        "YOLO ONNX": model_dir / "icon_detect" / "model.onnx",
        "SigLIP 2": model_dir / "icon_classify_siglip" / "model.safetensors",
    }
    all_ok = True
    for name, path in checks.items():
        if path.exists():
            mb = path.stat().st_size / (1024 * 1024)
            # Check minimum size from manifest
            rel = str(path.relative_to(model_dir))
            manifest_entry = MODEL_MANIFEST.get(rel, {})
            min_mb = manifest_entry.get("min_size_mb", 0)
            if mb < min_mb:
                print(f"  ⚠️  {name}: {mb:.1f} MB (expected >= {min_mb} MB, possibly truncated)")
                all_ok = False
            else:
                status = f"✅ {name}: {mb:.1f} MB"
                # SHA256 check if hash is known
                expected_hash = manifest_entry.get("sha256_prefix")
                if expected_hash:
                    actual_hash = _sha256_prefix(path)
                    if actual_hash != expected_hash:
                        status += f" ⚠ hash mismatch (got {actual_hash}, expected {expected_hash})"
                print(f"  {status}")
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

    # 1. OmniParser V2 + SigLIP 2
    print(f"\n📦 OmniParser V2 + SigLIP 2 (~1.5 GB)")
    download_omniparser(MODELS)

    # 2. YOLO ONNX export
    print("\n📦 YOLO ONNX export (recommended backend)")
    export_yolo_onnx(MODELS)

    # 3. Verify
    print("\n🔍 Verification:")
    if verify_models(MODELS):
        print("\n✅ All models ready!")
    else:
        print("\n⚠️  Some models are missing. Check the output above.")


if __name__ == "__main__":
    main()
