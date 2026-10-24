"""
VISTA End-to-End Retrieval Engine (Phase 4/5 Integration).

Implements the full thesis pipeline at query time:
    Natural Language Query
        -> MedicalEmbedder (384-D query vector)
        -> FAISSBoxIndex (nearest semantic box match)
        -> CosineSimilarityCalculator (rank docs inside the box)
        -> DuckDBPriorityEngine (priority_score = w_f*freshness + w_c*freq + w_i*importance)
        -> Ranked results to clinician (< 2 sec target)
"""
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
import numpy as np


class VISTARetrievalEngine:
    """
    Full-stack semantic search over the box-clustered medical warehouse.

    Loads artifacts produced by:
      - Backend/Embeddings/pipeline.py   -> data/processed/{embeddings.npy, metadata.json}
      - Backend/Clustering/pipeline.py   -> data/clustering/{cluster_labels.npy, box_index.faiss, box_metadata.json, ...}
    """

    def __init__(self, embedder: Optional[Any] = None, priority_weights: Optional[Dict[str, float]] = None):
        from Backend.Embeddings.embedder import MedicalEmbedder
        from Backend.Clustering.faiss_index import FAISSBoxIndex
        from Backend.Clustering.kmeans_boxes import BoxClusterer
        from Database.DuckDB.priority_scoring import DuckDBPriorityEngine

        self.embedder = embedder or MedicalEmbedder()
        self.faiss_index = FAISSBoxIndex()
        self.clusterer = BoxClusterer()
        weights = priority_weights or {}
        self.priority_engine = DuckDBPriorityEngine(
            w_freshness=weights.get("w_freshness", 0.4),
            w_frequency=weights.get("w_frequency", 0.4),
            w_importance=weights.get("w_importance", 0.2),
        )

        self.doc_embeddings: Optional[np.ndarray] = None
        self.doc_metadata: List[Dict[str, Any]] = []
        self.doc_raw_text: Dict[str, str] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    # Artifact loading
    # ------------------------------------------------------------------
    def load_artifacts(
        self,
        processed_dir: Path,
        clustering_dir: Path,
        include_raw_text: bool = True,
    ) -> None:
        """
        Loads embeddings + metadata + FAISS box index + doc-cluster assignments.

        Args:
            processed_dir:  directory containing embeddings.npy & metadata.json (Phase 2/3 outputs)
            clustering_dir: directory containing cluster_labels.npy, box_index.faiss,
                            box_metadata.json, doc_box_assignments.json (Phase 4 outputs)
        """
        import json

        processed_dir = Path(processed_dir)
        clustering_dir = Path(clustering_dir)

        self.doc_embeddings = np.load(str(processed_dir / "embeddings.npy"))
        with open(processed_dir / "metadata.json", "r", encoding="utf-8") as f:
            self.doc_metadata = json.load(f)

        assignments_path = clustering_dir / "doc_box_assignments.json"
        if assignments_path.exists():
            with open(assignments_path, "r", encoding="utf-8") as f:
                self.doc_box_assignments = json.load(f)
        else:
            self.doc_box_assignments = {}

        if include_raw_text:
            raw_text_path = clustering_dir / "raw_texts.json"
            if raw_text_path.exists():
                with open(raw_text_path, "r", encoding="utf-8") as f:
                    self.doc_raw_text = json.load(f)

        self.faiss_index.load(
            clustering_dir / "box_index.faiss", clustering_dir / "box_metadata.json"
        )
        self._loaded = True

    @classmethod
    def from_default_paths(cls, **kwargs) -> "VISTARetrievalEngine":
        from config.settings import settings

        engine = cls(**kwargs)
        engine.load_artifacts(
            processed_dir=settings.DATA_PROCESSED_DIR,
            clustering_dir=settings.DATA_CLUSTERING_DIR,
        )
        return engine

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def search(
        self,
        query: str,
        top_boxes: int = 1,
        top_docs_per_box: int = 5,
        rank_within_box_by_similarity: bool = True,
    ) -> Dict[str, Any]:
        """
        Full pipeline: query -> box match -> in-box ranking -> priority ordering.

        Args:
            query: natural language clinical query.
            top_boxes: number of nearest semantic boxes to retrieve.
            top_docs_per_box: number of documents to return per box.
            rank_within_box_by_similarity: if True, rank docs inside the box by
                cosine similarity to the query (then priority score as tiebreaker);
                if False, rank purely by priority score.

        Returns:
            {"query", "elapsed_sec", "boxes": [{box metadata + results:[...] }]}
        """
        if not self._loaded:
            raise ValueError("Artifacts not loaded. Call load_artifacts() first.")

        t0 = time.time()
        q_vec = self.embedder.encode_single(query)

        # Step 1: nearest semantic boxes via FAISS (box-level index only)
        box_matches = self.faiss_index.search_box(q_vec, top_k=top_boxes)

        boxes_out = []
        for box_meta in box_matches:
            box_id = int(box_meta["box_id"])

            # Step 2: candidate docs inside the matched box
            candidates = [
                (idx, rec)
                for idx, rec in enumerate(self.doc_metadata)
                if self.doc_box_assignments.get(str(idx)) == box_id
                or rec.get("box_id") == box_id
            ]
            if not candidates:
                continue

            # Step 3: in-box ranking — cosine similarity to the query
            cand_indices = [idx for idx, _ in candidates]
            cand_vectors = self.doc_embeddings[cand_indices]
            from Backend.Embeddings.similarity import CosineSimilarityCalculator

            sims = CosineSimilarityCalculator.query_similarity(q_vec, cand_vectors)

            # Step 4: combine similarity + priority score per doc
            scored = []
            for (idx, rec), sim in zip(candidates, sims):
                d = dict(rec)
                d["similarity_score"] = round(float(sim), 4)
                d["priority_score"] = self.priority_engine.compute_priority_score(
                    freshness=d.get("freshness", 0.5),
                    call_frequency=d.get("call_frequency", 0.5),
                    importance=d.get("importance", 0.5),
                )
                d["box_id"] = box_id
                d["raw_text"] = self.doc_raw_text.get(str(d.get("doc_id")), "")
                scored.append(d)

            if rank_within_box_by_similarity:
                scored.sort(
                    key=lambda d: (d["similarity_score"], d["priority_score"]),
                    reverse=True,
                )
            else:
                scored.sort(key=lambda d: d["priority_score"], reverse=True)

            top_docs = scored[:top_docs_per_box]
            boxes_out.append({**box_meta, "results": top_docs})

        elapsed = time.time() - t0
        return {"query": query, "elapsed_sec": round(elapsed, 3), "boxes": boxes_out}

    # ------------------------------------------------------------------
    # Cluster analytics for the dashboard
    # ------------------------------------------------------------------
    def get_box_overview(self) -> List[Dict[str, Any]]:
        """Returns box-level metadata for dashboard tables/charts."""
        if not self._loaded:
            raise ValueError("Artifacts not loaded. Call load_artifacts() first.")
        return self.faiss_index.box_metadata

    def get_cluster_metrics(self) -> Dict[str, Any]:
        """Loads clustering quality metrics produced by the Phase 4 pipeline."""
        import json
        from config.settings import settings

        metrics_path = Path(settings.DATA_CLUSTERING_DIR) / "cluster_metrics.json"
        if metrics_path.exists():
            with open(metrics_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
