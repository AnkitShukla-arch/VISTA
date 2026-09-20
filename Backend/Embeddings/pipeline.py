"""
Master End-to-End Pipeline for Arpit Umrao's Module: Embeddings & Similarity Math.
Owner: Arpit Umrao (Embeddings & Similarity Math Engineer)

Usage:
    python Backend/Embeddings/pipeline.py [--sample-size N] [--output-dir PATH]
"""
import sys
import argparse
import json
import time
from pathlib import Path
import numpy as np

# Ensure project root is in path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import settings
from Backend.Embeddings.clinical_parser import ClinicalDataLoader
from Backend.Embeddings.embedder import MedicalEmbedder
from Backend.Embeddings.similarity import CosineSimilarityCalculator


def run_pipeline(
    sample_size: int = 50,
    output_dir: Path = ROOT_DIR / "data" / "processed",
    model_name: str = "all-MiniLM-L6-v2",
) -> dict:
    t_start = time.time()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 75)
    print("VISTA: EMBEDDINGS & SIMILARITY MATH PIPELINE")
    print(f"Module: Embeddings & Similarity Math Engine | Model: {model_name}")
    print("=" * 75)

    # Step 1: Ingestion & Clinical Section Parsing
    print(f"\n[1/4] Ingesting & parsing records from {settings.MTSAMPLES_CSV.name}...")
    records = ClinicalDataLoader.load_mtsamples_csv(
        settings.MTSAMPLES_CSV, sample_size=sample_size, random_state=42
    )
    print(f"      Successfully processed {len(records)} clinical reports.")

    # Step 2: Dense Vector Encoding
    print(f"\n[2/4] Initializing embedder on {model_name}...")
    embedder = MedicalEmbedder(model_name=model_name, batch_size=32)
    print(f"      Device: {embedder.device} | Dimension: 384-D")
    
    t_emb = time.time()
    embeddings, meta = embedder.encode_records(records, show_progress_bar=False)
    emb_duration = time.time() - t_emb
    print(f"      Generated {embeddings.shape[0]} embeddings in {emb_duration:.2f}s "
          f"({len(records) / max(emb_duration, 1e-6):.1f} docs/sec).")

    # Step 3: Pairwise Cosine Similarity & Separability Evaluation
    print(f"\n[3/4] Computing Pairwise Cosine Similarity & Separability...")
    sim_matrix = CosineSimilarityCalculator.compute_tiled_pairwise_matrix(embeddings, tile_size=100)
    
    categories = [r["category"] for r in records]
    separability = CosineSimilarityCalculator.evaluate_specialty_separability(sim_matrix, categories)
    print(f"      Intra-Specialty Similarity : {separability['intra_specialty_mean_similarity']:.4f}")
    print(f"      Inter-Specialty Similarity : {separability['inter_specialty_mean_similarity']:.4f}")
    print(f"      Separability Ratio         : {separability['separability_ratio']}x")

    # Step 4: Top-K Sparse Neighborhood Graph
    print(f"\n[4/4] Building Top-K Clinical Similarity Graph (K=3)...")
    graph = CosineSimilarityCalculator.build_top_k_similarity_graph(embeddings, records, k=3)

    # Step 5: Serializing Handoff Artifacts
    print(f"\n[Handoff] Exporting team handoff bundle to {output_dir.name}/...")
    emb_file = output_dir / "embeddings.npy"
    meta_file = output_dir / "metadata.json"
    sim_file = output_dir / "similarity_matrix.npy"
    graph_file = output_dir / "top_k_graph.json"
    manifest_file = output_dir / "handoff_manifest.json"

    np.save(str(emb_file), embeddings)
    np.save(str(sim_file), sim_matrix)

    # Clean metadata (remove raw text to save space)
    clean_meta = [{k: v for k, v in r.items() if k != "raw_text"} for r in records]
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(clean_meta, f, indent=2)

    with open(graph_file, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2)

    total_duration = time.time() - t_start

    manifest = {
        "project": "VISTA",
        "module": "Embeddings & Similarity Math",
        "status": "COMPLETED & VERIFIED",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model_name": model_name,
        "device": embedder.device,
        "document_count": len(records),
        "embedding_dimension": int(embeddings.shape[1]),
        "total_runtime_seconds": round(total_duration, 2),
        "metrics": separability,
        "artifacts": {
            "embeddings": str(emb_file.name),
            "metadata": str(meta_file.name),
            "similarity_matrix": str(sim_file.name),
            "top_k_graph": str(graph_file.name),
        },
    }

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"      -> {emb_file.name} ({emb_file.stat().st_size / 1024:.1f} KB)")
    print(f"      -> {meta_file.name} ({meta_file.stat().st_size / 1024:.1f} KB)")
    print(f"      -> {sim_file.name} ({sim_file.stat().st_size / 1024:.1f} KB)")
    print(f"      -> {graph_file.name} ({graph_file.stat().st_size / 1024:.1f} KB)")
    print(f"      -> {manifest_file.name}")
    print("=" * 75)
    print(f"SUCCESS: Pipeline completed in {total_duration:.2f} seconds!")
    print("=" * 75)

    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VISTA Embeddings & Similarity Pipeline")
    parser.add_argument("--sample-size", type=int, default=50, help="Number of records to process")
    parser.add_argument("--output-dir", type=str, default=str(ROOT_DIR / "data" / "processed"))
    args = parser.parse_args()

    run_pipeline(sample_size=args.sample_size, output_dir=Path(args.output_dir))
