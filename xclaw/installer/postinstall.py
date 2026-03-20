"""Post-install initialization for X-Claw.

Can be run standalone:  python -m xclaw.installer.postinstall
Or via CLI:             xclaw setup

Flow:
1. Create DATA_DIR directory structure
2. Check if models already exist
3. If missing → launch download GUI (Tkinter)
4. Run ``xclaw init`` to verify
5. Write .installed marker
"""

import subprocess
import sys
from pathlib import Path


def run_postinstall() -> int:
    """Run the full post-install sequence. Returns 0 on success."""
    from xclaw.config import DATA_DIR, MODELS_DIR

    # 1. Create directory structure
    for subdir in ("models", "screenshots", "logs"):
        (DATA_DIR / subdir).mkdir(parents=True, exist_ok=True)
    print(f"[setup] Data directory: {DATA_DIR}")

    # 2. Check models
    model_dir = MODELS_DIR
    need_download = not _models_present(model_dir)

    if need_download:
        # Prefer DATA_DIR/models for installed mode
        if not (DATA_DIR / "pyproject.toml").exists():
            model_dir = DATA_DIR / "models"
            model_dir.mkdir(parents=True, exist_ok=True)

        print("[setup] Models not found — launching download ...")
        try:
            from xclaw.installer.download_gui import run_download_gui
            ok = run_download_gui(model_dir)
        except Exception as exc:
            print(f"[setup] GUI failed ({exc}), falling back to CLI download ...")
            ok = _cli_download(model_dir)

        if not ok:
            print("[setup] Model download failed.")
            return 1
    else:
        print(f"[setup] Models already present at {model_dir}")

    # 4. Verify via xclaw init
    print("[setup] Running xclaw init ...")
    ret = subprocess.call([sys.executable, "-m", "xclaw.cli", "init"])
    if ret != 0:
        print("[setup] xclaw init failed.")
        return ret

    # 5. Write marker
    marker = DATA_DIR / ".installed"
    marker.write_text("1")
    print("[setup] Installation complete!")
    return 0


def _models_present(model_dir: Path) -> bool:
    return (
        (model_dir / "icon_detect" / "model.pt").exists()
        and (model_dir / "icon_classify_siglip" / "config.json").exists()
    )


def _cli_download(model_dir: Path) -> bool:
    """Fallback: download models via CLI (no GUI)."""
    try:
        # Add scripts/ to path so we can import download_models
        scripts_dir = str(Path(__file__).resolve().parents[2] / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from download_models import download_omniparser
        download_omniparser(model_dir)
        return _models_present(model_dir)
    except Exception as exc:
        print(f"[setup] CLI download error: {exc}")
        return False


if __name__ == "__main__":
    sys.exit(run_postinstall())
