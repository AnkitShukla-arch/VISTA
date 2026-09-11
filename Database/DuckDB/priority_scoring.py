"""
DuckDB Priority Scoring Engine.
Owner: Anant Dubey (Metadata Analytics & Priority Scoring)
Computes:
    priority_score = (w_f * freshness_score) + (w_c * frequency_score) + (w_i * importance_score)
"""
from pathlib import Path
from typing import Dict, List, Any, Optional
import datetime


class DuckDBPriorityEngine:
    """Analytical engine for metadata freshness and retrieval priority."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        w_freshness: float = 0.35,
        w_frequency: float = 0.35,
        w_importance: float = 0.30,
    ):
        self.db_path = str(db_path) if db_path else ":memory:"
        self.w_freshness = w_freshness
        self.w_frequency = w_frequency
        self.w_importance = w_importance
        self._conn = None

    @property
    def conn(self):
        """Lazy loader for DuckDB connection."""
        if self._conn is None:
            try:
                import duckdb

                if self.db_path != ":memory:":
                    Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
                self._conn = duckdb.connect(self.db_path)
            except ImportError:
                raise ImportError("duckdb is required. Install via: pip install duckdb")
        return self._conn

    def compute_priority_score(
        self, freshness: float, call_frequency: float, importance: float
    ) -> float:
        """
        Computes composite priority score in range [0.0, 1.0].
        All input values should be normalized between 0 and 1.
        """
        score = (
            (self.w_freshness * freshness)
            + (self.w_frequency * call_frequency)
            + (self.w_importance * importance)
        )
        return float(min(max(score, 0.0), 1.0))

    def rank_documents_in_box(
        self, documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Sorts documents within a matched semantic box by composite priority score.
        """
        ranked = []
        for doc in documents:
            f = doc.get("freshness", 0.5)
            c = doc.get("call_frequency", 0.5)
            i = doc.get("importance", 0.5)
            doc_copy = doc.copy()
            doc_copy["priority_score"] = self.compute_priority_score(f, c, i)
            ranked.append(doc_copy)

        ranked.sort(key=lambda x: x["priority_score"], reverse=True)
        return ranked
