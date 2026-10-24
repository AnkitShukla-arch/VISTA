"""HTTP API for the VISTA dashboard.

Run from the repository root with:
    uvicorn Backend.api:app --reload --port 8000
"""
from __future__ import annotations

import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
CLUSTERING = ROOT / "data" / "clustering"
COLORS = ["#59a98b", "#8a9cc4", "#c48c77", "#a68fc0", "#86a865", "#c8a55f", "#65a8b3", "#cc7c8d", "#8399a1", "#a8a46d", "#6d91c1", "#b587a2"]

app = FastAPI(title="VISTA Clinical Search API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=25)
    n_boxes: int = Field(default=2, ge=1, le=12)


class QueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def _engine():
    from Backend.Clustering.retrieval_engine import VISTARetrievalEngine
    return VISTARetrievalEngine.from_default_paths()


def _box_data() -> list[dict[str, Any]]:
    summaries = _read_json(CLUSTERING / "box_summaries.json", [])
    result = [{
        "box_id": int(item["box_id"]),
        "label": item.get("label") or f"Clinical box {item['box_id'] + 1}",
        "doc_count": int(item.get("size", 0)),
        "keywords": item.get("keywords", [])[:8],
        "color": COLORS[int(item["box_id"]) % len(COLORS)],
    } for item in summaries]
    try:
        from Backend.ingestion import uploaded_records
        uploads = uploaded_records()
        added = Counter(int(row.get("box_id", 0)) for row in uploads)
        for box in result:
            box["doc_count"] += added.get(box["box_id"], 0)
    except Exception:
        pass
    return result


def _documents() -> list[dict[str, Any]]:
    rows = _read_json(PROCESSED / "metadata.json", [])
    labels_path = CLUSTERING / "cluster_labels.npy"
    labels = np.load(labels_path).tolist() if labels_path.exists() else []
    assignments = _read_json(CLUSTERING / "doc_box_assignments.json", {})
    result = []
    for index, row in enumerate(rows):
        box_id = row.get("box_id")
        if box_id is None and index < len(labels):
            box_id = labels[index]
        if box_id is None:
            box_id = assignments.get(str(index), 0)
        text = row.get("raw_text") or row.get("diagnostic_summary") or ""
        result.append({
            "doc_id": str(row.get("doc_id", f"report-{index + 1}")),
            "title": str(row.get("title") or row.get("doc_id") or f"Clinical report {index + 1}"),
            "specialty": str(row.get("category") or "General"),
            "box_id": int(box_id),
            "cosine_similarity": 0.0,
            "priority_score": 0.0,
            "snippet": text[:300],
            "full_text": text,
        })
    try:
        from Backend.ingestion import _patient_from_filename, _patient_from_text, uploaded_records
        for row in uploaded_records():
            patient_name = row.get("patient_name")
            if not patient_name or patient_name == "Not found":
                patient_name = _patient_from_text(str(row.get("raw_text") or "")) or _patient_from_filename(str(row.get("source_filename") or row.get("title") or "")) or "Not found"
            patient_name = re.sub(r"^(?:mr|mrs|ms|miss|dr)\.?\s+", "", str(patient_name), flags=re.IGNORECASE).strip()
            title = str(row["title"])
            source_filename = str(row.get("source_filename") or "")
            if patient_name != "Not found" and source_filename and title == Path(source_filename).stem:
                title = f"{patient_name} · Medical report"
            result.append({
                "doc_id": str(row["doc_id"]), "title": title,
                "specialty": str(row.get("specialty") or "Clinical report"), "box_id": int(row.get("box_id", 0)),
                "cosine_similarity": float(row.get("cosine_similarity", 0)), "priority_score": float(row.get("priority_score", 0)),
                "snippet": str(row.get("snippet") or row.get("raw_text", ""))[:300], "full_text": str(row.get("raw_text", "")),
                "patient_name": patient_name, "age": row.get("age"),
                "conditions": row.get("conditions", []), "source_filename": row.get("source_filename", ""),
            })
    except Exception:
        pass
    # Newly uploaded reports lead the doctor-facing collection list.
    return sorted(result, key=lambda doc: 0 if doc.get("source_filename") else 1)


def _direct_search(query: str, limit: int) -> list[dict[str, Any]]:
    """Fast exact patient and clinical-term lookup before semantic ranking."""
    docs = _documents()
    normalized = re.sub(r"[^a-z0-9]+", " ", query.casefold()).strip()
    patient_query = re.sub(
        r"\b(give|show|find|get|retrieve|search|please|me|the|report|reports|medical|record|records|patient|patients|named|name|for|of|about|to|list|all|with|who|has|have|having|and|mr|mrs|ms|miss|dr)\b",
        " ", normalized,
    )
    name_parts = patient_query.split()
    person_cue = bool(re.search(r"\b(mr|mrs|ms|miss|dr|named)\b|\breport\s+(?:of|for)\s+[a-z]", normalized))
    # A two-word name is an explicit lookup. Match indexed patient names,
    # report titles, and source filenames so previously uploaded reports work.
    if len(name_parts) >= 2 or (person_cue and name_parts):
        name = " ".join(name_parts)
        name_hits = []
        for doc in docs:
            searchable = " ".join(str(doc.get(key, "")) for key in ("patient_name", "title", "source_filename", "doc_id")).casefold()
            searchable = re.sub(r"[^a-z0-9]+", " ", searchable)
            if name in searchable:
                item = dict(doc)
                item["cosine_similarity"] = 1.0
                name_hits.append(item)
        if name_hits:
            return name_hits[:limit]

    alias_groups = [
        ("diabetes", ("diabetes", "diabetic", "sugar", "glucose", "hba1c", "hyperglycemia")),
        ("cancer", ("cancer", "carcinoma", "tumor", "tumour", "oncology", "malignancy")),
        ("hypertension", ("hypertension", "blood pressure", "high bp", "htn")),
        ("cardiac", ("heart attack", "myocardial infarction", "troponin", "cardiac")),
    ]
    relevant = next((terms for _, terms in alias_groups if any(term in normalized for term in terms)), None)
    if relevant:
        hits = []
        for doc in docs:
            haystack = " ".join(str(doc.get(key, "")) for key in ("title", "specialty", "snippet", "full_text", "patient_name", "source_filename")).casefold()
            matched = [term for term in relevant if term in haystack]
            if matched:
                item = dict(doc)
                item["cosine_similarity"] = min(0.99, 0.82 + 0.05 * len(matched))
                hits.append(item)
        if hits:
            hits.sort(key=lambda item: (item["cosine_similarity"], bool(item.get("patient_name") and item["patient_name"] != "Not found")), reverse=True)
            return hits[:limit]
    return []


def _is_patient_lookup(query: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", query.casefold())
    has_lookup_intent = re.search(r"\b(patient|patients|report|reports|record|records|named|name|give|show|find|get|retrieve|list)\b", normalized)
    if re.search(r"\b(mr|mrs|ms|miss|dr|named)\b|\breport\s+(?:of|for)\s+[a-z]", normalized):
        return True
    remaining = re.sub(r"\b(give|show|find|get|retrieve|search|please|me|the|report|reports|medical|record|records|patient|patients|named|name|for|of|about|to|list|all|with|who|has|have|having|and|mr|mrs|ms|miss|dr)\b", " ", normalized)
    return bool(has_lookup_intent and len(remaining.split()) >= 2)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "artifacts_ready": (PROCESSED / "metadata.json").exists() and (CLUSTERING / "box_summaries.json").exists(),
        "document_count": len(_documents()),
        "box_count": len(_box_data()),
        "embedding_dimension": 384,
    }


@app.post("/search")
def search(body: SearchRequest):
    import time
    started = time.perf_counter()
    direct_docs = _direct_search(body.query, body.top_k * body.n_boxes)
    if direct_docs or _is_patient_lookup(body.query):
        summaries = {box["box_id"]: box for box in _box_data()}
        grouped: dict[int, list[dict[str, Any]]] = {}
        for doc in direct_docs:
            grouped.setdefault(int(doc["box_id"]), []).append(doc)
        matched = []
        for box_id, members in grouped.items():
            summary = summaries.get(box_id, {})
            matched.append({**summary, "box_id": box_id, "label": summary.get("label", f"Clinical box {box_id + 1}"), "similarity": max(item["cosine_similarity"] for item in members), "keywords": summary.get("keywords", [])})
        return {"matched_boxes": matched, "documents": direct_docs, "latency_ms": round((time.perf_counter() - started) * 1000)}
    try:
        result = _engine().search(body.query, top_boxes=body.n_boxes, top_docs_per_box=body.top_k)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Retrieval is unavailable: {exc}") from exc
    summaries = {b["box_id"]: b for b in _box_data()}
    matched = []
    docs = []
    for box in result.get("boxes", []):
        box_id = int(box["box_id"])
        matched.append({**summaries.get(box_id, {}), "box_id": box_id, "label": box.get("label", "Clinical box"), "similarity": float(box.get("similarity_score", 0)), "keywords": box.get("keywords", [])})
        for doc in box.get("results", []):
            text = doc.get("raw_text") or doc.get("diagnostic_summary") or ""
            docs.append({
                "doc_id": str(doc.get("doc_id", "")), "title": str(doc.get("title") or doc.get("doc_id", "Clinical report")),
                "specialty": str(doc.get("category", "General")), "box_id": box_id,
                "cosine_similarity": float(doc.get("similarity_score", 0)), "priority_score": float(doc.get("priority_score", 0)),
                "snippet": text[:300], "full_text": text,
            })
    try:
        from Backend.ingestion import uploaded_records
        uploaded = uploaded_records(with_vectors=True)
        if uploaded and result.get("boxes"):
            query_vector = _engine().embedder.encode_single(body.query)
            matched_ids = {int(box["box_id"]) for box in result["boxes"]}
            overlay = []
            for item in uploaded:
                if int(item.get("box_id", -1)) not in matched_ids or not item.get("embedding"):
                    continue
                vector = np.asarray(item["embedding"], dtype=np.float32)
                similarity = float(np.dot(query_vector, vector))
                overlay.append({
                    "doc_id": item["doc_id"], "title": item["title"], "specialty": item.get("specialty", "Clinical report"),
                    "box_id": int(item["box_id"]), "cosine_similarity": similarity,
                    "priority_score": float(item.get("priority_score", 0)), "snippet": item.get("snippet", ""),
                    "full_text": item.get("raw_text", ""),
                })
            overlay.sort(key=lambda doc: (doc["cosine_similarity"], doc["priority_score"]), reverse=True)
            docs.extend(overlay[:body.top_k * body.n_boxes])
    except Exception:
        pass
    return {"matched_boxes": matched, "documents": docs, "latency_ms": round((time.perf_counter() - started) * 1000)}


@app.post("/ingestion/jobs")
async def create_ingestion_job(request: Request, filename: str = Query(..., min_length=1, max_length=255)):
    from Backend.ingestion import create_job
    try:
        content = await request.body()
        return create_job(filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/ingestion/jobs")
def get_ingestion_jobs():
    from Backend.ingestion import list_jobs
    return list_jobs()


@app.get("/ingestion/jobs/{job_id}")
def get_ingestion_job(job_id: str):
    from Backend.ingestion import get_job
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    return job


@app.post("/query")
def run_warehouse_query(body: QueryRequest):
    from Backend.ingestion import execute_count_query
    try:
        return execute_count_query(body.question)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Warehouse query failed: {exc}") from exc


@app.get("/boxes")
def boxes():
    return _box_data()


@app.get("/boxes/{box_id}/documents")
def box_documents(box_id: int):
    rows = [doc for doc in _documents() if doc["box_id"] == box_id]
    if not rows and box_id not in {b["box_id"] for b in _box_data()}:
        raise HTTPException(status_code=404, detail="Semantic box not found")
    return rows


@app.get("/documents")
def list_documents(box: int | None = None, specialty: str | None = None, q: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    rows = _documents()
    if box is not None:
        rows = [doc for doc in rows if doc["box_id"] == box]
    if specialty:
        rows = [doc for doc in rows if doc["specialty"].casefold() == specialty.casefold()]
    if q:
        term = q.casefold()
        rows = [doc for doc in rows if term in f"{doc['title']} {doc['doc_id']} {doc['snippet']}".casefold()]
    total = len(rows)
    start = (page - 1) * page_size
    return {"items": rows[start:start + page_size], "total": total, "page": page, "page_size": page_size}


@app.get("/documents/{doc_id}")
def get_document(doc_id: str):
    doc = next((row for row in _documents() if row["doc_id"] == doc_id), None)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@app.get("/projection")
def get_projection():
    path = CLUSTERING / "pca_projection.npy"
    if not path.exists():
        return []
    coordinates = np.load(path)
    docs = _documents()
    return [{"doc_id": doc["doc_id"], "x": float(coordinates[i][0]), "y": float(coordinates[i][1]), "box_id": doc["box_id"], "title": doc["title"], "specialty": doc["specialty"]} for i, doc in enumerate(docs[:len(coordinates)])]


@app.get("/metrics")
def get_metrics():
    raw = _read_json(CLUSTERING / "cluster_metrics.json", {})
    sweep = _read_json(CLUSTERING / "k_sweep.json", {})
    scores = {int(k): float(v) for k, v in sweep.get("scores", [])}
    inertias = {int(k): float(v) for k, v in sweep.get("inertias", [])}
    k_sweep = [{"k": k, "silhouette": score, "inertia": inertias.get(k, 0.0)} for k, score in scores.items()]
    docs = _documents()
    grouped: Counter[tuple[int, str]] = Counter((d["box_id"], d["specialty"]) for d in docs)
    box_names = {b["box_id"]: b["label"] for b in _box_data()}
    box_specialty = [{"box": box_names.get(box_id, f"Box {box_id}"), "specialty": specialty, "count": count} for (box_id, specialty), count in grouped.items()]
    matrix_path = PROCESSED / "similarity_matrix.npy"
    matrix = np.load(matrix_path, mmap_mode="r") if matrix_path.exists() else np.eye(40)
    sample = np.asarray(matrix[:40, :40], dtype=float).tolist()
    return {
        "silhouette": float(raw.get("silhouette_score", 0)), "davies_bouldin": float(raw.get("davies_bouldin_score", 0)),
        "calinski_harabasz": float(raw.get("calinski_harabasz_score", 0)), "specialty_purity": float(raw.get("specialty_purity", 0)),
        "k_sweep": k_sweep, "box_specialty": box_specialty, "similarity_matrix_40x40": sample,
    }
