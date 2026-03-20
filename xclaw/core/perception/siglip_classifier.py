"""SigLIP 2 B/16 zero-shot icon classifier — replaces MiniCPM-V caption.

Text features are pre-computed at startup; inference is a single batched
forward pass of image encoding + cosine similarity.

All platforms: MPS / CUDA / CPU supported without monkey-patches.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from xclaw.core.perception.icon_labels import ICON_LABELS


class SigLIPClassifier:
    """Zero-shot icon classifier using SigLIP 2 B/16."""

    def __init__(self, model_dir: Path, device: str, dtype: torch.dtype):
        from transformers import AutoModel, AutoTokenizer, SiglipImageProcessor
        import transformers
        transformers.logging.set_verbosity_error()

        self.device = device
        self.dtype = dtype

        # SigLIP 2 uses GemmaTokenizer — AutoProcessor's SiglipProcessor rejects it,
        # so we build image_processor + tokenizer separately.
        self._image_processor = SiglipImageProcessor.from_pretrained(str(model_dir))
        self._tokenizer = AutoTokenizer.from_pretrained(str(model_dir))

        self.model = AutoModel.from_pretrained(
            str(model_dir),
            torch_dtype=dtype,
        ).to(device).eval()

        # Pre-compute text embeddings for all labels
        text_inputs = self._tokenizer(
            ICON_LABELS, padding=True, return_tensors="pt"
        ).to(device)
        with torch.inference_mode():
            text_embeds = self.model.get_text_features(**text_inputs)
            self._text_embeds = F.normalize(text_embeds, dim=-1)  # (N, D)

    @torch.inference_mode()
    def batch_classify(
        self, screenshot: np.ndarray, icon_elements: list[dict]
    ) -> list[dict]:
        """Classify icon regions via cosine similarity with pre-computed text features.

        Args:
            screenshot: Full screenshot as numpy array (RGB).
            icon_elements: Elements needing classification (must have ``bbox`` key).

        Returns:
            List of ``{"label": str, "confidence": float}`` dicts, one per element.
        """
        if not icon_elements:
            return []

        from PIL import Image

        pil_img = Image.fromarray(screenshot)
        crops = []
        for elem in icon_elements:
            x1, y1, x2, y2 = elem["bbox"]
            crop = pil_img.crop((
                max(0, x1 - 5), max(0, y1 - 5),
                min(pil_img.width, x2 + 5), min(pil_img.height, y2 + 5),
            ))
            crops.append(crop)

        image_inputs = self._image_processor(
            images=crops, return_tensors="pt"
        ).to(self.device)
        image_embeds = self.model.get_image_features(**image_inputs)
        image_embeds = F.normalize(image_embeds, dim=-1)  # (B, D)

        logits = image_embeds @ self._text_embeds.T  # (B, N)

        results = []
        for i in range(logits.shape[0]):
            topk = logits[i].topk(2)
            idx = topk.indices[0].item()
            conf = topk.values[0].item()
            gap = (topk.values[0] - topk.values[1]).item()
            results.append({"label": ICON_LABELS[idx], "confidence": conf, "gap": gap})

        return results
