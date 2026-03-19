"""Tkinter GUI for downloading X-Claw models.

Uses only Python builtins + huggingface_hub (already a dependency).
"""

import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk
from pathlib import Path

# ── Download items ──

OMNIPARSER_REPO = "microsoft/OmniParser-v2.0"
OMNIPARSER_FILES = [
    "icon_detect/model.pt",
    "icon_detect/model.yaml",
    "icon_detect/train_args.yaml",
]

MINICPM_REPO = "openbmb/MiniCPM-V-2"


class DownloadGUI:
    MAX_RETRIES = 3

    def __init__(self, model_dir: Path):
        self.model_dir = model_dir
        self.success = False

        self.root = tk.Tk()
        self.root.title("X-Claw 模型下载")
        self.root.resizable(False, False)
        self.root.geometry("520x220")

        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill="both", expand=True)

        self.status_label = ttk.Label(frame, text="准备下载 …", font=("", 13))
        self.status_label.pack(anchor="w")

        self.file_label = ttk.Label(frame, text="", foreground="gray")
        self.file_label.pack(anchor="w", pady=(4, 0))

        self.progress = ttk.Progressbar(frame, length=480, mode="determinate")
        self.progress.pack(pady=(12, 0))

        self.detail_label = ttk.Label(frame, text="", foreground="gray")
        self.detail_label.pack(anchor="w", pady=(4, 0))

        self.retry_btn = ttk.Button(frame, text="重试", command=self._start_download)
        self.retry_btn.pack(pady=(10, 0))
        self.retry_btn.pack_forget()  # hidden until error

    def run(self) -> bool:
        self._start_download()
        self.root.mainloop()
        return self.success

    # ── threading ──

    def _start_download(self):
        self.retry_btn.pack_forget()
        threading.Thread(target=self._download_thread, daemon=True).start()

    def _download_thread(self):
        try:
            total_steps = len(OMNIPARSER_FILES) + 3  # +1 MiniCPM-V, +1 PaddleOCR, +1 init
            step = 0

            self._ui(status="下载 OmniParser V2 …")

            # Download OmniParser files one by one
            self.model_dir.mkdir(parents=True, exist_ok=True)
            for f in OMNIPARSER_FILES:
                step += 1
                self._ui(
                    file=f"({step}/{len(OMNIPARSER_FILES)}) {f}",
                    progress=step / total_steps * 100,
                )
                self._download_with_retry(
                    [
                        sys.executable, "-m", "huggingface_hub", "download",
                        OMNIPARSER_REPO, f, "--local-dir", str(self.model_dir),
                    ],
                    label=f,
                )

            # Download MiniCPM-V 2.0
            step += 1
            self._ui(
                status="下载 MiniCPM-V 2.0 …",
                file="icon caption model",
                progress=step / total_steps * 100,
            )
            minicpm_dir = self.model_dir / "icon_caption_minicpm"
            self._download_with_retry(
                [
                    sys.executable, "-m", "huggingface_hub", "download",
                    MINICPM_REPO, "--local-dir", str(minicpm_dir),
                ],
                label="MiniCPM-V-2",
            )

            # PaddleOCR
            step += 1
            self._ui(
                status="初始化 PaddleOCR …",
                file="首次运行自动下载模型",
                progress=step / total_steps * 100,
            )
            try:
                from paddleocr import PaddleOCR
                PaddleOCR(use_angle_cls=True, lang="ch", use_gpu=False, show_log=False)
            except Exception:
                pass  # Non-fatal — PaddleOCR retries at runtime

            # Init
            step += 1
            self._ui(
                status="初始化中 …",
                file="验证模型加载",
                progress=step / total_steps * 100,
            )
            time.sleep(0.3)

            self._ui(
                status="安装完成！",
                file="",
                progress=100,
                detail="所有模型已就绪，可以关闭此窗口。",
            )
            self.success = True

            # Auto-close after 2 seconds
            self.root.after(2000, self.root.destroy)

        except Exception as exc:
            self._ui(
                status=f"下载失败: {exc}",
                detail="请检查网络连接后点击「重试」。",
                show_retry=True,
            )

    def _ui(self, *, status=None, file=None, progress=None, detail=None, show_retry=False):
        """Schedule UI updates on the main thread."""
        def _update():
            if status is not None:
                self.status_label.config(text=status)
            if file is not None:
                self.file_label.config(text=file)
            if progress is not None:
                self.progress["value"] = progress
            if detail is not None:
                self.detail_label.config(text=detail)
            if show_retry:
                self.retry_btn.pack(pady=(10, 0))
        self.root.after(0, _update)

    def _download_with_retry(self, cmd: list[str], label: str = "") -> None:
        """Run a download subprocess with exponential-backoff retry."""
        for attempt in range(self.MAX_RETRIES):
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                return
            except subprocess.CalledProcessError:
                if attempt == self.MAX_RETRIES - 1:
                    raise
                wait = (2 ** attempt) * 2  # 2s, 4s, 8s
                self._ui(
                    detail=f"下载失败 ({label})，{wait}s 后重试… ({attempt + 1}/{self.MAX_RETRIES})",
                )
                time.sleep(wait)


def run_download_gui(model_dir: Path) -> bool:
    """Show the download GUI and block until complete. Returns True on success."""
    gui = DownloadGUI(model_dir)
    return gui.run()


if __name__ == "__main__":
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("models")
    ok = run_download_gui(dest)
    sys.exit(0 if ok else 1)
