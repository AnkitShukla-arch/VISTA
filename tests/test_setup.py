"""
Verification script for VISTA project setup and core math modules.
"""
import sys
from pathlib import Path
import numpy as np

# Ensure project root is in path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import settings
from Backend.ETL.cleaner import MedicalTextCleaner
from Backend.Embeddings.similarity import CosineSimilarityCalculator
from Database.DuckDB.priority_scoring import DuckDBPriorityEngine


def test_config():
    print("Testing config settings...")
    assert settings.PROJECT_NAME == "VISTA"
    assert settings.EMBEDDING_MODEL_NAME == "all-MiniLM-L6-v2"
    print("  [PASS] Config settings loaded properly.")


def test_cleaner():
    print("Testing MedicalTextCleaner...")
    raw = "Patient presents with   acute chest pain. ====\n\n\nFollow up."
    cleaned = MedicalTextCleaner.clean_text(raw)
    assert "====" not in cleaned
    assert "  " not in cleaned
    assert MedicalTextCleaner.compute_hash("hello world") == MedicalTextCleaner.compute_hash("Hello   World ")
    print("  [PASS] MedicalTextCleaner functions as expected.")


def test_cosine_similarity_math():
    print("Testing CosineSimilarityCalculator...")
    # Orthogonal vectors -> similarity = 0
    v1 = np.array([[1.0, 0.0, 0.0]])
    v2 = np.array([[0.0, 1.0, 0.0]])
    sim = CosineSimilarityCalculator.query_similarity(v1, v2)
    assert np.isclose(sim[0], 0.0), f"Expected 0.0, got {sim[0]}"

    # Identical vectors -> similarity = 1
    v3 = np.array([[0.5, 0.5, 0.0]])
    sim_self = CosineSimilarityCalculator.query_similarity(v3, v3)
    assert np.isclose(sim_self[0], 1.0), f"Expected 1.0, got {sim_self[0]}"

    # Pairwise matrix
    mat = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    pairwise = CosineSimilarityCalculator.compute_pairwise_matrix(mat)
    assert pairwise.shape == (3, 3)
    assert np.allclose(np.diag(pairwise), 1.0)
    print("  [PASS] CosineSimilarityCalculator math is verified.")


def test_duckdb_priority_math():
    print("Testing DuckDBPriorityEngine composite scoring...")
    engine = DuckDBPriorityEngine(w_freshness=0.4, w_frequency=0.4, w_importance=0.2)
    score = engine.compute_priority_score(freshness=1.0, call_frequency=1.0, importance=1.0)
    assert np.isclose(score, 1.0)

    score_half = engine.compute_priority_score(freshness=0.5, call_frequency=0.5, importance=0.5)
    assert np.isclose(score_half, 0.5)
    print("  [PASS] DuckDBPriorityEngine priority formula verified.")


if __name__ == "__main__":
    print(f"--- Running VISTA Setup Verification (Python {sys.version.split()[0]}) ---")
    test_config()
    test_cleaner()
    test_cosine_similarity_math()
    test_duckdb_priority_math()
    print("--- ALL VERIFICATION TESTS PASSED SUCCESSFULLY! ---")
