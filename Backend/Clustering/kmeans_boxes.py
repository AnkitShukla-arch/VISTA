"""
K-Means Box Clustering Engine.
Owners: Ansh Gaur (Project Lead) & Ankit Shukla
Groups clinical reports into semantic "boxes" based on document embeddings.
"""
from typing import Dict, List, Any, Optional
import numpy as np


class BoxClusterer:
    """Partitions medical report embeddings into K semantic boxes using K-Means."""

    def __init__(self, n_clusters: int = 15, random_state: int = 42):
        self.n_clusters = n_clusters
        self.random_state = random_state
        self.kmeans = None
        self.cluster_labels_ = None
        self.cluster_centers_ = None

    def fit_predict(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Cluster document embeddings into semantic boxes.

        Args:
            embeddings: (N, D) array of document vectors.

        Returns:
            (N,) array of integer cluster assignments.
        """
        try:
            from sklearn.cluster import KMeans

            self.kmeans = KMeans(
                n_clusters=self.n_clusters,
                random_state=self.random_state,
                n_init="auto",
            )
            self.cluster_labels_ = self.kmeans.fit_predict(embeddings)
            self.cluster_centers_ = self.kmeans.cluster_centers_
            return self.cluster_labels_
        except ImportError:
            raise ImportError("scikit-learn is required for BoxClusterer. Install via: pip install scikit-learn")

    def group_by_box(
        self, records: List[Dict[str, Any]], cluster_labels: np.ndarray
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Organizes records into dictionary keyed by box_id."""
        boxes: Dict[int, List[Dict[str, Any]]] = {i: [] for i in range(self.n_clusters)}
        for record, label in zip(records, cluster_labels):
            record["box_id"] = int(label)
            boxes[int(label)].append(record)
        return boxes
