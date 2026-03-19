#!/usr/bin/env python3
"""Build lightweight X-Claw installer packages.

macOS:   python scripts/build_installer.py --platform macos   → dist/XClaw-<ver>.pkg
Windows: python scripts/build_installer.py --platform windows → dist/ (ready for Inno Setup)

The installer contains only xclaw source + uv binary (~30 MB compressed).
All heavy dependencies are downloaded online during first launch.
"""

import argparse
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BUILD_DIR = PROJECT_ROOT / "build"
DIST_DIR = PROJECT_ROOT / "dist"

UV_BASE_URL = "https://github.com/astral-sh/uv/releases/latest/download"
UV_TARGETS = {
    "macos": "uv-aarch64-apple-darwin.tar.gz",
    "windows": "uv-x86_64-pc-windows-msvc.zip",
}

# Files/dirs to copy as xclaw-src
XCLAW_SRC_ITEMS = [
    "xclaw",
    "pyproject.toml",
    ".python-version",
]


def get_version() -> str:
    toml = (PROJECT_ROOT / "pyproject.toml").read_text()
    for line in toml.splitlines():
        if line.strip().startswith("version"):
            return line.split('"')[1]
    return "0.0.0"


# ── uv download ──


def download_uv(target_platform: str, dest: Path) -> Path:
    """Download the uv binary for the given platform. Returns path to the binary."""
    archive_name = UV_TARGETS[target_platform]
    url = f"{UV_BASE_URL}/{archive_name}"
    archive_path = BUILD_DIR / archive_name

    if not archive_path.exists():
        print(f"  Downloading uv from {url} ...")
        urllib.request.urlretrieve(url, archive_path)

    if archive_name.endswith(".tar.gz"):
        with tarfile.open(archive_path) as tar:
            for member in tar.getmembers():
                if member.name.endswith("/uv") or member.name == "uv":
                    member.name = "uv"
                    tar.extract(member, dest)
                    uv_path = dest / "uv"
                    uv_path.chmod(uv_path.stat().st_mode | stat.S_IEXEC)
                    return uv_path
    elif archive_name.endswith(".zip"):
        with zipfile.ZipFile(archive_path) as zf:
            for name in zf.namelist():
                if name.endswith("uv.exe"):
                    data = zf.read(name)
                    uv_path = dest / "uv.exe"
                    uv_path.write_bytes(data)
                    return uv_path

    raise RuntimeError(f"Could not find uv binary in {archive_name}")


def copy_xclaw_src(dest: Path):
    """Copy xclaw source tree + pyproject.toml into dest/."""
    dest.mkdir(parents=True, exist_ok=True)
    for item in XCLAW_SRC_ITEMS:
        src = PROJECT_ROOT / item
        dst = dest / item
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        elif src.is_file():
            shutil.copy2(src, dst)
    print(f"  Copied xclaw source to {dest}")


# ── macOS ──


def build_macos():
    version = get_version()
    app_name = "X-Claw.app"
    app_dir = BUILD_DIR / app_name / "Contents"
    macos_dir = app_dir / "MacOS"
    res_dir = app_dir / "Resources"

    # Clean
    if (BUILD_DIR / app_name).exists():
        shutil.rmtree(BUILD_DIR / app_name)
    macos_dir.mkdir(parents=True)
    res_dir.mkdir(parents=True)

    # 1. Info.plist
    plist_template = (SCRIPT_DIR / "macos" / "Info.plist.template").read_text()
    plist = plist_template.replace("${VERSION}", version)
    (app_dir / "Info.plist").write_text(plist)

    # 2. uv binary
    print("Downloading uv for macOS ...")
    download_uv("macos", res_dir)

    # 3. xclaw source
    copy_xclaw_src(res_dir / "xclaw-src")

    # 4. Launcher: MacOS/xclaw
    launcher = macos_dir / "xclaw"
    launcher.write_text("""\
#!/bin/bash
APPDIR="$(cd "$(dirname "$0")/.." && pwd)"
RES="$APPDIR/Resources"
VENV="$HOME/Library/Application Support/X-Claw/.venv"
export XCLAW_HOME="$RES/xclaw-src"
export XCLAW_DATA="$HOME/Library/Application Support/X-Claw"

# First run: auto-install
if [ ! -d "$VENV" ]; then
    exec "$APPDIR/MacOS/xclaw-setup"
fi

exec "$VENV/bin/python" -m xclaw.cli "$@"
""")
    launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC)

    # 5. Setup launcher: MacOS/xclaw-setup
    setup_launcher = macos_dir / "xclaw-setup"
    setup_launcher.write_text("""\
#!/bin/bash
set -e
APPDIR="$(cd "$(dirname "$0")/.." && pwd)"
RES="$APPDIR/Resources"
UV="$RES/uv"
XCLAW_SRC="$RES/xclaw-src"
export XCLAW_DATA="$HOME/Library/Application Support/X-Claw"
VENV="$XCLAW_DATA/.venv"

echo "=== X-Claw 首次安装 ==="
echo "正在安装 Python 和依赖 (约 1.5 GB) ..."

# uv sync installs Python + all deps
cd "$XCLAW_SRC"
"$UV" sync --extra mac --python 3.12

echo "正在下载模型 ..."
# Run post-install (model download + init)
export XCLAW_HOME="$XCLAW_SRC"
"$VENV/bin/python" -m xclaw.installer.postinstall

echo "=== 安装完成！==="
""")
    setup_launcher.chmod(setup_launcher.stat().st_mode | stat.S_IEXEC)

    # 6. Icon placeholder
    icon_src = SCRIPT_DIR / "resources" / "icon.icns"
    if icon_src.exists():
        shutil.copy2(icon_src, res_dir / "icon.icns")

    # 7. Build .pkg
    DIST_DIR.mkdir(exist_ok=True)
    pkg_path = DIST_DIR / f"XClaw-{version}.pkg"

    # Prepare pkg scripts dir
    pkg_scripts = BUILD_DIR / "pkg-scripts"
    if pkg_scripts.exists():
        shutil.rmtree(pkg_scripts)
    pkg_scripts.mkdir()
    postinstall_sh = SCRIPT_DIR / "macos" / "postinstall.sh"
    shutil.copy2(postinstall_sh, pkg_scripts / "postinstall")
    (pkg_scripts / "postinstall").chmod(0o755)

    # pkgbuild
    subprocess.run([
        "pkgbuild",
        "--root", str(BUILD_DIR / app_name),
        "--install-location", f"/Applications/{app_name}",
        "--scripts", str(pkg_scripts),
        "--identifier", "com.xclaw.app",
        "--version", version,
        str(pkg_path),
    ], check=True)

    pkg_mb = pkg_path.stat().st_size / (1024 * 1024)
    print(f"\n✅ macOS installer: {pkg_path}  ({pkg_mb:.1f} MB)")


# ── Windows ──


def build_windows():
    version = get_version()
    win_dir = BUILD_DIR / "windows"

    if win_dir.exists():
        shutil.rmtree(win_dir)
    win_dir.mkdir(parents=True)

    # 1. uv binary
    print("Downloading uv for Windows ...")
    download_uv("windows", win_dir)

    # 2. xclaw source
    copy_xclaw_src(win_dir / "xclaw-src")

    # 3. xclaw.bat launcher
    (win_dir / "xclaw.bat").write_text("""\
@echo off
set XCLAW_HOME=%~dp0xclaw-src
set XCLAW_DATA=%LOCALAPPDATA%\\X-Claw
set VENV=%LOCALAPPDATA%\\X-Claw\\.venv

if not exist "%VENV%\\Scripts\\python.exe" (
    call "%~dp0xclaw-setup.bat"
)
"%VENV%\\Scripts\\python.exe" -m xclaw.cli %*
""")

    # 4. xclaw-setup.bat
    (win_dir / "xclaw-setup.bat").write_text("""\
@echo off
echo === X-Claw First-Time Setup ===
echo Installing Python and dependencies (~1.8 GB) ...

set XCLAW_SRC=%~dp0xclaw-src
set XCLAW_DATA=%LOCALAPPDATA%\\X-Claw
set XCLAW_HOME=%XCLAW_SRC%
set VENV=%LOCALAPPDATA%\\X-Claw\\.venv

cd /d "%XCLAW_SRC%"
"%~dp0uv.exe" sync --extra win --python 3.12

echo Downloading models ...
"%VENV%\\Scripts\\python.exe" -m xclaw.installer.postinstall

echo === Setup complete! ===
""")

    # 5. Check for Inno Setup compiler
    DIST_DIR.mkdir(exist_ok=True)
    iss_path = SCRIPT_DIR / "installer.iss"

    iscc = shutil.which("iscc") or shutil.which("ISCC")
    if iscc and iss_path.exists():
        subprocess.run([iscc, str(iss_path)], check=True)
        print(f"\n✅ Windows installer built in {DIST_DIR}/")
    else:
        print(f"\n✅ Windows build staged at {win_dir}")
        if not iscc:
            print("   Inno Setup (iscc) not found — run iscc scripts/installer.iss manually.")


# ── Main ──


def main():
    parser = argparse.ArgumentParser(description="Build X-Claw installer")
    parser.add_argument(
        "--platform",
        choices=["macos", "windows", "auto"],
        default="auto",
        help="Target platform (default: auto-detect)",
    )
    args = parser.parse_args()

    BUILD_DIR.mkdir(exist_ok=True)

    target = args.platform
    if target == "auto":
        target = "macos" if platform.system() == "Darwin" else "windows"

    print(f"Building X-Claw installer for {target} ...")
    print(f"  Version: {get_version()}")
    print(f"  Build:   {BUILD_DIR}")
    print(f"  Dist:    {DIST_DIR}")
    print()

    if target == "macos":
        build_macos()
    elif target == "windows":
        build_windows()


if __name__ == "__main__":
    main()
