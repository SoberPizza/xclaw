"""Windows keyboard control via ctypes SendInput."""

import ctypes
import time
import random

user32 = ctypes.windll.user32

# SendInput constants
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

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


def _type_unicode_char(char: str):
    """Send a Unicode character via KEYEVENTF_UNICODE — works for any character."""
    code = ord(char)
    _send_key(scan=code, flags=KEYEVENTF_UNICODE)
    time.sleep(random.uniform(0.02, 0.06))
    _send_key(scan=code, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)


def type_text(text: str):
    r"""Type text with human-like delays.

    Strategy:
    - \n → Enter VK
    - \t → Tab VK
    - Everything else → KEYEVENTF_UNICODE (bypasses IME, works for all characters)
    """
    for char in text:
        if char == '\n':
            _press_release_vk(WIN_VK["return"])
        elif char == '\t':
            _press_release_vk(WIN_VK["tab"])
        else:
            _type_unicode_char(char)



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
