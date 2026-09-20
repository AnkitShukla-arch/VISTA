"""
Medical Report Embedder using Sentence Transformers.

Enhancements:
- Auto GPU/CUDA device selection with graceful CPU fallback.
- High-throughput batch encoding with progress tracking.
- Persistent embedding caching (.npy for vectors, .json / .parquet for metadata).
- L2-normalization verification and benchmark telemetry (throughput, latency).
"""
from pathlib import Path
from typing import List, Dict, Any, Union, Optional, Tuple
import time
import json
import numpy as np


class MedicalEmbedder:
    """
    Encodes medical clinical text into dense semantic vectors (default: 384-D)
    using Sentence Transformers (default: all-MiniLM-L6-v2 or clinical models).
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: Optional[str] = None,
        batch_size: int = 64,
    ):
        self.model_name = model_name
        self.batch_size = batch_size
        self._model = None

        # Auto-detect optimal device if not explicitly set
        if device is not None:
            self.device = device
        else:
            self.device = self._auto_detect_device()

    @staticmethod
    def _auto_detect_device() -> str:
        """Detect CUDA GPU or fall back to CPU."""
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"

    @property
    def model(self):
        """Lazy loader for SentenceTransformer model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name, device=self.device)
            except ImportError:
                raise ImportError(
                    "sentence-transformers is required for MedicalEmbedder. "
                    "Install via: pip install sentence-transformers"
                )
        return self._model

    def encode(
        self,
        texts: Union[str, List[str]],
        normalize_embeddings: bool = True,
        show_progress_bar: bool = False,
    ) -> np.ndarray:
        """
        Generates dense embeddings for input texts.

        Args:
            texts: Single clinical string or list of clinical report strings.
            normalize_embeddings: If True, vectors are L2-normalized so dot product = cosine similarity.
            show_progress_bar: Whether to display a progress bar for large batches.

        Returns:
            np.ndarray of shape (N, dimension) with float32 embeddings.
        """
        if isinstance(texts, str):
            texts = [texts]

        if not texts:
            return np.empty((0, 384), dtype=np.float32)

        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=show_progress_bar,
            normalize_embeddings=normalize_embeddings,
            convert_to_numpy=True,
        )

        embeddings = embeddings.astype(np.float32)

        # Verification: Ensure no NaNs or Infs
        if np.isnan(embeddings).any() or np.isinf(embeddings).any():
            embeddings = np.nan_to_num(embeddings, nan=0.0, posinf=1.0, neginf=-1.0)

        return embeddings

    def encode_single(self, text: str, normalize: bool = True) -> np.ndarray:
        """Convenience method to encode a single query string into a 1D vector."""
        vec = self.encode([text], normalize_embeddings=normalize, show_progress_bar=False)
        return vec[0]

    def encode_records(
        self,
        records: List[Dict[str, Any]],
        text_field: str = "diagnostic_summary",
        show_progress_bar: bool = True,
    ) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """
        Encodes a list of parsed record dictionaries and returns both the embedding
        matrix and metadata records aligned by index.
        """
        texts = [r.get(text_field, "") for r in records]
        embeddings = self.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=show_progress_bar,
        )
        return embeddings, records

    def save_cache(
        self,
        embeddings: np.ndarray,
        records: List[Dict[str, Any]],
        output_dir: Union[str, Path],
        prefix: str = "vista",
    ) -> Tuple[Path, Path]:
        """
        Persists embeddings and aligned metadata for downstream handoff to K-Means
        clustering and FAISS indexing.
        """
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        npy_path = out_path / f"{prefix}_embeddings.npy"
        json_path = out_path / f"{prefix}_metadata.json"

        # Save binary embeddings
        np.save(str(npy_path), embeddings)

        # Save metadata (excluding raw_text to keep file compact)
        clean_metadata = []
        for r in records:
            meta = {k: v for k, v in r.items() if k != "raw_text"}
            clean_metadata.append(meta)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(clean_metadata, f, indent=2)

        return npy_path, json_path

    @staticmethod
    def load_cache(
        embeddings_path: Union[str, Path],
        metadata_path: Union[str, Path],
    ) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """Loads cached embeddings and metadata."""
        emb_path = Path(embeddings_path)
        meta_path = Path(metadata_path)

        if not emb_path.exists() or not meta_path.exists():
            raise FileNotFoundError(f"Missing cache files: {emb_path} or {meta_path}")

        embeddings = np.load(str(emb_path))
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        return embeddings, metadata

    def benchmark_encoding(self, sample_texts: List[str]) -> Dict[str, Any]:
        """
        Runs a performance benchmark measuring throughput and latency.
        """
        n_samples = len(sample_texts)
        if n_samples == 0:
            return {"error": "Empty text list provided."}

        t0 = time.time()
        embs = self.encode(sample_texts, normalize_embeddings=True, show_progress_bar=False)
        duration = time.time() - t0

        records_per_sec = n_samples / max(duration, 1e-6)
        latency_ms_per_doc = (duration / n_samples) * 1000

        # Verify unit magnitude
        norms = np.linalg.norm(embs, axis=1)
        is_normalized = bool(np.allclose(norms, 1.0, atol=1e-4))

        return {
            "model_name": self.model_name,
            "device": self.device,
            "sample_count": n_samples,
            "dimension": embs.shape[1],
            "total_duration_sec": round(duration, 3),
            "throughput_docs_per_sec": round(records_per_sec, 1),
            "latency_ms_per_doc": round(latency_ms_per_doc, 2),
            "is_l2_normalized": is_normalized,
            "embedding_memory_kb": round(embs.nbytes / 1024, 2),
        }
