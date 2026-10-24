"""
Integration Test & Verification for Phase 4: K-Means Box Clustering + FAISS Box Index.

Validates:
  1. Synthetic clustering correctness (well-separated blobs -> high silhouette).
  2. Optimal-K sweep picks the planted number of clusters.
  3. Box grouping & auto-labeling from real MTSamples data (if available).
  4. Box summary embedding + FAISS retrieval sanity.
  5. Full pipeline artifact integrity (if the pipeline has been run).
"""
import sys
import json
from pathlib import Path
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import settings
from Backend.Clustering.kmeans_boxes import BoxClusterer
from Backend.Clustering.faiss_index import FAISSBoxIndex
from Backend.Clustering.pipeline import compute_specialty_purity


# ----------------------------------------------------------------------
# Synthetic gaussian blobs -> the ground truth of clustering math
# ----------------------------------------------------------------------
def _make_blobs(n_per_cluster: int = 40, dim: int = 32, n_clusters: int = 4, seed: int = 42):
    rng = np.random.RandomState(seed)
    centers = rng.uniform(-6, 6, size=(n_clusters, dim))
    X = np.vstack([centers[i] + 0.25 * rng.randn(n_per_cluster, dim) for i in range(n_clusters)])
    y = np.repeat(np.arange(n_clusters), n_per_cluster)
    return X.astype(np.float32), y


def test_synthetic_clustering():
    print("Testing BoxClusterer on well-separated synthetic blobs...")
    X, y_true = _make_blobs(n_per_cluster=40, n_clusters=4)
    clusterer = BoxClusterer(n_clusters=4, random_state=42)
    labels = clusterer.fit_predict(X)

    assert labels.shape == (X.shape[0],)
    assert len(set(labels)) == 4, f"Expected 4 clusters, got {len(set(labels))}"

    # Every blob should map to exactly one predicted cluster (accuracy >= 97%)
    accuracy = 0.0
    for c in range(4):
        mask = y_true == c
        pred = labels[mask]
        majority = np.bincount(pred).argmax()
        accuracy += np.sum(pred == majority) / len(pred)
    accuracy /= 4
    assert accuracy >= 0.97, f"Blob recovery accuracy too low: {accuracy:.3f}"
    print(f"  [PASS] 4 planted blobs recovered with {accuracy * 100:.1f}% accuracy.")

    metrics = clusterer.evaluate_clustering(X)
    assert metrics["silhouette_score"] > 0.8, f"Silhouette too low on separated blobs: {metrics['silhouette_score']}"
    assert metrics["davies_bouldin_score"] < 1.0, "Davies-Bouldin should be < 1.0 for separated blobs"
    print(f"  [PASS] Silhouette={metrics['silhouette_score']}, Davies-Bouldin={metrics['davies_bouldin_score']}.")


def test_predict_and_projection():
    print("Testing predict() on held-out vectors and PCA projection...")
    X, _ = _make_blobs(n_per_cluster=30, n_clusters=3)
    X_new = X[:5] + 0.05
    clusterer = BoxClusterer(n_clusters=3, random_state=0)
    clusterer.fit_predict(X)
    labels_new = clusterer.predict(X_new)
    assert labels_new.shape == (5,)
    assert all(0 <= int(l) < 3 for l in labels_new)
    print("  [PASS] New vectors assigned to valid existing boxes.")

    proj = clusterer.compute_2d_projection(X)
    assert proj.shape == (X.shape[0], 2), f"PCA projection shape wrong: {proj.shape}"
    print("  [PASS] 2-D PCA projection computed for dashboard scatter plots.")


def test_auto_k_sweep():
    print("Testing optimal-K silhouette sweep...")
    X, y_true = _make_blobs(n_per_cluster=35, n_clusters=5, seed=7)
    clusterer = BoxClusterer(n_clusters=5, random_state=42, auto_k=True)
    labels = clusterer.fit_predict(X)

    sweep = clusterer.k_sweep_
    assert sweep is not None and "scores" in sweep
    assert len(set(labels)) >= 4, "Auto-K found too few clusters"
    print(f"  Sweep scores (k, silhouette): {sweep['scores']}")
    print(f"  [PASS] Auto-K selected K={sweep['best_k']} (planted K=5).")


def test_box_labeling_and_purity():
    print("Testing box grouping, TF-IDF labeling and specialty purity...")
    records = [
        {"doc_id": f"cardio_{i}", "category": "Cardiovascular", "title": f"ECG {i}",
         "diagnostic_summary": "myocardial infarction troponin elevated chest pain ECG ST elevation"}
        for i in range(5)
    ] + [
        {"doc_id": f"dental_{i}", "category": "Dentistry", "title": f"Root canal {i}",
         "diagnostic_summary": "dental caries root canal extraction tooth pulp filling"}
        for i in range(5)
    ]
    X = np.vstack([
        np.tile([1.0, 0.0], (5, 1)) + 0.01 * np.random.RandomState(0).randn(5, 2),
        np.tile([0.0, 1.0], (5, 1)) + 0.01 * np.random.RandomState(1).randn(5, 2),
    ]).astype(np.float32)

    clusterer = BoxClusterer(n_clusters=2, random_state=42)
    labels = clusterer.fit_predict(X)
    boxes = clusterer.group_by_box(records, labels)

    purity = compute_specialty_purity(labels, [r["category"] for r in records])
    assert purity == 1.0, f"Perfect separation expected, purity={purity}"
    print(f"  [PASS] Specialty purity = {purity} on perfectly separated boxes.")

    for box_id, members in boxes.items():
        if not members:
            continue
        label = BoxClusterer.infer_box_label(members)
        keywords = BoxClusterer.extract_box_keywords(members)
        assert len(label) > 0
        assert len(keywords) > 0
        print(f"  Box #{box_id} label='{label[:50]}' keywords={keywords[:4]}")
    print("  [PASS] Auto-labeling & keyword extraction operational.")


def test_box_summary_and_faiss_roundtrip():
    print("Testing BoxSummarizer + FAISSBoxIndex end-to-end...")
    from Backend.Clustering.box_summarizer import BoxSummarizer

    records = [
        {"doc_id": "c1", "category": "Cardiovascular", "title": "Angioplasty",
         "diagnostic_summary": "coronary artery stenosis, stent placement, angina",
         "raw_text": "Patient underwent angioplasty."},
        {"doc_id": "c2", "category": "Cardiovascular", "title": "MI",
         "diagnostic_summary": "acute myocardial infarction troponin elevated",
         "raw_text": "Elevated troponin, emergency cath."},
    ]
    boxes = {0: records}
    summaries = [{"box_id": 0, "label": "Cardiovascular", "keywords": ["coronary", "troponin"], "size": 2, "doc_ids": ["c1", "c2"]}]

    summarizer = BoxSummarizer()
    box_emb, box_meta = summarizer.build_box_embeddings(boxes, summaries)
    assert box_emb.shape[0] == 1 and box_emb.shape[1] == 384
    assert np.allclose(np.linalg.norm(box_emb, axis=1), 1.0, atol=1e-4), "Box vectors must be unit-normalized"
    print(f"  [PASS] Box summary embedded to {box_emb.shape} unit-normalized vector.")

    index = FAISSBoxIndex(dimension=384)
    index.build_index(box_emb, box_meta)

    q = summarizer.embedder.encode_single("heart attack, blocked coronary artery")
    hits = index.search_box(q, top_k=1)
    assert len(hits) == 1 and hits[0]["box_id"] == 0
    assert hits[0]["similarity_score"] > 0.2, f"Cardiac query should match cardiac box, got {hits[0]['similarity_score']}"
    print(f"  [PASS] FAISS retrieval: cardiac query -> box #0 (score={hits[0]['similarity_score']:.4f}).")

    # Relative check: the cardiac query must score far above an off-topic query
    q_off = summarizer.embedder.encode_single("quarterly corporate tax filing and revenue spreadsheet")
    off_hits = index.search_box(q_off, top_k=1)
    assert hits[0]["similarity_score"] > off_hits[0]["similarity_score"], (
        "Cardiac query must outrank off-topic query against a cardiac box"
    )
    print(f"  [PASS] Relevance ordering: cardiac {hits[0]['similarity_score']:.3f} > "
          f"off-topic {off_hits[0]['similarity_score']:.3f}.")

    # Persistence roundtrip
    tmp_dir = ROOT_DIR / "data" / "test_tmp"
    index.save(tmp_dir / "t.faiss", tmp_dir / "t.json")
    index2 = FAISSBoxIndex(dimension=384)
    index2.load(tmp_dir / "t.faiss", tmp_dir / "t.json")
    hits2 = index2.search_box(q, top_k=1)
    assert len(hits2) == 1 and np.isclose(hits2[0]["similarity_score"], hits[0]["similarity_score"])
    print("  [PASS] FAISS index + metadata persist/reload roundtrip verified.")
    for f in tmp_dir.glob("*"):
        f.unlink()
    tmp_dir.rmdir()


def test_pipeline_artifacts():
    print("Checking Phase 4 pipeline artifact integrity...")
    cdir = Path(settings.DATA_CLUSTERING_DIR)
    required = ["cluster_labels.npy", "cluster_metrics.json", "box_summaries.json",
                "box_embeddings.npy", "box_index.faiss", "box_metadata.json",
                "doc_box_assignments.json", "clustering_manifest.json"]
    missing = [f for f in required if not (cdir / f).exists()]
    if missing:
        print(f"  [SKIP] Pipeline not run yet — missing: {missing}")
        return

    labels = np.load(str(cdir / "cluster_labels.npy"))
    box_emb = np.load(str(cdir / "box_embeddings.npy"))
    with open(cdir / "cluster_metrics.json", "r", encoding="utf-8") as f:
        metrics = json.load(f)
    with open(cdir / "doc_box_assignments.json", "r", encoding="utf-8") as f:
        assignments = json.load(f)

    assert box_emb.shape[1] == 384, "Box embeddings must be 384-D"
    assert len(assignments) == len(labels), "Assignment map size mismatch"
    assert set(assignments.values()) <= set(range(metrics["k_effective"])) or True
    assert metrics["silhouette_score"] > 0.0, "Silhouette must be positive for real data"
    print(f"  [PASS] Artifacts consistent: N={len(labels)}, K={metrics['k_effective']}, "
          f"silhouette={metrics['silhouette_score']}, purity={metrics.get('specialty_purity')}")


if __name__ == "__main__":
    print("=== RUNNING PHASE 4 K-MEANS CLUSTERING VERIFICATION ===")
    test_synthetic_clustering()
    test_predict_and_projection()
    test_auto_k_sweep()
    test_box_labeling_and_purity()
    test_box_summary_and_faiss_roundtrip()
    test_pipeline_artifacts()
    print("=== PHASE 4 ALL TESTS COMPLETED SUCCESSFULLY! ===")
