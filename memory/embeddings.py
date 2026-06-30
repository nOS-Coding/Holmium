import logging
import os
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

_MODEL_PATH = "/usr/lib/holmium/embeddings/model.onnx"
_DIM = 384


class ONNXEmbedding:
    """all-MiniLM-L6-v2 ONNX embedding model running on CPU.

    Loads the model from ``_MODEL_PATH``.  Falls back to a deterministic
    numpy-based embedding when the model file is not found (useful for
    development or testing).
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        self._model_path = model_path or _MODEL_PATH
        self._session: Optional["onnxruntime.InferenceSession"] = None
        self._tokenizer: Optional["tokenizers.Tokenizer"] = None
        self._fallback_rng: Optional[np.random.Generator] = None
        self._load()

    def _load(self) -> None:
        if not os.path.isfile(self._model_path):
            logger.warning(
                "ONNX model not found at %s — using fallback numpy embedding",
                self._model_path,
            )
            self._fallback_rng = np.random.default_rng(42)
            return

        try:
            import onnxruntime
            import tokenizers
        except ImportError as exc:
            raise ImportError(
                "onnxruntime-cpu and tokenizers are required for ONNX embedding. "
                "Install with: pip install onnxruntime-cpu tokenizers"
            ) from exc

        opts = onnxruntime.SessionOptions()
        opts.intra_op_num_threads = os.cpu_count() or 4
        opts.inter_op_num_threads = 1
        opts.log_severity_level = 3

        self._session = onnxruntime.InferenceSession(
            self._model_path, opts, providers=["CPUExecutionProvider"]
        )
        self._tokenizer = tokenizers.Tokenizer.from_file(
            os.path.join(os.path.dirname(self._model_path), "tokenizer.json")
        )

        logger.info(
            "ONNX embedding model loaded from %s (input names: %s)",
            self._model_path,
            [i.name for i in self._session.get_inputs()],
        )

    def _mean_pooling(self, token_embeds: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
        mask = attention_mask.astype(np.float32)[:, :, np.newaxis]
        masked = token_embeds * mask
        return masked.sum(axis=1) / mask.sum(axis=1).clip(min=1e-9)

    def embed(self, text: str) -> List[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        if self._fallback_rng is not None:
            return [
                self._fallback_rng.normal(0, 0.02, _DIM).tolist() for _ in texts
            ]

        assert self._session is not None and self._tokenizer is not None

        encoded = self._tokenizer.encode_batch(
            [self._preprocess(t) for t in texts]
        )
        input_ids = np.array(
            [e.ids[: self._max_seq_len()] for e in encoded], dtype=np.int64
        )
        attention_mask = np.array(
            [e.attention_mask[: self._max_seq_len()] for e in encoded],
            dtype=np.int64,
        )
        # Pad to uniform length
        max_len = max(input_ids.shape[1], 1)
        if input_ids.shape[1] < max_len:
            pad_w = max_len - input_ids.shape[1]
            input_ids = np.pad(input_ids, ((0, 0), (0, pad_w)), constant_values=0)
            attention_mask = np.pad(attention_mask, ((0, 0), (0, pad_w)), constant_values=0)

        outputs = self._session.run(
            None,
            {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": np.zeros_like(input_ids),
            },
        )
        token_embeds = outputs[0]
        pooled = self._mean_pooling(token_embeds, attention_mask)
        # L2-normalise
        norms = np.linalg.norm(pooled, axis=1, keepdims=True).clip(min=1e-12)
        normalized = pooled / norms
        return normalized.tolist()

    def _preprocess(self, text: str) -> str:
        return text.strip().replace("\n", " ")[:512]

    def _max_seq_len(self) -> int:
        return 256

    @property
    def dimension(self) -> int:
        return _DIM
