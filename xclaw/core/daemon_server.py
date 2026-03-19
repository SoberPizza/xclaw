"""Cross-platform perception daemon server.

macOS: Unix Domain Socket (/tmp/xclaw.sock)
Windows: Named Pipe (\\.\pipe\xclaw_perception)
"""

import json
import os
import sys
import time
import threading
import platform
from pathlib import Path

from xclaw.core.backend_registry import BackendRegistry

_system = platform.system()
PID_FILE = Path.home() / ".xclaw" / "daemon.pid"
IDLE_TIMEOUT = 300


class DaemonServer:
    def __init__(self):
        self.last_activity = time.time()
        self.registry = BackendRegistry()
        self.engine = None

    def _ensure_engine(self):
        if self.engine is not None:
            return

        project_root = os.environ.get("XCLAW_HOME") or str(Path(__file__).parents[2])
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        from xclaw.core.perception.pipeline_backend import PipelineBackend
        from xclaw.core.perception.engine import PerceptionEngine

        backend = PipelineBackend()
        self.registry.register("pipeline", backend)
        self.registry.switch("pipeline")

        self.engine = PerceptionEngine.get_instance()
        self.engine._ensure_models()
        print("[daemon] Models loaded. Ready.", flush=True)

    def handle(self, request: dict) -> dict:
        self.last_activity = time.time()
        cmd = request.get("command")

        if cmd == "ping":
            return {"status": "alive"}
        elif cmd == "shutdown":
            PID_FILE.unlink(missing_ok=True)
            os._exit(0)
        elif cmd == "look":
            self._ensure_engine()
            t0 = time.monotonic()
            try:
                result = self.engine.full_look(
                    region=request.get("region"),
                    with_image=request.get("with_image", False),
                )
                elapsed_ms = (time.monotonic() - t0) * 1000
                self.registry.active_entry.record_call(elapsed_ms)
                return result
            except Exception as e:
                self.registry.active_entry.record_error()
                raise
        elif cmd == "screenshot":
            self._ensure_engine()
            return self.engine.screenshot_only(region=request.get("region"))
        elif cmd == "list-backends":
            return self.registry.list_backends()
        elif cmd == "switch-backend":
            name = request.get("name")
            if not name:
                return {"status": "error", "message": "Missing 'name' parameter"}
            try:
                result = self.registry.switch(name)
                # Update engine backend reference
                if self.engine is not None:
                    self.engine._backend = self.registry.active
                return result
            except KeyError as e:
                return {"status": "error", "message": str(e)}
        elif cmd == "backend-status":
            return self.registry.backend_status(request.get("name"))
        else:
            return {"status": "error", "message": f"Unknown command: {cmd}"}

    def run(self):
        PID_FILE.parent.mkdir(exist_ok=True)
        PID_FILE.write_text(str(os.getpid()))

        # Idle watchdog
        threading.Thread(target=self._watchdog, daemon=True).start()

        if _system == "Darwin":
            self._serve_unix_socket()
        elif _system == "Windows":
            self._serve_named_pipe()

    def _serve_unix_socket(self):
        import socket

        sock_path = "/tmp/xclaw.sock"
        # Clean up old socket
        if os.path.exists(sock_path):
            os.unlink(sock_path)

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(sock_path)
        server.listen(1)
        os.chmod(sock_path, 0o600)  # Current user only
        print(f"[daemon] Listening on {sock_path}", flush=True)

        while True:
            conn, _ = server.accept()
            try:
                # Read length prefix + data
                length_bytes = self._recv_exact(conn, 4)
                length = int.from_bytes(length_bytes, "big")
                data = self._recv_exact(conn, length)

                request = json.loads(data.decode("utf-8"))
                response = self.handle(request)

                resp_bytes = json.dumps(response, ensure_ascii=False).encode("utf-8")
                conn.sendall(len(resp_bytes).to_bytes(4, "big") + resp_bytes)
            except Exception as e:
                try:
                    err = json.dumps({"status": "error", "message": str(e)}).encode()
                    conn.sendall(len(err).to_bytes(4, "big") + err)
                except Exception:
                    pass
            finally:
                conn.close()

    def _serve_named_pipe(self):
        import win32pipe
        import win32file

        pipe_name = r"\\.\pipe\xclaw_perception"
        print(f"[daemon] Listening on {pipe_name}", flush=True)

        while True:
            pipe = win32pipe.CreateNamedPipe(
                pipe_name,
                win32pipe.PIPE_ACCESS_DUPLEX,
                (
                    win32pipe.PIPE_TYPE_BYTE
                    | win32pipe.PIPE_READMODE_BYTE
                    | win32pipe.PIPE_WAIT
                ),
                1, 4 * 1024 * 1024, 4 * 1024 * 1024, 0, None,
            )
            try:
                win32pipe.ConnectNamedPipe(pipe, None)
                _, data = win32file.ReadFile(pipe, 4 * 1024 * 1024)
                request = json.loads(data.decode("utf-8"))
                response = self.handle(request)
                win32file.WriteFile(
                    pipe,
                    json.dumps(response, ensure_ascii=False).encode("utf-8"),
                )
            except Exception as e:
                try:
                    win32file.WriteFile(
                        pipe,
                        json.dumps({"status": "error", "message": str(e)}).encode("utf-8"),
                    )
                except Exception:
                    pass
            finally:
                win32file.CloseHandle(pipe)

    @staticmethod
    def _recv_exact(conn, n):
        buf = bytearray()
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("Client disconnected")
            buf.extend(chunk)
        return bytes(buf)

    def _watchdog(self):
        while True:
            time.sleep(30)
            if time.time() - self.last_activity > IDLE_TIMEOUT:
                print(
                    f"[daemon] Idle {IDLE_TIMEOUT}s, shutting down.", flush=True
                )
                PID_FILE.unlink(missing_ok=True)
                if _system == "Darwin":
                    try:
                        os.unlink("/tmp/xclaw.sock")
                    except Exception:
                        pass
                os._exit(0)


if __name__ == "__main__":
    DaemonServer().run()
