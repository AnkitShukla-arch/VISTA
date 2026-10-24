"""
Cached data loaders for the VISTA NLP Dashboard.

All heavy resources (retrieval engine, embeddings, projections) are loaded once
per Streamlit session via @st.cache_resource and shared across pages.
"""
import sys
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import streamlit as st
import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import settings


# ----------------------------------------------------------------------
# Availability probe (cheap, no model load)
# ----------------------------------------------------------------------
@st.cache_data(ttl=30)
def check_artifacts() -> Dict[str, bool]:
    """Checks which pipeline artifacts exist on disk."""
    processed = Path(settings.DATA_PROCESSED_DIR)
    clustering = Path(settings.DATA_CLUSTERING_DIR)
    return {
        "processed": (processed / "embeddings.npy").exists()
        and (processed / "metadata.json").exists(),
        "clustering": (clustering / "box_index.faiss").exists()
        and (clustering / "box_metadata.json").exists(),
        "similarity": (processed / "similarity_matrix.npy").exists(),
        "projection": (clustering / "pca_projection.npy").exists(),
        "manifest": (clustering / "clustering_manifest.json").exists(),
    }


# ----------------------------------------------------------------------
# Deterministic simulated access telemetry
# ----------------------------------------------------------------------
def _simulated_telemetry(doc_id: str) -> Tuple[float, float, float]:
    """
    Derives stable pseudo telemetry (freshness, call_frequency, importance)
    from the doc_id hash. In production these come from DuckDB analytics over
    real hospital access logs; simulated values keep the priority layer
    demonstrable without live telemetry data.
    """
    h = hashlib.md5(str(doc_id).encode("utf-8")).digest()
    return (
        0.35 + (h[0] / 255.0) * 0.65,  # freshness in [0.35, 1.0]
        0.20 + (h[1] / 255.0) * 0.80,  # call_frequency in [0.20, 1.0]
        0.30 + (h[2] / 255.0) * 0.70,  # importance in [0.30, 1.0]
    )


# ----------------------------------------------------------------------
# Heavy resources
# ----------------------------------------------------------------------
@st.cache_resource(show_spinner="Loading VISTA retrieval engine (first load downloads/initializes the embedding model)...")
def load_engine() -> Any:
    """Loads the full retrieval stack: embedder + FAISS box index + priority engine."""
    from Backend.Clustering.retrieval_engine import VISTARetrievalEngine

    engine = VISTARetrievalEngine.from_default_paths()

    # Enrich metadata with (simulated) priority telemetry for in-box ranking
    for rec in engine.doc_metadata:
        f, c, i = _simulated_telemetry(rec.get("doc_id", ""))
        rec["freshness"] = f
        rec["call_frequency"] = c
        rec["importance"] = i

    # Warm-up query so per-query latency reflects real search, not model load
    engine.search("warmup", top_boxes=1, top_docs_per_box=1)
    return engine


@st.cache_resource(show_spinner="Loading embedding artifacts...")
def load_embeddings() -> Tuple[np.ndarray, List[Dict[str, Any]]]:
    """Loads document embeddings and aligned metadata."""
    processed = Path(settings.DATA_PROCESSED_DIR)
    embeddings = np.load(str(processed / "embeddings.npy"))
    with open(processed / "metadata.json", "r", encoding="utf-8") as f:
        metadata = json.load(f)
    return embeddings, metadata


@st.cache_resource(show_spinner="Loading cluster artifacts...")
def load_cluster_data() -> Dict[str, Any]:
    """Loads labels, projection, box summaries, metrics and manifest."""
    cdir = Path(settings.DATA_CLUSTERING_DIR)
    data: Dict[str, Any] = {}

    if (cdir / "cluster_labels.npy").exists():
        data["labels"] = np.load(str(cdir / "cluster_labels.npy"))
    if (cdir / "pca_projection.npy").exists():
        data["projection"] = np.load(str(cdir / "pca_projection.npy"))
    if (cdir / "box_summaries.json").exists():
        with open(cdir / "box_summaries.json", "r", encoding="utf-8") as f:
            data["box_summaries"] = json.load(f)
    if (cdir / "cluster_metrics.json").exists():
        with open(cdir / "cluster_metrics.json", "r", encoding="utf-8") as f:
            data["metrics"] = json.load(f)
    if (cdir / "k_sweep.json").exists():
        with open(cdir / "k_sweep.json", "r", encoding="utf-8") as f:
            data["k_sweep"] = json.load(f)
    if (cdir / "clustering_manifest.json").exists():
        with open(cdir / "clustering_manifest.json", "r", encoding="utf-8") as f:
            data["manifest"] = json.load(f)
    return data


@st.cache_resource(show_spinner="Loading similarity matrix...")
def load_similarity_matrix() -> Optional[np.ndarray]:
    """Loads the Phase 3 pairwise cosine similarity matrix if present."""
    path = Path(settings.DATA_PROCESSED_DIR) / "similarity_matrix.npy"
    if path.exists():
        return np.load(str(path))
    return None


def get_doc_raw_text(doc: Dict[str, Any]) -> str:
    """Best-effort raw text for display: raw_text field, else diagnostic summary."""
    return (
        doc.get("raw_text")
        or doc.get("diagnostic_summary")
        or "No text preview available for this document."
    )
