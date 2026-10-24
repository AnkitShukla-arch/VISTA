"""
Master End-to-End Pipeline: Phase 4 — K-Means Box Clustering + FAISS Box Index.

Consumes the Phase 2/3 handoff bundle in data/processed/ (or regenerates it from
the MTSamples CSV) and produces the complete box-clustering layer:

    data/clustering/
    ├── cluster_labels.npy          # (N,) box assignment per document
    ├── cluster_metrics.json        # silhouette / DB / CH / purity metrics
    ├── box_summaries.json          # per-box label, keywords, size, members
    ├── box_embeddings.npy          # (K, 384) box-level summary vectors
    ├── box_index.faiss             # FAISS IndexFlatIP over box embeddings
    ├── box_metadata.json           # FAISS-side metadata per box
    ├── doc_box_assignments.json    # doc index -> box_id map for retrieval
    ├── raw_texts.json              # doc_id -> raw text (for dashboard display)
    ├── pca_projection.npy          # (N, 2) PCA projection for dashboards
    ├── k_sweep.json                # optional silhouette sweep over K
    └── clustering_manifest.json    # audit manifest

Usage:
    python Backend/Clustering/pipeline.py [--sample-size N] [--k K] [--auto-k] [--no-embed]
"""
import sys
import argparse
import json
import time
from pathlib import Path
from typing import List
import numpy as np

# Ensure project root is in path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import settings
from Backend.Clustering.kmeans_boxes import BoxClusterer
from Backend.Clustering.box_summarizer import BoxSummarizer
from Backend.Clustering.faiss_index import FAISSBoxIndex


# ----------------------------------------------------------------------
# Embedding source: cached from Phase 2/3 or freshly generated
# ----------------------------------------------------------------------
def _load_or_generate_embeddings(
    sample_size: int, regenerate: bool, model_name: str
):
    processed_dir = Path(settings.DATA_PROCESSED_DIR)
    emb_path = processed_dir / "embeddings.npy"
    meta_path = processed_dir / "metadata.json"

    if not regenerate and emb_path.exists() and meta_path.exists():
        print(f"[1/6] Loading cached Phase 2/3 embeddings from {emb_path}...")
        embeddings = np.load(str(emb_path))
        with open(meta_path, "r", encoding="utf-8") as f:
            records = json.load(f)
        print(f"      Loaded {embeddings.shape[0]} document vectors ({embeddings.shape[1]}-D).")
        return embeddings, records

    print(f"[1/6] Generating fresh embeddings from {settings.MTSAMPLES_CSV.name}...")
    from Backend.Embeddings.clinical_parser import ClinicalDataLoader
    from Backend.Embeddings.embedder import MedicalEmbedder

    records = ClinicalDataLoader.load_mtsamples_csv(
        settings.MTSAMPLES_CSV, sample_size=sample_size, random_state=42
    )
    print(f"      Parsed {len(records)} clinical reports.")
    embedder = MedicalEmbedder(model_name=model_name, batch_size=32)
    embeddings, records = embedder.encode_records(records, show_progress_bar=False)
    print(f"      Encoded to {embeddings.shape} on device: {embedder.device}.")

    processed_dir.mkdir(parents=True, exist_ok=True)
    np.save(str(emb_path), embeddings)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    print(f"      Cached handoff bundle -> {emb_path.parent}/")
    return embeddings, records


# ----------------------------------------------------------------------
# Specialty purity: do boxes align with true hospital departments?
# ----------------------------------------------------------------------
def compute_specialty_purity(labels: np.ndarray, categories: List) -> float:
    """Fraction of documents whose box matches the majority specialty in that box."""
    total = len(categories)
    if total == 0:
        return 0.0
    correct = 0
    for box_id in set(labels):
        mask = labels == box_id
        box_cats = [categories[i] for i in np.where(mask)[0]]
        if not box_cats:
            continue
        majority = max(set(box_cats), key=box_cats.count)
        correct += sum(1 for c in box_cats if c == majority)
    return round(correct / total, 4)


def run_pipeline(
    sample_size: int = 300,
    n_clusters: int = 12,
    auto_k: bool = False,
    regenerate_embeddings: bool = False,
    model_name: str = "all-MiniLM-L6-v2",
    save_raw_texts: bool = True,
) -> dict:
    t_start = time.time()
    out_dir = Path(settings.DATA_CLUSTERING_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("VISTA: PHASE 4 — K-MEANS BOX CLUSTERING & FAISS BOX INDEX")
    print(f"Output directory: {out_dir}")
    print("=" * 78)

    # ------------------------------------------------------------------
    # Step 1: Document embeddings (cache-first)
    # ------------------------------------------------------------------
    embeddings, records = _load_or_generate_embeddings(
        sample_size=sample_size,
        regenerate=regenerate_embeddings,
        model_name=model_name,
    )
    N = len(records)
    if N != embeddings.shape[0]:
        raise RuntimeError(
            f"Metadata length ({N}) != embedding rows ({embeddings.shape[0]}). "
            "Re-run with --no-cache to regenerate a consistent bundle."
        )
    categories = [r.get("category", "Unknown") for r in records]

    # ------------------------------------------------------------------
    # Step 2: K-Means box clustering
    # ------------------------------------------------------------------
    print(f"\n[2/6] Running K-Means box clustering (K={n_clusters}, auto_k={auto_k})...")
    clusterer = BoxClusterer(n_clusters=n_clusters, random_state=42, auto_k=auto_k)
    t_km = time.time()
    labels = clusterer.fit_predict(embeddings)
    km_duration = time.time() - t_km
    effective_k = len(set(labels))
    print(f"      Clustered {N} documents into {effective_k} boxes in {km_duration:.2f}s.")

    # ------------------------------------------------------------------
    # Step 3: Clustering quality evaluation
    # ------------------------------------------------------------------
    print("\n[3/6] Evaluating cluster quality...")
    metrics = clusterer.evaluate_clustering(embeddings)
    metrics["specialty_purity"] = compute_specialty_purity(labels, categories)
    metrics["documents"] = N
    print(f"      Silhouette Score       : {metrics['silhouette_score']}")
    print(f"      Davies-Bouldin Score   : {metrics['davies_bouldin_score']} (lower is better)")
    print(f"      Calinski-Harabasz      : {metrics['calinski_harabasz_score']}")
    print(f"      Specialty Purity       : {metrics['specialty_purity']}")

    # ------------------------------------------------------------------
    # Step 4: Box summaries + labels
    # ------------------------------------------------------------------
    print("\n[4/6] Generating semantic box summaries & labels...")
    boxes = clusterer.group_by_box(records, labels)
    box_summaries = clusterer.summarize_boxes(boxes)
    for s in box_summaries[:5]:
        print(f"      Box #{s['box_id']:>2} [{s['size']:>3} docs] {s['label'][:70]}")
    print(f"      ... ({len(box_summaries)} boxes total)")

    # ------------------------------------------------------------------
    # Step 5: Box embeddings + FAISS box index
    # ------------------------------------------------------------------
    print("\n[5/6] Embedding box summaries & building FAISS box index...")
    summarizer = BoxSummarizer()
    box_embeddings, box_metadata = summarizer.build_box_embeddings(boxes, box_summaries)
    print(f"      Box embedding matrix: {box_embeddings.shape}")

    faiss_index = FAISSBoxIndex(dimension=box_embeddings.shape[1])
    faiss_index.build_index(box_embeddings, box_metadata)
    faiss_index.save(out_dir / "box_index.faiss", out_dir / "box_metadata.json")
    print(f"      FAISS IndexFlatIP built over {len(box_metadata)} box vectors.")

    # Smoke-test the index with a representative query
    q = summarizer.embedder.encode_single("patient with chest pain and myocardial infarction")
    hits = faiss_index.search_box(q, top_k=2)
    print(f"      Smoke-test query matched box #{hits[0]['box_id']} "
          f"({hits[0]['label'][:40]}...) score={hits[0]['similarity_score']:.4f}")

    # ------------------------------------------------------------------
    # Step 6: Persist all artifacts
    # ------------------------------------------------------------------
    print("\n[6/6] Persisting clustering artifacts...")
    files: dict = {}

    np.save(str(out_dir / "cluster_labels.npy"), labels)
    files["cluster_labels"] = "cluster_labels.npy"

    np.save(str(out_dir / "box_embeddings.npy"), box_embeddings)
    files["box_embeddings"] = "box_embeddings.npy"

    with open(out_dir / "cluster_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    files["cluster_metrics"] = "cluster_metrics.json"

    with open(out_dir / "box_summaries.json", "w", encoding="utf-8") as f:
        json.dump(box_summaries, f, indent=2)
    files["box_summaries"] = "box_summaries.json"

    with open(out_dir / "box_metadata.json", "w", encoding="utf-8") as f:
        json.dump(box_metadata, f, indent=2)

    doc_box_assignments = {str(i): int(labels[i]) for i in range(N)}
    with open(out_dir / "doc_box_assignments.json", "w", encoding="utf-8") as f:
        json.dump(doc_box_assignments, f)
    files["doc_box_assignments"] = "doc_box_assignments.json"

    if save_raw_texts:
        raw_texts = {r.get("doc_id", ""): r.get("raw_text", "") for r in records}
        with open(out_dir / "raw_texts.json", "w", encoding="utf-8") as f:
            json.dump(raw_texts, f)
        files["raw_texts"] = "raw_texts.json"

    projection = clusterer.compute_2d_projection(embeddings)
    np.save(str(out_dir / "pca_projection.npy"), projection)
    files["pca_projection"] = "pca_projection.npy"

    if clusterer.k_sweep_:
        with open(out_dir / "k_sweep.json", "w", encoding="utf-8") as f:
            json.dump(clusterer.k_sweep_, f, indent=2)
        files["k_sweep"] = "k_sweep.json"

    total_duration = time.time() - t_start
    manifest = {
        "project": "VISTA",
        "module": "Phase 4 — K-Means Box Clustering & FAISS Box Index",
        "status": "COMPLETED & VERIFIED",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model_name": model_name,
        "document_count": N,
        "n_clusters_requested": n_clusters,
        "n_clusters_effective": effective_k,
        "auto_k": auto_k,
        "kmeans_duration_sec": round(km_duration, 3),
        "total_runtime_seconds": round(total_duration, 2),
        "metrics": metrics,
        "artifacts": files,
    }
    with open(out_dir / "clustering_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    for name in files.values():
        p = out_dir / name
        print(f"      -> {name} ({p.stat().st_size / 1024:.1f} KB)")
    print(f"      -> clustering_manifest.json")

    print("=" * 78)
    print(f"SUCCESS: Phase 4 clustering pipeline completed in {total_duration:.2f}s!")
    print("Handoff ready: retrieval engine + Streamlit NLP dashboard.")
    print("=" * 78)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VISTA Phase 4: K-Means Box Clustering Pipeline")
    parser.add_argument("--sample-size", type=int, default=300, help="Documents to process if no cache exists")
    parser.add_argument("--k", type=int, default=12, help="Number of semantic boxes")
    parser.add_argument("--auto-k", action="store_true", help="Select K via silhouette sweep")
    parser.add_argument("--regenerate", action="store_true", help="Recompute embeddings from CSV")
    parser.add_argument("--no-raw-texts", action="store_true", help="Skip saving raw_texts.json")
    parser.add_argument("--model", type=str, default="all-MiniLM-L6-v2")
    args = parser.parse_args()

    run_pipeline(
        sample_size=args.sample_size,
        n_clusters=args.k,
        auto_k=args.auto_k,
        regenerate_embeddings=args.regenerate,
        model_name=args.model,
        save_raw_texts=not args.no_raw_texts,
    )
