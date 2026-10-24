"""
K-Means Box Clustering Engine (Phase 4).

Groups clinical report embeddings into semantic "boxes" using K-Means over
L2-normalized 384-D sentence-transformer vectors. Includes:
- Optimal-K selection via Silhouette score sweep (with elbow/fallback support).
- Cluster quality metrics (silhouette, Davies-Bouldin, Calinski-Harabasz, inertia).
- TF-IDF keyword extraction per box for automatic labeling.
- 2-D projection (PCA) for dashboard visualization.
"""
from typing import Dict, List, Any, Optional, Tuple
import numpy as np


class BoxClusterer:
    """Partitions medical report embeddings into K semantic boxes using K-Means."""

    def __init__(
        self,
        n_clusters: int = 15,
        random_state: int = 42,
        auto_k: bool = False,
        k_range: Tuple[int, int] = (5, 25),
    ):
        self.n_clusters = n_clusters
        self.random_state = random_state
        self.auto_k = auto_k
        self.k_range = k_range
        self.kmeans = None
        self.cluster_labels_ = None
        self.cluster_centers_ = None
        self.k_sweep_ = None  # populated when auto_k=True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize(embeddings: np.ndarray) -> np.ndarray:
        """L2-normalize rows so K-Means optimizes spherical cosine geometry."""
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        return embeddings / np.maximum(norms, 1e-12)

    def _fit_kmeans(self, embeddings: np.ndarray, k: int):
        from sklearn.cluster import KMeans

        return KMeans(n_clusters=k, random_state=self.random_state, n_init="auto").fit(
            embeddings
        )

    # ------------------------------------------------------------------
    # Optimal-K sweep
    # ------------------------------------------------------------------
    def find_optimal_k(
        self,
        embeddings: np.ndarray,
        k_min: Optional[int] = None,
        k_max: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Sweeps K over [k_min, k_max] and selects the K maximizing the mean
        Silhouette score. Falls back gracefully for tiny datasets.

        Returns:
            {"best_k", "scores": [(k, silhouette), ...], "inertias": [(k, inertia), ...]}
        """
        from sklearn.metrics import silhouette_score

        k_min = k_min or self.k_range[0]
        k_max = k_max or self.k_range[1]

        N = embeddings.shape[0]
        # K must satisfy: 2 <= K <= N-1
        k_max = min(k_max, max(2, N - 1))
        k_min = max(2, min(k_min, k_max))

        norm_embs = self._normalize(embeddings)
        scores: List[Tuple[int, float]] = []
        inertias: List[Tuple[int, float]] = []

        for k in range(k_min, k_max + 1):
            km = self._fit_kmeans(norm_embs, k)
            labels = km.labels_
            sil = float(silhouette_score(norm_embs, labels)) if len(set(labels)) > 1 else 0.0
            scores.append((k, round(sil, 4)))
            inertias.append((k, round(float(km.inertia_), 2)))

        best_k = max(scores, key=lambda t: t[1])[0]
        self.k_sweep_ = {"best_k": int(best_k), "scores": scores, "inertias": inertias}
        return self.k_sweep_

    # ------------------------------------------------------------------
    # Core fitting
    # ------------------------------------------------------------------
    def fit_predict(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Cluster document embeddings into semantic boxes.

        Args:
            embeddings: (N, D) array of document vectors.

        Returns:
            (N,) array of integer cluster assignments.
        """
        if self.auto_k:
            sweep = self.find_optimal_k(embeddings)
            self.n_clusters = sweep["best_k"]

        norm_embs = self._normalize(embeddings)

        try:
            from sklearn.cluster import KMeans
        except ImportError:
            raise ImportError(
                "scikit-learn is required for BoxClusterer. Install via: pip install scikit-learn"
            )

        self.kmeans = KMeans(
            n_clusters=self.n_clusters,
            random_state=self.random_state,
            n_init="auto",
        )
        self.cluster_labels_ = self.kmeans.fit_predict(norm_embs)
        self.cluster_centers_ = self.kmeans.cluster_centers_
        return self.cluster_labels_

    def predict(self, embeddings: np.ndarray) -> np.ndarray:
        """Assigns new vectors to the nearest existing box. Requires fit_predict() first."""
        if self.kmeans is None:
            raise ValueError("BoxClusterer has not been fitted. Call fit_predict() first.")
        return self.kmeans.predict(self._normalize(embeddings))

    def group_by_box(
        self, records: List[Dict[str, Any]], cluster_labels: np.ndarray
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Organizes records into a dictionary keyed by box_id."""
        boxes: Dict[int, List[Dict[str, Any]]] = {i: [] for i in range(self.n_clusters)}
        for record, label in zip(records, cluster_labels):
            record["box_id"] = int(label)
            boxes[int(label)].append(record)
        return boxes

    # ------------------------------------------------------------------
    # Quality metrics
    # ------------------------------------------------------------------
    def evaluate_clustering(self, embeddings: np.ndarray) -> Dict[str, Any]:
        """
        Computes clustering quality metrics for the fitted model.

        Returns silhouette, Davies-Bouldin (lower better), Calinski-Harabasz
        (higher better), inertia, cluster sizes and specialty purity.
        """
        from sklearn.metrics import (
            silhouette_score,
            davies_bouldin_score,
            calinski_harabasz_score,
        )

        if self.cluster_labels_ is None:
            raise ValueError("BoxClusterer has not been fitted. Call fit_predict() first.")

        norm_embs = self._normalize(embeddings)
        labels = self.cluster_labels_
        k = len(set(labels))

        sizes = {int(c): int(np.sum(labels == c)) for c in sorted(set(labels))}
        metrics: Dict[str, Any] = {
            "n_clusters": self.n_clusters,
            "k_effective": k,
            "cluster_sizes": sizes,
            "noise_points": 0,
        }

        if k > 1:
            metrics["silhouette_score"] = round(float(silhouette_score(norm_embs, labels)), 4)
            metrics["davies_bouldin_score"] = round(float(davies_bouldin_score(norm_embs, labels)), 4)
            metrics["calinski_harabasz_score"] = round(
                float(calinski_harabasz_score(norm_embs, labels)), 2
            )
            metrics["inertia"] = round(float(self.kmeans.inertia_), 2)
        else:
            metrics["silhouette_score"] = 0.0
            metrics["davies_bouldin_score"] = float("inf")
            metrics["calinski_harabasz_score"] = 0.0
            metrics["inertia"] = 0.0
        return metrics

    # ------------------------------------------------------------------
    # Visualization projection
    # ------------------------------------------------------------------
    def compute_2d_projection(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Projects high-dimensional embeddings to 2-D via PCA for scatter plots.
        """
        from sklearn.decomposition import PCA

        norm_embs = self._normalize(embeddings)
        n_components = 2 if norm_embs.shape[0] >= 2 and norm_embs.shape[1] >= 2 else 1
        pca = PCA(n_components=n_components, random_state=self.random_state)
        proj = pca.fit_transform(norm_embs)
        if proj.shape[1] == 1:
            proj = np.hstack([proj, np.zeros_like(proj)])
        return proj

    # ------------------------------------------------------------------
    # Automatic box labeling
    # ------------------------------------------------------------------
    @staticmethod
    def extract_box_keywords(
        records: List[Dict[str, Any]], top_n: int = 8
    ) -> List[str]:
        """
        Extracts the most representative specialty keywords for a box using TF-IDF
        over the diagnostic summaries of its member documents.
        """
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
        except ImportError:
            raise ImportError(
                "scikit-learn is required for keyword extraction. Install via: pip install scikit-learn"
            )

        corpus = [
            r.get("diagnostic_summary") or r.get("title", "")
            for r in records
            if (r.get("diagnostic_summary") or r.get("title", ""))
        ]
        if not corpus:
            return ["empty-box"]

        # Guard against tiny / degenerate boxes
        try:
            vectorizer = TfidfVectorizer(
                max_features=2000,
                stop_words="english",
                ngram_range=(1, 2),
                min_df=1,
                token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z-]{2,}\b",
            )
            tfidf = vectorizer.fit_transform(corpus)
            if tfidf.shape[1] == 0:
                return ["unlabeled"]
            scores = np.asarray(tfidf.mean(axis=0)).flatten()
            vocab = vectorizer.get_feature_names_out()
            top_idx = np.argsort(-scores)[:top_n]
            return [str(vocab[i]) for i in top_idx if scores[i] > 0][:top_n] or ["unlabeled"]
        except ValueError:
            return ["unlabeled"]

    @staticmethod
    def infer_box_label(records: List[Dict[str, Any]], top_n: int = 4) -> str:
        """
        Derives a human-readable label for a box from the dominant specialty
        categories of its members, e.g. 'Cardiovascular / Surgery / Orthopedic'.
        """
        from collections import Counter

        counts = Counter(
            r.get("category", "Unknown") for r in records if r.get("category")
        )
        if not counts:
            return "Unlabeled Box"
        top = [cat.title() for cat, _ in counts.most_common(top_n)]
        return " / ".join(top)

    def summarize_boxes(
        self, boxes: Dict[int, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        Generates a summary record per box: label, keywords, size,
        dominant specialty, and member doc ids.
        """
        summaries = []
        for box_id in sorted(boxes.keys()):
            members = boxes.get(box_id, [])
            label = self.infer_box_label(members)
            keywords = self.extract_box_keywords(members) if members else []
            summaries.append(
                {
                    "box_id": box_id,
                    "label": label,
                    "keywords": keywords,
                    "size": len(members),
                    "doc_ids": [r.get("doc_id") for r in members],
                }
            )
        return summaries
