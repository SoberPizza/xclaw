"""
X-Claw 环境检查 v2.1
"""
import sys
import os

def check(name, test_fn):
    try:
        result = test_fn()
        print(f"  ✅ {name}: {result}")
        return True
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        return False


print()
print("=" * 55)
print("  X-Claw 环境检查 v2.1")
print("=" * 55)

all_ok = True

# ── Phase 1: Python ──────────────────────────────────
print()
print("  📦 Phase 1: Python")
print("  " + "-" * 50)

all_ok &= check("Python version", lambda: (
    f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    + (" ✅ ≥3.12" if sys.version_info >= (3, 12) else " ⚠️ 推荐 3.12+")
))

all_ok &= check("uv 虚拟环境", lambda: (
    "activated ✅" if ".venv" in sys.prefix else f"⚠️ prefix={sys.prefix}"
))

# ── Phase 2: GPU ─────────────────────────────────────
print()
print("  🎮 Phase 2: GPU + PyTorch")
print("  " + "-" * 50)

all_ok &= check("PyTorch", lambda: f"v{__import__('torch').__version__}")

all_ok &= check("CUDA available", lambda: (
    f"✅ CUDA {__import__('torch').version.cuda}"
    if __import__('torch').cuda.is_available()
    else (_ for _ in ()).throw(RuntimeError("CUDA not available — 检查显卡驱动"))
))

all_ok &= check("GPU device", lambda: __import__('torch').cuda.get_device_name(0))

all_ok &= check("VRAM", lambda: (
    f"{__import__('torch').cuda.get_device_properties(0).total_mem / 1024**3:.1f} GB total"
    if hasattr(__import__('torch').cuda.get_device_properties(0), 'total_mem')
    else f"{__import__('torch').cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB total"
))

# ── Phase 3: 截图 + 控制 ─────────────────────────────
print()
print("  🖥️  Phase 3: 截图 + 鼠标键盘")
print("  " + "-" * 50)

all_ok &= check("mss (截图)", lambda: (
    __import__('mss'),
    f"v{__import__('mss').__version__}, {len(__import__('mss').mss().monitors) - 1} monitor(s)"
)[1])

all_ok &= check("PyAutoGUI (控制)", lambda: (
    f"v{__import__('pyautogui').__version__}, screen={__import__('pyautogui').size()}"
))

all_ok &= check("Pillow (图像处理)", lambda: f"v{__import__('PIL').__version__}")

# ── Phase 4: CLI 框架 ────────────────────────────────
print()
print("  ⌨️  Phase 4: CLI")
print("  " + "-" * 50)

all_ok &= check("click", lambda: f"v{__import__('importlib').metadata.version('click')}")

all_ok &= check("rich", lambda: f"v{__import__('importlib').metadata.version('rich')}")

all_ok &= check("xclaw CLI 入口", lambda: (
    __import__('xclaw.cli', fromlist=['main']),
    "xclaw.cli:main found ✅"
)[1])

# ── Phase 5: OmniParser ─────────────────────────────
print()
print("  🧠 Phase 5: OmniParser 模型权重")
print("  " + "-" * 50)

has_yolo = os.path.exists("weights/icon_detect/model.pt")
has_florence = os.path.exists("weights/icon_caption_florence/model.safetensors")

if has_yolo:
    print("  ✅ icon_detect: found")
else:
    print("  ⏳ icon_detect: not yet downloaded")

if has_florence:
    print("  ✅ icon_caption_florence: found")
else:
    print("  ⏳ icon_caption_florence: not yet downloaded")

has_omniparser_code = os.path.exists("OmniParser")
if has_omniparser_code:
    print("  ✅ OmniParser code: found")
else:
    print("  ⏳ OmniParser code: not yet cloned")

# ── Phase 6: HuggingFace CLI ────────────────────────
print()
print("  📥 Phase 6: HuggingFace CLI")
print("  " + "-" * 50)

all_ok &= check("huggingface-hub", lambda: f"v{__import__('importlib').metadata.version('huggingface-hub')}")

# ── 结果 ─────────────────────────────────────────────
print()
print("=" * 55)
models_ready = has_yolo and has_florence and has_omniparser_code

if all_ok and models_ready:
    print("  🎉 ALL GOOD — Ready to build xclaw!")
elif all_ok and not models_ready:
    print("  🎉 基础环境 ALL GOOD!")
    print("  📋 下一步: 下载 OmniParser 模型权重 (Step 4)")
else:
    print("  ⚠️  有检查项未通过，先修复上面标 ❌ 的项目")
print("=" * 55)
print()