"""Florence-2 icon captioner (fine-tuned from OmniParser V2)."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# Florence-2 inference constants
_CROP_SIZE = 64
_BATCH_SIZE = 128
_MAX_NEW_TOKENS = 20
_PROMPT = "<CAPTION>"


class IconClassifier:
    """Florence-2 fine-tuned icon captioner.

    Loads the OmniParser V2 fine-tuned Florence-2-base model and generates
    short text captions for icon crops.  Despite the class name, this produces
    free-text captions rather than fixed class labels.

    The class name is kept as ``IconClassifier`` for backward compatibility
    with :class:`PipelineBackend` and the :class:`PerceptionBackend` protocol.
    """

    def __init__(self, model_path: Path, device: str = "cuda"):
        self._model = None
        self._processor = None
        self._model_path = model_path  # directory containing Florence-2 weights
        self._device = device
        self._loaded = False

    def load(self) -> None:
        """Lazy-load the Florence-2 model and processor from a local directory."""
        if self._loaded:
            return
        if not self._model_path.exists():
            logger.info(
                "Florence-2 model not found at %s, captioning disabled",
                self._model_path,
            )
            return

        import torch
        from transformers import AutoModelForCausalLM, AutoProcessor

        dtype = torch.float16 if self._device == "cuda" else torch.float32

        try:
            self._processor = AutoProcessor.from_pretrained(
                str(self._model_path), trust_remote_code=True,
            )
            self._model = AutoModelForCausalLM.from_pretrained(
                str(self._model_path),
                dtype=dtype,
                trust_remote_code=True,
                attn_implementation="eager",
            ).to(self._device)
            self._model.eval()
            self._loaded = True
            logger.debug(
                "Florence-2 loaded from %s on %s (%s)",
                self._model_path, self._device, dtype,
            )
        except Exception:
            logger.warning(
                "Failed to load Florence-2 from %s", self._model_path,
                exc_info=True,
            )
            self._model = None
            self._processor = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def classify(self, image: np.ndarray, icon_elements: list[dict]) -> list[str]:
        """Caption each icon bbox region, returning a short text per element."""
        if self._model is None or self._processor is None:
            return ["unknown" for _ in icon_elements]
        if not icon_elements:
            return []

        import torch
        from PIL import Image

        pil_image = Image.fromarray(image)
        crops: list[Image.Image] = []

        for elem in icon_elements:
            x1, y1, x2, y2 = elem["bbox"]
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(pil_image.width, x2)
            y2 = min(pil_image.height, y2)
            crop = pil_image.crop((x1, y1, x2, y2)).resize(
                (_CROP_SIZE, _CROP_SIZE), Image.LANCZOS,
            )
            crops.append(crop)

        captions: list[str] = []
        device = self._model.device
        is_cuda = device.type == "cuda"

        for batch_start in range(0, len(crops), _BATCH_SIZE):
            batch = crops[batch_start : batch_start + _BATCH_SIZE]

            if is_cuda:
                inputs = self._processor(
                    text=[_PROMPT] * len(batch),
                    images=batch,
                    return_tensors="pt",
                    do_resize=False,
                ).to(device=device, dtype=torch.float16)
            else:
                inputs = self._processor(
                    text=[_PROMPT] * len(batch),
                    images=batch,
                    return_tensors="pt",
                ).to(device=device)

            with torch.inference_mode():
                generated_ids = self._model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=_MAX_NEW_TOKENS,
                    num_beams=1,
                    do_sample=False,
                    use_cache=False,
                )

            batch_captions = self._processor.batch_decode(
                generated_ids, skip_special_tokens=True,
            )
            captions.extend(c.strip() for c in batch_captions)

        return captions
