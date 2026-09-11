"""
Embeddings and Similarity Math Module (Owner: Arpit Umrao)
Responsible for clinical text vectorization using Sentence Transformers (all-MiniLM-L6-v2),
section-aware clinical parsing, and optimized pairwise cosine similarity matrix computation.
"""
from Backend.Embeddings.embedder import MedicalEmbedder
from Backend.Embeddings.similarity import CosineSimilarityCalculator
from Backend.Embeddings.clinical_parser import (
    ClinicalSectionParser,
    ClinicalDataLoader,
)

__all__ = [
    "MedicalEmbedder",
    "CosineSimilarityCalculator",
    "ClinicalSectionParser",
    "ClinicalDataLoader",
]
