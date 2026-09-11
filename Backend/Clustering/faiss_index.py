"""
FAISS Vector Index for Box Summary Embeddings.
Owners: Ansh Gaur & Ankit Shukla
Stores and searches across cluster box summary vectors.
"""
from pathlib import Path
from typing import List, Dict, Any, Tuple
import json
import numpy as np


class FAISSBoxIndex:
    """FAISS Index specifically built over box summary embeddings."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.index = None
        self.box_metadata: List[Dict[str, Any]] = []

    def build_index(
        self, box_embeddings: np.ndarray, box_metadata: List[Dict[str, Any]]
    ):
        """Build an exact Inner-Product (cosine similarity for normalized vectors) FAISS index."""
        try:
            import faiss

            # Normalize vectors to ensure inner product equals cosine similarity
            norm = np.linalg.norm(box_embeddings, axis=1, keepdims=True)
            norm_embeddings = box_embeddings / np.maximum(norm, 1e-12)

            self.index = faiss.IndexFlatIP(self.dimension)
            self.index.add(norm_embeddings.astype(np.float32))
            self.box_metadata = box_metadata
        except ImportError:
            raise ImportError("faiss-cpu is required. Install via: pip install faiss-cpu")

    def search_box(
        self, query_embedding: np.ndarray, top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """Search the closest semantic box for an input query vector."""
        if self.index is None:
            raise ValueError("FAISS index has not been built or loaded.")

        q = query_embedding.reshape(1, -1).astype(np.float32)
        norm = np.linalg.norm(q, axis=1, keepdims=True)
        q = q / np.maximum(norm, 1e-12)

        distances, indices = self.index.search(q, top_k)
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx != -1 and idx < len(self.box_metadata):
                meta = self.box_metadata[idx].copy()
                meta["similarity_score"] = float(dist)
                results.append(meta)
        return results

    def save(self, index_path: Path, metadata_path: Path):
        """Persist FAISS index and metadata to disk."""
        import faiss

        index_path = Path(index_path)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(index_path))

        metadata_path = Path(metadata_path)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(self.box_metadata, f, indent=2)

    def load(self, index_path: Path, metadata_path: Path):
        """Load FAISS index and metadata from disk."""
        import faiss

        self.index = faiss.read_index(str(index_path))
        with open(metadata_path, "r", encoding="utf-8") as f:
            self.box_metadata = json.load(f)
