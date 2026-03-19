"""MiniCPM-V 2.0 icon caption — replaces Florence-2.

No transformers upper-bound constraint.

Windows: CUDA FP16  (~200ms/icon)
macOS:   CPU FP32   (~2-3s/icon)
"""

from pathlib import Path

import numpy as np
import torch


class MiniCPMCaption:
    """Generate short UI-element descriptions using MiniCPM-V 2.0."""

    def __init__(self, model_dir: Path, device: str = "cpu", dtype=torch.float32):
        from transformers import AutoModel, AutoTokenizer

        self.device = device
        self.dtype = dtype

        self.tokenizer = AutoTokenizer.from_pretrained(
            str(model_dir), trust_remote_code=True
        )
        self.model = AutoModel.from_pretrained(
            str(model_dir),
            torch_dtype=dtype,
            trust_remote_code=True,
        ).to(device).eval()

    @torch.inference_mode()
    def batch_caption(
        self, screenshot: np.ndarray, icon_elements: list[dict]
    ) -> list[str]:
        """Generate semantic descriptions for icon regions.

        Args:
            screenshot: Full screenshot as numpy array (RGB).
            icon_elements: Elements needing caption (must have ``bbox`` key).

        Returns:
            List of text descriptions, one per element.
        """
        from PIL import Image

        captions = []
        pil_img = Image.fromarray(screenshot)

        for elem in icon_elements:
            x1, y1, x2, y2 = elem["bbox"]
            crop = pil_img.crop((
                max(0, x1 - 5), max(0, y1 - 5),
                min(pil_img.width, x2 + 5), min(pil_img.height, y2 + 5),
            ))

            msgs = [{"role": "user", "content": "Describe this UI element in a few words."}]
            answer = self.model.chat(
                image=crop,
                msgs=msgs,
                tokenizer=self.tokenizer,
                sampling=False,
                max_new_tokens=30,
            )
            captions.append(answer.strip())

        return captions
