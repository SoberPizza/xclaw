"""Windows keyboard control via ctypes SendInput.

Three input paths:
  A) VK physical key simulation for ASCII characters (with IME detection)
  B) Clipboard paste for non-ASCII characters (Chinese, emoji, kaomoji)
  C) KEYEVENTF_UNICODE as internal fallback (supports surrogate pairs)
"""

import ctypes
import ctypes.wintypes
import time
import random
import logging

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
imm32 = ctypes.windll.imm32

# SendInput constants
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

# Clipboard constants
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

# IME conversion mode flag
IME_CMODE_ALPHANUMERIC = 0x0000

# Windows Virtual Key codes
WIN_VK = {
    "return": 0x0D, "enter": 0x0D, "tab": 0x09, "space": 0x20,
    "backspace": 0x08, "delete": 0x2E, "escape": 0x1B, "esc": 0x1B,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "ctrl": 0x11, "control": 0x11, "lctrl": 0xA2, "rctrl": 0xA3,
    "shift": 0x10, "lshift": 0xA0, "rshift": 0xA1,
    "alt": 0x12, "lalt": 0xA4, "ralt": 0xA5,
    "win": 0x5B, "lwin": 0x5B, "rwin": 0x5C,
    "capslock": 0x14, "numlock": 0x90, "scrolllock": 0x91,
    "insert": 0x2D, "printscreen": 0x2C,
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45,
    "f": 0x46, "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A,
    "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E, "o": 0x4F,
    "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54,
    "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59, "z": 0x5A,
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
}

# Modifier VK codes
WIN_MOD_VK = {
    "ctrl": 0x11, "control": 0x11,
    "shift": 0x10,
    "alt": 0x12,
    "win": 0x5B,
}

VK_SHIFT = 0x10
VK_CONTROL = 0x11


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT(ctypes.Structure):
    # Windows INPUT union 的大小取最大成员（MOUSEINPUT = 32 bytes），
    # 如果只放 KEYBDINPUT（24 bytes），sizeof(INPUT) 会少 8 bytes，
    # 导致 SendInput 因 cbSize 不匹配而静默失败。
    # 用 _pad 填充到 MOUSEINPUT 的大小以保证结构体正确。
    class _INPUT_UNION(ctypes.Union):
        _fields_ = [
            ("ki", KEYBDINPUT),
            ("_pad", ctypes.c_ubyte * 32),
        ]

    _anonymous_ = ("_input",)
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("_input", _INPUT_UNION),
    ]


# ── Low-level SendInput helpers ──


def _send_key(vk: int = 0, scan: int = 0, flags: int = 0):
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ki.wVk = vk
    inp.ki.wScan = scan
    inp.ki.dwFlags = flags
    inp.ki.time = 0
    inp.ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def _press_release_vk(vk: int):
    _send_key(vk=vk)
    time.sleep(random.uniform(0.02, 0.06))
    _send_key(vk=vk, flags=KEYEVENTF_KEYUP)


# ── Path C: KEYEVENTF_UNICODE (internal fallback, supports surrogate pairs) ──


def _type_unicode_char(char: str):
    """Send a Unicode character via KEYEVENTF_UNICODE.

    Handles BMP characters directly and supplementary plane characters
    (e.g. emoji) as UTF-16 surrogate pairs.
    """
    code = ord(char)
    if code <= 0xFFFF:
        # BMP character — single event pair
        _send_key(scan=code, flags=KEYEVENTF_UNICODE)
        time.sleep(random.uniform(0.02, 0.06))
        _send_key(scan=code, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)
    else:
        # Supplementary plane — UTF-16 surrogate pair
        high = 0xD800 + ((code - 0x10000) >> 10)
        low = 0xDC00 + ((code - 0x10000) & 0x3FF)
        _send_key(scan=high, flags=KEYEVENTF_UNICODE)
        _send_key(scan=low, flags=KEYEVENTF_UNICODE)
        time.sleep(random.uniform(0.02, 0.06))
        _send_key(scan=low, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)
        _send_key(scan=high, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)


# ── IME detection and control ──


def _get_foreground_ime_context():
    """Get IME context for the foreground window."""
    hwnd = user32.GetForegroundWindow()
    return hwnd, imm32.ImmGetContext(hwnd)


def _is_ime_chinese_mode() -> bool:
    """Check if the current IME is in Chinese (non-alphanumeric) input mode."""
    hwnd, himc = _get_foreground_ime_context()
    if not himc:
        return False
    conversion = ctypes.wintypes.DWORD()
    sentence = ctypes.wintypes.DWORD()
    result = imm32.ImmGetConversionStatus(
        himc, ctypes.byref(conversion), ctypes.byref(sentence)
    )
    imm32.ImmReleaseContext(hwnd, himc)
    if not result:
        return False
    # If not alphanumeric mode, it's in Chinese/Japanese/Korean input mode
    return (conversion.value & 0x01) != IME_CMODE_ALPHANUMERIC


def _toggle_ime_to_english():
    """Send Shift to toggle IME from Chinese to English mode."""
    _send_key(vk=VK_SHIFT)
    _send_key(vk=VK_SHIFT, flags=KEYEVENTF_KEYUP)
    time.sleep(random.uniform(0.05, 0.10))


# ── Path A: VK physical key simulation (ASCII) ──


def type_char_vk(char: str):
    """Type a single ASCII character using VK physical key simulation.

    Uses VkKeyScanW to map the character to VK + shift state for the
    current keyboard layout. Falls back to KEYEVENTF_UNICODE if the
    character has no VK mapping.
    """
    result = user32.VkKeyScanW(ord(char))
    if result == -1:
        # No VK mapping on current layout — fallback
        _type_unicode_char(char)
        return

    vk = result & 0xFF
    shift_state = (result >> 8) & 0xFF
    need_shift = bool(shift_state & 0x01)

    if need_shift:
        _send_key(vk=VK_SHIFT)
        time.sleep(random.uniform(0.01, 0.03))

    _send_key(vk=vk)
    time.sleep(random.uniform(0.02, 0.06))
    _send_key(vk=vk, flags=KEYEVENTF_KEYUP)

    if need_shift:
        time.sleep(random.uniform(0.01, 0.03))
        _send_key(vk=VK_SHIFT, flags=KEYEVENTF_KEYUP)


# ── Path B: Clipboard paste (non-ASCII) ──


def _get_clipboard_text() -> str | None:
    """Read current clipboard text (CF_UNICODETEXT). Returns None if empty."""
    if not user32.OpenClipboard(0):
        return None
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return None
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _set_clipboard_text(text: str) -> bool:
    """Write text to clipboard as CF_UNICODETEXT."""
    if not user32.OpenClipboard(0):
        return False
    try:
        user32.EmptyClipboard()
        data = text.encode("utf-16-le") + b"\x00\x00"
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            return False
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            kernel32.GlobalFree(handle)
            return False
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(handle)
        user32.SetClipboardData(CF_UNICODETEXT, handle)
        return True
    finally:
        user32.CloseClipboard()


def clipboard_paste(text: str):
    """Paste text via clipboard (Ctrl+V), preserving original clipboard content."""
    # Save original clipboard
    original = _get_clipboard_text()

    # Write our text
    if not _set_clipboard_text(text):
        logger.warning("Failed to set clipboard, falling back to KEYEVENTF_UNICODE")
        for ch in text:
            _type_unicode_char(ch)
        return

    # Ctrl+V
    _send_key(vk=VK_CONTROL)
    time.sleep(random.uniform(0.02, 0.04))
    _press_release_vk(WIN_VK["v"])
    time.sleep(random.uniform(0.02, 0.04))
    _send_key(vk=VK_CONTROL, flags=KEYEVENTF_KEYUP)

    # Wait for paste to be processed by target application
    time.sleep(random.uniform(0.05, 0.12))

    # Restore original clipboard
    if original is not None:
        _set_clipboard_text(original)
    else:
        # Clear clipboard to original empty state
        if user32.OpenClipboard(0):
            user32.EmptyClipboard()
            user32.CloseClipboard()


# ── Public API ──


def type_text(text: str):
    r"""Type text using segmented input strategy.

    - ``\n`` → Enter VK
    - ``\t`` → Tab VK
    - ASCII printable → Path A (VK physical key, with IME toggle if needed)
    - Non-ASCII → Path B (clipboard paste)

    Note: When called via NativeActionBackend, IME management is handled
    at the backend level.  This standalone function includes its own IME
    toggle for direct usage.
    """
    ime_was_chinese = _is_ime_chinese_mode()
    ime_toggled = False

    segments = _split_text(text)
    has_ascii = any(k == "ascii" for k, _ in segments)

    if has_ascii and ime_was_chinese:
        _toggle_ime_to_english()
        ime_toggled = True

    for kind, segment in segments:
        if kind == "control":
            for char in segment:
                if char == "\n":
                    _press_release_vk(WIN_VK["return"])
                elif char == "\t":
                    _press_release_vk(WIN_VK["tab"])
        elif kind == "ascii":
            for char in segment:
                type_char_vk(char)
        elif kind == "non_ascii":
            clipboard_paste(segment)

    if ime_toggled:
        _toggle_ime_to_english()  # Shift toggles back


def _split_text(text: str) -> list[tuple[str, str]]:
    """Split text into contiguous segments of (kind, content).

    Kinds: 'control' (\\n, \\t), 'ascii' (printable ASCII), 'non_ascii' (everything else).
    """
    if not text:
        return []

    segments: list[tuple[str, str]] = []
    current_kind = _char_kind(text[0])
    current_chars = [text[0]]

    for char in text[1:]:
        kind = _char_kind(char)
        if kind == current_kind:
            current_chars.append(char)
        else:
            segments.append((current_kind, "".join(current_chars)))
            current_kind = kind
            current_chars = [char]

    segments.append((current_kind, "".join(current_chars)))
    return segments


def _char_kind(char: str) -> str:
    if char in ("\n", "\t"):
        return "control"
    if 0x20 <= ord(char) <= 0x7E:
        return "ascii"
    return "non_ascii"


def hotkey(combo: str):
    """Hotkey combo: 'ctrl+a', 'ctrl+shift+s', 'alt+f4'."""
    keys = [k.strip().lower() for k in combo.split("+")]

    mod_vks = []
    final_vk = None

    for key in keys:
        if key in WIN_MOD_VK:
            mod_vks.append(WIN_MOD_VK[key])
        elif key in WIN_VK:
            final_vk = WIN_VK[key]
        else:
            raise ValueError(f"Unknown key: '{key}'")

    if final_vk is None:
        raise ValueError("Hotkey must include a non-modifier key")

    # Press modifiers
    for vk in mod_vks:
        _send_key(vk=vk)
        time.sleep(random.uniform(0.02, 0.04))

    # Press+release final key
    _press_release_vk(final_vk)

    # Release modifiers (reverse order)
    for vk in reversed(mod_vks):
        _send_key(vk=vk, flags=KEYEVENTF_KEYUP)
        time.sleep(random.uniform(0.02, 0.04))
