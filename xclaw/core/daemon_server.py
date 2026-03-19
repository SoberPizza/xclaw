r"""Cross-platform perception daemon server.

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


class DaemonServer:
    def __init__(self):
        self.last_activity = time.time()
        self.registry = BackendRegistry()
        self.engine = None

    @staticmethod
    def _init_platform():
        """Platform init that cli.py normally does — needed because daemon is a standalone process."""
        import logging
        import warnings

        # ── Silence noisy loggers ──
        logging.getLogger().setLevel(logging.CRITICAL)
        warnings.filterwarnings("ignore")

        os.environ["NO_COLOR"] = "1"
        os.environ["TRANSFORMERS_VERBOSITY"] = "error"
        os.environ["YOLO_VERBOSE"] = "False"
        os.environ["GLOG_minloglevel"] = "2"
        os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "1"
        os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"
        os.environ["ORT_LOG_LEVEL"] = "3"
        os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
        os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"

        # Pre-configure paddlex loggers before import
        for name in ("paddlex", "paddlex.inference", "paddlex.utils"):
            lg = logging.getLogger(name)
            lg.addHandler(logging.NullHandler())
            lg.setLevel(logging.CRITICAL)
            lg.propagate = False

        # ── Windows CUDA DLL registration ──
        if sys.platform == "win32":
            import site
            for sp in site.getsitepackages():
                nvidia_dir = os.path.join(sp, "nvidia")
                if not os.path.isdir(nvidia_dir):
                    continue
                for sub in os.listdir(nvidia_dir):
                    bin_dir = os.path.join(nvidia_dir, sub, "bin")
                    if os.path.isdir(bin_dir):
                        os.add_dll_directory(bin_dir)
            try:
                import torch  # noqa: F401
            except Exception:
                pass

    def _ensure_engine(self):
        if self.engine is not None:
            return

        project_root = os.environ.get("XCLAW_HOME") or str(Path(__file__).parents[2])
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        from xclaw.platform import PERCEPTION_CONFIG
        from xclaw.core.perception.pipeline_backend import PipelineBackend
        from xclaw.core.perception.engine import PerceptionEngine

        backend = PipelineBackend(PERCEPTION_CONFIG)
        self.registry.register("pipeline", backend)
        self.registry.switch("pipeline")

        self.engine = PerceptionEngine(backend=backend)
        PerceptionEngine._instance = self.engine  # register as global singleton
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
            with self.registry.with_active() as (backend, entry):
                try:
                    # Use the engine (its _backend is set during _ensure_engine)
                    result = self.engine.full_look(
                        region=request.get("region"),
                        with_image=request.get("with_image", False),
                    )
                    elapsed_ms = (time.monotonic() - t0) * 1000
                    entry.record_call(elapsed_ms)
                    return result
                except Exception as e:
                    entry.record_error()
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
                # switch() acquires write lock, waits for in-flight perceive() calls
                result = self.registry.switch(name)
                # Engine backend reference is updated after write lock releases,
                # but the next with_active() call will pick up the new backend.
                if self.engine is not None:
                    self.engine._backend = self.registry.active
                return result
            except KeyError as e:
                return {"status": "error", "message": str(e)}
        elif cmd == "schedule":
            self._ensure_engine()
            from xclaw.core.context.scheduler import schedule
            sr = schedule(
                action_result=request.get("action_result"),
                force_level=request.get("force_level"),
            )
            return {
                "perception": sr.perception,
                "level": sr.level,
                "diff_ratio": sr.diff_ratio,
                "escalation_path": sr.escalation_path,
                "elapsed_ms": sr.elapsed_ms,
            }
        elif cmd == "backend-status":
            return self.registry.backend_status(request.get("name"))
        else:
            return {"status": "error", "message": f"Unknown command: {cmd}"}

    def run(self):
        self._init_platform()

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
                win32file.FlushFileBuffers(pipe)
                win32pipe.DisconnectNamedPipe(pipe)
            except Exception as e:
                try:
                    win32file.WriteFile(
                        pipe,
                        json.dumps({"status": "error", "message": str(e)}).encode("utf-8"),
                    )
                except Exception:
                    pass
                try:
                    win32pipe.DisconnectNamedPipe(pipe)
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

    def _cleanup_and_exit(self):
        """Clean up PID/socket files, then exit."""
        PID_FILE.unlink(missing_ok=True)
        if _system == "Darwin":
            try:
                os.unlink("/tmp/xclaw.sock")
            except Exception:
                pass
        os._exit(0)

    def _unload_caption(self):
        """Unload MiniCPM-V from active backend (write-lock protected)."""
        self.registry._rw.acquire_write()
        try:
            for entry in self.registry._backends.values():
                if hasattr(entry.backend, "unload_caption"):
                    entry.backend.unload_caption()
        finally:
            self.registry._rw.release_write()

    def _unload_all_models(self):
        """Unload all models from active backend (write-lock protected)."""
        self.registry._rw.acquire_write()
        try:
            for entry in self.registry._backends.values():
                if hasattr(entry.backend, "unload_all"):
                    entry.backend.unload_all()
                    entry.loaded = False
        finally:
            self.registry._rw.release_write()

    def _watchdog(self):
        from xclaw.config import (
            DAEMON_IDLE_UNLOAD_CAPTION_S,
            DAEMON_IDLE_UNLOAD_ALL_S,
            DAEMON_IDLE_EXIT_S,
        )

        caption_unloaded = False
        all_unloaded = False
        while True:
            time.sleep(30)
            idle = time.time() - self.last_activity

            if idle > DAEMON_IDLE_EXIT_S:
                print(
                    f"[daemon] Idle {DAEMON_IDLE_EXIT_S}s, shutting down.",
                    flush=True,
                )
                self._cleanup_and_exit()

            elif idle > DAEMON_IDLE_UNLOAD_ALL_S and not all_unloaded:
                print("[daemon] Idle 15min, unloading all models.", flush=True)
                self._unload_all_models()
                all_unloaded = True

            elif idle > DAEMON_IDLE_UNLOAD_CAPTION_S and not caption_unloaded:
                print("[daemon] Idle 5min, unloading MiniCPM-V.", flush=True)
                self._unload_caption()
                caption_unloaded = True

            # Reset flags on activity
            if idle < DAEMON_IDLE_UNLOAD_CAPTION_S:
                caption_unloaded = False
                all_unloaded = False


if __name__ == "__main__":
    DaemonServer().run()
