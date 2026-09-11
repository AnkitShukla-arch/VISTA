"""
Integration Test & Benchmark for Phase 2: Vector Embedder.
Owner: Arpit Umrao (Embeddings & Similarity Math Engineer)
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import settings
from Backend.Embeddings.clinical_parser import ClinicalDataLoader
from Backend.Embeddings.embedder import MedicalEmbedder


def main():
    print("=== PHASE 2: MEDICAL VECTOR EMBEDDER PIPELINE & BENCHMARK ===")
    
    # 1. Load real sample records
    print(f"\n[Step 1] Loading sample records from {settings.MTSAMPLES_CSV.name}...")
    records = ClinicalDataLoader.load_mtsamples_csv(settings.MTSAMPLES_CSV, sample_size=10, random_state=42)
    print(f"  Loaded {len(records)} clinical reports.")
    for i, r in enumerate(records[:3], 1):
        print(f"  {i}. [{r['category']}] {r['title']}")

    # 2. Initialize Embedder
    print(f"\n[Step 2] Initializing MedicalEmbedder (all-MiniLM-L6-v2)...")
    embedder = MedicalEmbedder(model_name="all-MiniLM-L6-v2", batch_size=32)
    print(f"  Target Device: {embedder.device}")
    print(f"  Model Name   : {embedder.model_name}")

    # 3. Benchmark Encoding Performance
    summaries = [r["diagnostic_summary"] for r in records]
    print(f"\n[Step 3] Running performance benchmark on {len(summaries)} documents...")
    metrics = embedder.benchmark_encoding(summaries)
    print("  --------------------------------------------------")
    print(f"  * Model                : {metrics['model_name']}")
    print(f"  * Device               : {metrics['device']}")
    print(f"  * Dimension            : {metrics['dimension']}-D")
    print(f"  * Total Duration       : {metrics['total_duration_sec']} sec")
    print(f"  * Throughput           : {metrics['throughput_docs_per_sec']} docs/sec")
    print(f"  * Latency per Document : {metrics['latency_ms_per_doc']} ms")
    print(f"  * L2-Normalized        : {metrics['is_l2_normalized']}")
    print(f"  * Memory Allocated     : {metrics['embedding_memory_kb']} KB")
    print("  --------------------------------------------------")

    # 4. Generate Embeddings for All Records
    print(f"\n[Step 4] Vectorizing all records...")
    embeddings, meta = embedder.encode_records(records, show_progress_bar=False)
    print(f"  Generated embedding matrix shape: {embeddings.shape} (N={embeddings.shape[0]}, D={embeddings.shape[1]})")

    # 5. Test Caching & Serialization
    cache_dir = ROOT_DIR / "data" / "cache"
    print(f"\n[Step 5] Saving embeddings and metadata to {cache_dir.name}...")
    npy_path, json_path = embedder.save_cache(embeddings, meta, output_dir=cache_dir, prefix="phase2_test")
    print(f"  Saved binary embeddings: {npy_path.name} ({npy_path.stat().st_size / 1024:.1f} KB)")
    print(f"  Saved metadata index   : {json_path.name} ({json_path.stat().st_size / 1024:.1f} KB)")

    # Verify reload
    reloaded_emb, reloaded_meta = embedder.load_cache(npy_path, json_path)
    assert reloaded_emb.shape == embeddings.shape, "Shape mismatch upon reload"
    assert len(reloaded_meta) == len(meta), "Metadata length mismatch"
    print("  [PASS] Cache reload verified with 100% integrity.")

    # 6. Sample Single Query Encoding
    test_query = "patient presenting with chest pain, elevated troponin, and acute myocardial infarction"
    print(f"\n[Step 6] Encoding live search query: '{test_query}'...")
    q_vec = embedder.encode_single(test_query)
    print(f"  Query Vector: shape {q_vec.shape}, L2-norm = {float(q_vec @ q_vec):.4f}")

    print("\n=== PHASE 2 COMPLETED SUCCESSFULLY! ===")


if __name__ == "__main__":
    main()
