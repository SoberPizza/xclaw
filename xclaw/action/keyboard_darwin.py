"""macOS keyboard control via Quartz CGEvent."""

import time
import random

import Quartz

# ── macOS virtual keycodes ──
MAC_KC = {
    "a": 0x00, "b": 0x0B, "c": 0x08, "d": 0x02, "e": 0x0E,
    "f": 0x03, "g": 0x05, "h": 0x04, "i": 0x22, "j": 0x26,
    "k": 0x28, "l": 0x25, "m": 0x2E, "n": 0x2D, "o": 0x1F,
    "p": 0x23, "q": 0x0C, "r": 0x0F, "s": 0x01, "t": 0x11,
    "u": 0x20, "v": 0x09, "w": 0x0D, "x": 0x07, "y": 0x10, "z": 0x06,
    "0": 0x1D, "1": 0x12, "2": 0x13, "3": 0x14, "4": 0x15,
    "5": 0x17, "6": 0x16, "7": 0x1A, "8": 0x1C, "9": 0x19,
    "return": 0x24, "enter": 0x24, "tab": 0x30, "space": 0x31,
    "backspace": 0x33, "delete": 0x75, "forwarddelete": 0x75,
    "escape": 0x35, "esc": 0x35,
    "up": 0x7E, "down": 0x7D, "left": 0x7B, "right": 0x7C,
    "home": 0x73, "end": 0x77, "pageup": 0x74, "pagedown": 0x79,
    "f1": 0x7A, "f2": 0x78, "f3": 0x63, "f4": 0x76,
    "f5": 0x60, "f6": 0x61, "f7": 0x62, "f8": 0x64,
    "f9": 0x65, "f10": 0x6D, "f11": 0x67, "f12": 0x6F,
    "-": 0x1B, "=": 0x18, "[": 0x21, "]": 0x1E,
    ";": 0x29, "'": 0x27, ",": 0x2B, ".": 0x2F, "/": 0x2C,
    "\\": 0x2A, "`": 0x32,
}

# ── Modifier keys ──
MAC_MOD_KC = {
    "cmd": 0x37, "command": 0x37,
    "shift": 0x38, "lshift": 0x38, "rshift": 0x3C,
    "alt": 0x3A, "option": 0x3A, "lalt": 0x3A, "ralt": 0x3D,
    "ctrl": 0x3B, "control": 0x3B, "lctrl": 0x3B, "rctrl": 0x3E,
    "fn": 0x3F,
}

MAC_MOD_FLAGS = {
    "cmd": Quartz.kCGEventFlagMaskCommand,
    "command": Quartz.kCGEventFlagMaskCommand,
    "shift": Quartz.kCGEventFlagMaskShift,
    "lshift": Quartz.kCGEventFlagMaskShift,
    "rshift": Quartz.kCGEventFlagMaskShift,
    "alt": Quartz.kCGEventFlagMaskAlternate,
    "option": Quartz.kCGEventFlagMaskAlternate,
    "lalt": Quartz.kCGEventFlagMaskAlternate,
    "ralt": Quartz.kCGEventFlagMaskAlternate,
    "ctrl": Quartz.kCGEventFlagMaskControl,
    "control": Quartz.kCGEventFlagMaskControl,
    "lctrl": Quartz.kCGEventFlagMaskControl,
    "rctrl": Quartz.kCGEventFlagMaskControl,
    "fn": Quartz.kCGEventFlagMaskSecondaryFn,
}

# Shift symbol mapping
SHIFT_CHARS = {
    '!': '1', '@': '2', '#': '3', '$': '4', '%': '5',
    '^': '6', '&': '7', '*': '8', '(': '9', ')': '0',
    '_': '-', '+': '=', '{': '[', '}': ']', '|': '\\',
    ':': ';', '"': "'", '<': ',', '>': '.', '?': '/',
    '~': '`',
}


def _key_event(keycode: int, down: bool, flags: int = 0):
    ev = Quartz.CGEventCreateKeyboardEvent(None, keycode, down)
    if flags:
        Quartz.CGEventSetFlags(ev, flags)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


def _press_release(keycode: int, flags: int = 0):
    _key_event(keycode, True, flags)
    time.sleep(random.uniform(0.02, 0.06))
    _key_event(keycode, False, flags)


def _type_unicode_char(char: str):
    """CGEventKeyboardSetUnicodeString — inject any Unicode directly.

    This is the key API on macOS to bypass IME and input any Unicode character.
    """
    ev_down = Quartz.CGEventCreateKeyboardEvent(None, 0, True)
    ev_up = Quartz.CGEventCreateKeyboardEvent(None, 0, False)

    Quartz.CGEventKeyboardSetUnicodeString(ev_down, len(char), char)
    Quartz.CGEventKeyboardSetUnicodeString(ev_up, len(char), char)

    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev_down)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev_up)


def type_text(text: str):
    r"""Human-level typing — supports Chinese/English/emoji.

    Strategy:
    - \n → Return keycode
    - \t → Tab keycode
    - ASCII mappable chars → keycode (with shift for uppercase)
    - Other (Chinese/Japanese/emoji) → CGEventKeyboardSetUnicodeString
    """
    for char in text:
        if char == '\n':
            _press_release(MAC_KC["return"])
        elif char == '\t':
            _press_release(MAC_KC["tab"])
        elif char == ' ':
            _press_release(MAC_KC["space"])
        elif char in SHIFT_CHARS:
            base = SHIFT_CHARS[char]
            if base in MAC_KC:
                _press_release(MAC_KC[base], Quartz.kCGEventFlagMaskShift)
            else:
                _type_unicode_char(char)
        elif char.lower() in MAC_KC and ord(char) < 128:
            flags = Quartz.kCGEventFlagMaskShift if char.isupper() else 0
            _press_release(MAC_KC[char.lower()], flags)
        else:
            # Chinese, Japanese, Korean, emoji → Unicode direct injection
            _type_unicode_char(char)



def hotkey(combo: str):
    """Hotkey combo: 'cmd+a', 'cmd+shift+s', 'cmd+option+esc'.

    Note for LLM callers:
    - macOS copy = cmd+c (not ctrl+c)
    - macOS paste = cmd+v
    - macOS select all = cmd+a
    - macOS close = cmd+w
    - macOS quit = cmd+q
    """
    keys = [k.strip().lower() for k in combo.split("+")]

    mod_keycodes = []
    mod_flags = 0
    final_keycode = None

    for key in keys:
        if key in MAC_MOD_KC:
            mod_keycodes.append(MAC_MOD_KC[key])
            mod_flags |= MAC_MOD_FLAGS[key]
        elif key in MAC_KC:
            final_keycode = MAC_KC[key]
        else:
            raise ValueError(
                f"Unknown key: '{key}'. "
                f"Modifiers: {sorted(MAC_MOD_KC.keys())}. "
                f"Keys: {sorted(MAC_KC.keys())}."
            )

    if final_keycode is None:
        raise ValueError("Hotkey must include a non-modifier key")

    # Press modifiers
    for kc in mod_keycodes:
        _key_event(kc, True)
        time.sleep(random.uniform(0.02, 0.04))

    # Press+release final key
    _press_release(final_keycode, mod_flags)

    # Release modifiers (reverse order)
    for kc in reversed(mod_keycodes):
        _key_event(kc, False)
        time.sleep(random.uniform(0.02, 0.04))
