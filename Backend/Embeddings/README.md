# VISTA: Embeddings & Similarity Math Module

**Module**: Embeddings & Similarity Math Engine  
**Architecture Stages**: **Stage 2 (Embeddings & Mathematical Core)** & **Handoff to Stage 3 (Clustering)**  
**Model**: Sentence Transformers (`all-MiniLM-L6-v2`, 384-dimensional dense vectors)

---

## 📌 Overview

This module transforms cleaned clinical text (from the Ingestion, OCR & ETL pipeline) into **normalized 384-dimensional dense vectors** and computes the **pairwise Cosine Similarity Matrix**. 

This document explains **what each file is**, **where it is located**, and **how each downstream module consumes it**.

---

## 📂 File Directory & Purpose

```text
Backend/Embeddings/
├── __init__.py               # Package exports
├── clinical_parser.py        # Section-aware SOAP & discharge parser (avoids 512-token cutoff)
├── embedder.py               # Sentence Transformer (all-MiniLM-L6-v2) 384-D vector engine
├── similarity.py             # Memory-safe tiled Cosine Similarity matrix & Top-K graph builder
├── pipeline.py               # One-click master runner (generates data/processed/ bundle)
└── README.md                 # This instruction guide
```

---

## 🤝 Downstream Module Handoff: Output Locations & Usage

When the pipeline runs, it exports all downstream artifacts into **`data/processed/`**:

```text
data/processed/
├── embeddings.npy            <── For K-Means Clustering & FAISS Vector Index
├── metadata.json             <── For Relational Database & Warehouse (PostgreSQL / Neon)
├── similarity_matrix.npy     <── For Cluster Purity, Graph Algorithms & Evaluation
├── top_k_graph.json          <── For Frontend UI (Similar Past Patients Panel)
└── handoff_manifest.json     <── Pipeline Audit & Verification Manifest
```

---

### 1. For the Clustering & FAISS Vector Index Module

* **File Location**: `data/processed/embeddings.npy`
* **What it is**: NumPy binary array of shape `(N, 384)` with `float32` unit-normalized vectors.
* **How to use it**:

```python
import numpy as np
from sklearn.cluster import KMeans

# 1. Load the pre-computed document embeddings
embeddings = np.load("data/processed/embeddings.npy")  # Shape: (N, 384)

# 2. Run K-Means Box Clustering
kmeans = KMeans(n_clusters=15, random_state=42)
box_assignments = kmeans.fit_predict(embeddings)

# 3. Compute Box Summaries and add to FAISS index
box_centers = kmeans.cluster_centers_  # Shape: (15, 384)
# Add box_centers directly to FAISS IndexFlatIP
```

---

### 2. For the Storage & Data Warehouse Module (Neon / PostgreSQL)

* **File Location**: `data/processed/metadata.json`
* **What it is**: Catalog of document records with IDs, titles, departments, and lengths.
* **How to use it**:

```python
import json

# 1. Load the document catalog
with open("data/processed/metadata.json", "r", encoding="utf-8") as f:
    catalog = json.load(f)

# 2. Insert into PostgreSQL warehouse
for doc in catalog:
    doc_id = doc["doc_id"]
    category = doc["category"]
    title = doc["title"]
    s3_url = f"s3://vista-lake/raw/{doc_id}.pdf"
    
    # Execute SQL insert:
    # INSERT INTO medical_documents (document_id, department, title, s3_url)
    # VALUES (doc_id, category, title, s3_url);
```

---

### 3. For the Metadata Analytics & Priority Scoring Module (DuckDB)

* **File Location**: `data/processed/metadata.json` & `data/processed/top_k_graph.json`
* **What it is**: Document metadata and pre-computed nearest clinical companion cases.
* **How to use it**:

```python
# Compute composite priority score inside matched semantic boxes
priority_score = (0.35 * freshness) + (0.35 * call_frequency) + (0.30 * severity)
# Use priority_score to rank documents returned to the clinician
```

---

### 4. For the Ingestion, OCR & ETL Pipeline

* **Input to this module**: Cleaned text files or CSVs from `RESULT/clean_data/` or `phase1_dataset/`.
* **Connection**: The master pipeline in `Backend/Embeddings/pipeline.py` reads the output from the ETL/OCR stage (`combined_dataset.csv` or `unstructured_notes/`) and automatically executes section-aware parsing and vectorization.

---

## ⚡ How to Run the Embedding Pipeline

To re-generate all embeddings, similarity matrices, and handoff files:

```bash
# Process 50 sample records (quick test)
python Backend/Embeddings/pipeline.py --sample-size 50

# Process full dataset into data/processed/
python Backend/Embeddings/pipeline.py --sample-size 5000
```

---

## 🔍 How to Verify the Outputs

Run the automated correctness auditor:

```bash
python tests/verify_output.py
```

This verifies:
1. Shape is strictly `(N, 384)` with unit $L_2$-length ($\|\vec{v}\|_2 = 1.0000$).
2. No NaNs or infinite values.
3. Similarity matrix is symmetric with diagonal $1.0000$.
4. Specialty separability ratio is $> 2.0\times$ (measured at **4.63×**).
