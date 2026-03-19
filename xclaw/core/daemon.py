r"""Cross-platform perception daemon client.

macOS: Unix Domain Socket (/tmp/xclaw.sock)
Windows: Named Pipe (\\.\pipe\xclaw_perception)
"""

import json
import os
import sys
import time
import subprocess
import platform
from pathlib import Path

_system = platform.system()

# Communication address
if _system == "Windows":
    PIPE_ADDR = r"\\.\pipe\xclaw_perception"
elif _system == "Darwin":
    SOCK_PATH = "/tmp/xclaw.sock"

PID_FILE = Path.home() / ".xclaw" / "daemon.pid"
IDLE_TIMEOUT = 300  # 5 minutes auto-shutdown


def is_daemon_alive() -> bool:
    if not PID_FILE.exists():
        return False

    pid = int(PID_FILE.read_text().strip())

    if _system == "Darwin":
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            PID_FILE.unlink(missing_ok=True)
            return False
    elif _system == "Windows":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        PID_FILE.unlink(missing_ok=True)
        return False

    return False


def ensure_daemon():
    if is_daemon_alive():
        return

    daemon_script = str(Path(__file__).parent / "daemon_server.py")

    env = os.environ.copy()
    from xclaw.config import PROJECT_ROOT, DATA_DIR
    env.setdefault("XCLAW_HOME", str(PROJECT_ROOT))
    env.setdefault("XCLAW_DATA", str(DATA_DIR))

    if _system == "Darwin":
        subprocess.Popen(
            [sys.executable, daemon_script],
            env=env,
            stdout=open("/tmp/xclaw_daemon.log", "w"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    elif _system == "Windows":
        subprocess.Popen(
            [sys.executable, daemon_script],
            env=env,
            creationflags=0x00000008 | 0x00000010,  # DETACHED + CREATE_NO_WINDOW
            close_fds=True,
        )

    # Wait for ready
    for _ in range(300):
        if is_daemon_alive():
            time.sleep(0.5)  # Extra wait for socket/pipe ready
            return
        time.sleep(0.1)
    raise RuntimeError("Daemon failed to start within 30s")


def request_perception(command: dict) -> dict:
    ensure_daemon()

    if _system == "Darwin":
        return _request_unix_socket(command)
    elif _system == "Windows":
        return _request_named_pipe(command)
    else:
        raise OSError(f"Unsupported platform: {_system}")


def _request_unix_socket(command: dict) -> dict:
    import socket

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(SOCK_PATH)
    s.settimeout(120)  # Florence-2 CPU may take seconds

    payload = json.dumps(command).encode("utf-8")
    # Length-prefixed protocol: 4-byte big-endian length + data
    s.sendall(len(payload).to_bytes(4, "big") + payload)

    # Receive length prefix
    length_bytes = _recv_exact(s, 4)
    length = int.from_bytes(length_bytes, "big")

    # Receive data
    data = _recv_exact(s, length)
    s.close()

    return json.loads(data.decode("utf-8"))


def _recv_exact(sock, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Daemon closed connection unexpectedly")
        buf.extend(chunk)
    return bytes(buf)


def _request_named_pipe(command: dict) -> dict:
    import win32file

    handle = win32file.CreateFile(
        PIPE_ADDR,
        win32file.GENERIC_READ | win32file.GENERIC_WRITE,
        0, None, win32file.OPEN_EXISTING, 0, None,
    )
    try:
        data = json.dumps(command).encode("utf-8")
        win32file.WriteFile(handle, data)
        _, resp = win32file.ReadFile(handle, 4 * 1024 * 1024)
        return json.loads(resp.decode("utf-8"))
    finally:
        win32file.CloseHandle(handle)
