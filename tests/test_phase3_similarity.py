"""
Integration Test & Benchmark for Phase 3: Scalable Cosine Similarity Engine.
Owner: Arpit Umrao (Embeddings & Similarity Math Engineer)
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import settings
from Backend.Embeddings.clinical_parser import ClinicalSectionParser
from Backend.Embeddings.embedder import MedicalEmbedder
from Backend.Embeddings.similarity import CosineSimilarityCalculator


def load_balanced_specialties(csv_path: Path, categories: list, per_category: int = 4):
    df = pd.read_csv(csv_path)
    records = []
    for cat in categories:
        sub = df[df["category"].str.contains(cat, case=False, na=False)].head(per_category)
        for _, row in sub.iterrows():
            summary = ClinicalSectionParser.build_diagnostic_summary(
                row["text"], title=row["title"], category=row["category"]
            )
            records.append({
                "doc_id": row["doc_id"],
                "category": cat,
                "title": str(row["title"]).strip(),
                "diagnostic_summary": summary
            })
    return records


def main():
    print("=== PHASE 3: SCALABLE COSINE SIMILARITY ENGINE ===")

    # 1. Load balanced records from 3 contrasting specialties
    target_specialties = ["Cardiovascular", "Dentistry", "Allergy"]
    print(f"\n[Step 1] Loading {len(target_specialties) * 4} balanced clinical records...")
    records = load_balanced_specialties(settings.MTSAMPLES_CSV, target_specialties, per_category=4)
    print(f"  Loaded {len(records)} records across: {', '.join(target_specialties)}")

    # 2. Vectorize via MedicalEmbedder
    print(f"\n[Step 2] Generating 384-D embeddings via MedicalEmbedder...")
    embedder = MedicalEmbedder(model_name="all-MiniLM-L6-v2")
    embeddings, _ = embedder.encode_records(records, show_progress_bar=False)
    print(f"  Generated embedding matrix: shape {embeddings.shape}")

    # 3. Compute Pairwise Similarity Matrix (Standard & Tiled)
    print(f"\n[Step 3] Computing Cosine Similarity Matrix...")
    sim_standard = CosineSimilarityCalculator.compute_pairwise_matrix(embeddings)
    sim_tiled = CosineSimilarityCalculator.compute_tiled_pairwise_matrix(embeddings, tile_size=6)

    assert np.allclose(sim_standard, sim_tiled, atol=1e-5), "Tiled matrix does not match standard matrix!"
    print(f"  [PASS] Standard and Tiled algorithms verified (shape: {sim_standard.shape}).")
    print(f"  Diagonal self-similarity: min={np.min(np.diag(sim_standard)):.4f}, max={np.max(np.diag(sim_standard)):.4f}")

    # 4. Evaluate Specialty Separability
    print(f"\n[Step 4] Quantifying Semantic Specialty Separability...")
    categories = [r["category"] for r in records]
    metrics = CosineSimilarityCalculator.evaluate_specialty_separability(sim_standard, categories)
    print("  --------------------------------------------------")
    print(f"  * Intra-Specialty Mean Similarity : {metrics['intra_specialty_mean_similarity']:.4f}")
    print(f"  * Inter-Specialty Mean Similarity : {metrics['inter_specialty_mean_similarity']:.4f}")
    print(f"  * Separability Ratio              : {metrics['separability_ratio']}x (Higher is better)")
    print(f"  * Total Pairwise Comparisons      : {metrics['intra_sample_pairs'] + metrics['inter_sample_pairs']}")
    print("  --------------------------------------------------")
    assert metrics["separability_ratio"] > 1.5, "Separability ratio below acceptable threshold (<1.5x)!"
    print("  [PASS] Strong semantic separability mathematically confirmed!")

    # 5. Build Sparse Top-K Graph
    print(f"\n[Step 5] Building Sparse Top-K Clinical Similarity Graph (K=2)...")
    graph = CosineSimilarityCalculator.build_top_k_similarity_graph(embeddings, records, k=2)
    print("  Sample Graph Nodes (Nearest Clinical Peers):")
    for node in graph[::4]:  # sample one from each category
        print(f"  • Source: [{node['category']}] {node['title'][:40]} (ID: {node['doc_id']})")
        for rank, match in enumerate(node["top_matches"], 1):
            print(f"      -> #{rank}: [{match['category']}] {match['title'][:35]} | Sim: {match['similarity']}")

    # 6. Live Clinical Query Search Test
    query = "patient with irregular heart rhythm, palpitations, and suspected atrial enlargement"
    print(f"\n[Step 6] Running Live Query Retrieval: '{query}'...")
    q_vec = embedder.encode_single(query)
    scores = CosineSimilarityCalculator.query_similarity(q_vec, embeddings)
    top_indices, top_scores = CosineSimilarityCalculator.top_k(scores, k=3)

    print("  Top 3 Ranked Matches:")
    for rank, (idx, score) in enumerate(zip(top_indices, top_scores), 1):
        matched_rec = records[idx]
        print(f"    #{rank} [Score: {score:.4f}] [{matched_rec['category']}] {matched_rec['title']} (ID: {matched_rec['doc_id']})")

    # Assert top result is Cardiovascular
    assert records[top_indices[0]]["category"] == "Cardiovascular", "Top result should be Cardiovascular!"
    print("  [PASS] Cardiology query correctly prioritized cardiology records over dentistry/allergy!")

    print("\n=== PHASE 3 ALL TESTS COMPLETED SUCCESSFULLY! ===")


if __name__ == "__main__":
    main()
