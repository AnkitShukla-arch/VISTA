# VISTA: Phase 4 — K-Means Box Clustering & FAISS Box Index

**Module**: Clustering & Box Index Layer
**Architecture Stage**: **Stage 3 (Box-Clustering) → Handoff to Retrieval (Stage 4)**
**Algorithm**: K-Means over L2-normalized 384-D Sentence-Transformer vectors + FAISS `IndexFlatIP` over box-level summaries

---

## 📌 Overview

This module implements the core of VISTA's thesis: instead of embedding and indexing **every document individually**, documents are grouped into semantic **boxes** (K-Means clusters), a compact summary is embedded **per box**, and only those K box-level vectors are indexed in FAISS. A query matches the nearest box first, then documents inside it are ranked by cosine similarity + the DuckDB priority score.

```
1,000 docs ──K-Means──> 12 boxes ──summarize──> 12 box embeddings ──FAISS──> box-level index
                                                                            (12 vectors, not 1,000)
```

---

## 📂 File Directory & Purpose

```text
Backend/Clustering/
├── __init__.py            # Package exports
├── kmeans_boxes.py        # BoxClusterer: fit_predict, auto-K sweep, quality metrics, auto-labels
├── box_summarizer.py      # BoxSummarizer: per-box summary text + 384-D box embedding
├── faiss_index.py         # FAISSBoxIndex: build / search / save / load over box vectors
├── retrieval_engine.py    # VISTARetrievalEngine: query → box → ranked docs (end-to-end)
├── pipeline.py            # One-click Phase 4 master runner
└── README.md              # This guide
```

---

## 🚀 Run the Pipeline

```bash
# Uses the Phase 2/3 cache in data/processed/ if present,
# otherwise re-embeds from the MTSamples CSV.
python Backend/Clustering/pipeline.py --auto-k
```

Options:

| Flag | Description |
|---|---|
| `--k 12` | Fixed number of semantic boxes |
| `--auto-k` | Sweep K via silhouette score and pick the best |
| `--sample-size 300` | Docs to embed if no cache exists |
| `--regenerate` | Force re-embedding from CSV |
| `--no-raw-texts` | Skip `raw_texts.json` export |

Measured run (1,000 real MTSamples reports, K=12):

```
Silhouette Score     : 0.0443
Davies-Bouldin Score : 3.67   (lower is better)
Calinski-Harabasz    : 19.62
Specialty Purity     : 0.955  ← 95.5% of docs sit in their box's majority specialty
```

---

## 📦 Output Artifacts (`data/clustering/`)

```text
data/clustering/
├── cluster_labels.npy          # (N,) box assignment per document
├── cluster_metrics.json        # silhouette / Davies-Bouldin / CH / purity
├── box_summaries.json          # per-box: label, keywords, size, member doc_ids
├── box_embeddings.npy          # (K, 384) box-level summary vectors
├── box_index.faiss             # FAISS IndexFlatIP over box embeddings
├── box_metadata.json           # FAISS-side metadata aligned with index rows
├── doc_box_assignments.json    # doc index -> box_id (retrieval join map)
├── raw_texts.json              # doc_id -> raw text (dashboard previews)
├── pca_projection.npy          # (N, 2) PCA projection (dashboard scatter)
├── k_sweep.json                # silhouette sweep over K (with --auto-k)
└── clustering_manifest.json    # audit manifest
```

---

## 🔍 How Each File Is Consumed

### 1. BoxClusterer (`kmeans_boxes.py`)

- `fit_predict(embeddings)` — L2-normalizes rows (so K-Means optimizes spherical/cosine geometry), then clusters. With `auto_k=True` it first sweeps K via `find_optimal_k`.
- `evaluate_clustering(embeddings)` — silhouette, Davies-Bouldin, Calinski-Harabasz, inertia, per-box sizes.
- `summarize_boxes(boxes)` — per-box human-readable label (dominant specialties) + TF-IDF keywords.
- `predict(X_new)` — assign held-out documents/queries to existing boxes.
- `compute_2d_projection(embeddings)` — PCA to 2-D for dashboards.

### 2. BoxSummarizer (`box_summarizer.py`)

- `build_box_summary_text(box_id, members, keywords)` — dense text: box size, dominant specialties, representative diagnostic excerpts. One embedding per box instead of per document.
- `build_box_embeddings(boxes, summaries)` — encodes all box summaries to unit-normalized `(K, 384)` vectors + aligned metadata for FAISS.

### 3. FAISSBoxIndex (`faiss_index.py`)

- `build_index(box_embeddings, box_metadata)` — exact `IndexFlatIP`; vectors are pre-normalized so inner product = cosine similarity.
- `search_box(query_embedding, top_k)` — nearest semantic boxes with scores.
- `save()` / `load()` — persist/reload index + metadata (paths from `config.settings`).

### 4. VISTARetrievalEngine (`retrieval_engine.py`)

The end-to-end query path:

```python
from Backend.Clustering.retrieval_engine import VISTARetrievalEngine

engine = VISTARetrievalEngine.from_default_paths()
result = engine.search(
    "patient with elevated troponin and acute myocardial infarction",
    top_boxes=2,          # nearest semantic boxes via FAISS
    top_docs_per_box=5,   # ranked by cosine sim, tie-broken by priority score
)
print(result["elapsed_sec"])    # search latency (model cached after first load)
for box in result["boxes"]:
    print(box["box_id"], box["label"], box["similarity_score"])
    for doc in box["results"]:
        print("   ", doc["similarity_score"], doc["priority_score"], doc["title"])
```

Priority score per document: `priority = w_f·freshness + w_c·call_frequency + w_i·importance` (weights via `priority_weights=`). In production these signals come from DuckDB analytics over real access logs; the dashboard enriches records with clearly-labeled simulated telemetry when live data is absent.

---

## 🧪 Verification

```bash
python tests/test_phase4_clustering.py
```

Covers: synthetic blob recovery (100% accuracy, silhouette > 0.9), auto-K sweep correctness, box labeling/purity, box-summary embedding shape + normalization, FAISS retrieval relevance ordering, persist/reload roundtrip, and full pipeline artifact integrity.

---

## 🤝 Downstream Consumers

| Consumer | Files used |
|---|---|
| Streamlit NLP dashboard (`Frontend/Streamlit/app.py`) | everything in `data/clustering/` + `data/processed/` |
| Neon/PostgreSQL warehouse | `box_summaries.json`, `doc_box_assignments.json` |
| DuckDB analytics | `box_summaries.json` (box stats), priority weights |
| Academic evaluation | `cluster_metrics.json`, `k_sweep.json`, `clustering_manifest.json` |
