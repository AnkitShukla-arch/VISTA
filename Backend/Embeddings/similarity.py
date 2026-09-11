"""
Pairwise Cosine Similarity Matrix and Vector Math Utilities.
Owner: Arpit Umrao (Embeddings & Similarity Math Engineer)

Enhancements:
- Memory-safe Tiled / Block-wise Matrix Multiplication (prevents OOM on large datasets).
- Memory-mapped Matrix persistence (np.memmap) for arbitrarily large scale.
- Sparse Top-K Medical Similarity Graph builder (companion case lookup).
- Specialty Separability Evaluator (quantifies intra-specialty vs. inter-specialty separation).
"""
from pathlib import Path
from typing import Tuple, List, Dict, Any, Optional, Union
import numpy as np


class CosineSimilarityCalculator:
    """
    High-performance, scalable Cosine Similarity engine:
        cos(theta) = (A . B) / (||A||_2 * ||B||_2)
    """

    @staticmethod
    def l2_normalize(matrix: np.ndarray, axis: int = 1, eps: float = 1e-12) -> np.ndarray:
        """L2-normalizes rows or columns of a vector matrix."""
        norm = np.linalg.norm(matrix, axis=axis, keepdims=True)
        return matrix / np.maximum(norm, eps)

    @classmethod
    def compute_pairwise_matrix(
        cls, embeddings: np.ndarray, is_normalized: bool = False
    ) -> np.ndarray:
        """
        Computes the standard (N, N) pairwise cosine similarity matrix in memory.

        Args:
            embeddings: 2D array of shape (N, D)
            is_normalized: If True, skips L2 normalization step

        Returns:
            np.ndarray of shape (N, N) where entry [i, j] in [-1.0, 1.0]
        """
        if embeddings.ndim != 2:
            raise ValueError(f"Expected 2D matrix, got shape {embeddings.shape}")

        matrix = embeddings if is_normalized else cls.l2_normalize(embeddings, axis=1)
        sim_matrix = np.matmul(matrix, matrix.T)
        return np.clip(sim_matrix, -1.0, 1.0)

    @classmethod
    def compute_tiled_pairwise_matrix(
        cls,
        embeddings: np.ndarray,
        tile_size: int = 500,
        is_normalized: bool = False,
        output_memmap_path: Optional[Union[str, Path]] = None,
    ) -> np.ndarray:
        """
        Memory-safe block-wise pairwise cosine similarity.
        Processes documents in tiles of size (tile_size, D) against the full (N, D) corpus.
        Optionally streams directly into a memory-mapped file on disk.
        """
        N, D = embeddings.shape
        norm_matrix = embeddings if is_normalized else cls.l2_normalize(embeddings, axis=1)

        if output_memmap_path:
            out_file = Path(output_memmap_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            result = np.memmap(
                str(out_file), dtype="float32", mode="w+", shape=(N, N)
            )
        else:
            result = np.zeros((N, N), dtype=np.float32)

        for i in range(0, N, tile_size):
            end_i = min(i + tile_size, N)
            tile = norm_matrix[i:end_i]  # shape (tile_size, D)
            # Dot product against full transposed matrix: (tile_size, D) @ (D, N) -> (tile_size, N)
            block_sims = np.matmul(tile, norm_matrix.T)
            result[i:end_i, :] = np.clip(block_sims, -1.0, 1.0)

        if output_memmap_path and hasattr(result, "flush"):
            result.flush()

        return result

    @classmethod
    def query_similarity(
        cls, query_vector: np.ndarray, doc_vectors: np.ndarray, is_normalized: bool = False
    ) -> np.ndarray:
        """
        Computes 1D cosine similarity array between a single query and multiple docs.
        """
        q = query_vector.reshape(1, -1)
        if not is_normalized:
            q = cls.l2_normalize(q, axis=1)
            docs = cls.l2_normalize(doc_vectors, axis=1)
        else:
            docs = doc_vectors

        sims = np.matmul(docs, q.T).flatten()
        return np.clip(sims, -1.0, 1.0)

    @staticmethod
    def top_k(scores: np.ndarray, k: int = 5) -> Tuple[np.ndarray, np.ndarray]:
        """Returns the top-k indices and their similarity scores sorted descending."""
        k = min(k, len(scores))
        top_indices = np.argpartition(-scores, k)[:k]
        top_indices = top_indices[np.argsort(-scores[top_indices])]
        return top_indices, scores[top_indices]

    @classmethod
    def build_top_k_similarity_graph(
        cls,
        embeddings: np.ndarray,
        records: List[Dict[str, Any]],
        k: int = 5,
        tile_size: int = 500,
    ) -> List[Dict[str, Any]]:
        """
        Builds a sparse similarity graph: For every document, identifies its
        Top-K most semantically related companion cases.
        """
        N = len(records)
        norm_embs = cls.l2_normalize(embeddings, axis=1)
        graph = []

        for i in range(0, N, tile_size):
            end_i = min(i + tile_size, N)
            tile = norm_embs[i:end_i]
            sims_block = np.matmul(tile, norm_embs.T)

            for local_idx, global_idx in enumerate(range(i, end_i)):
                row_sims = sims_block[local_idx].copy()
                # Exclude self-similarity
                row_sims[global_idx] = -1.0

                top_indices, top_scores = cls.top_k(row_sims, k=k)
                neighbors = []
                for idx, score in zip(top_indices, top_scores):
                    target_rec = records[idx]
                    neighbors.append(
                        {
                            "doc_id": target_rec.get("doc_id"),
                            "category": target_rec.get("category"),
                            "title": target_rec.get("title"),
                            "similarity": round(float(score), 4),
                        }
                    )

                source_rec = records[global_idx]
                graph.append(
                    {
                        "doc_id": source_rec.get("doc_id"),
                        "category": source_rec.get("category"),
                        "title": source_rec.get("title"),
                        "top_matches": neighbors,
                    }
                )

        return graph

    @classmethod
    def evaluate_specialty_separability(
        cls, similarity_matrix: np.ndarray, categories: List[str]
    ) -> Dict[str, Any]:
        """
        Evaluates the semantic separation of the embedding space:
        - Intra-Specialty Similarity: Average similarity of documents within the same specialty.
        - Inter-Specialty Similarity: Average similarity of documents across different specialties.
        - Separability Ratio: Intra / Inter (Higher is better, target > 1.5x - 2.0x).
        """
        N = len(categories)
        if similarity_matrix.shape != (N, N):
            raise ValueError(f"Matrix shape {similarity_matrix.shape} does not match {N} categories.")

        intra_scores = []
        inter_scores = []

        for i in range(N):
            for j in range(i + 1, N):
                sim = float(similarity_matrix[i, j])
                if categories[i] == categories[j]:
                    intra_scores.append(sim)
                else:
                    inter_scores.append(sim)

        avg_intra = float(np.mean(intra_scores)) if intra_scores else 0.0
        avg_inter = float(np.mean(inter_scores)) if inter_scores else 0.0
        separability_ratio = avg_intra / max(avg_inter, 1e-6)

        return {
            "intra_specialty_mean_similarity": round(avg_intra, 4),
            "inter_specialty_mean_similarity": round(avg_inter, 4),
            "separability_ratio": round(separability_ratio, 2),
            "intra_sample_pairs": len(intra_scores),
            "inter_sample_pairs": len(inter_scores),
        }
