"""
Box Summary Generator (Phase 4).

For each K-Means semantic box, generates a compact, information-dense summary
record and embeds it into a 384-D box-level vector. Only these box-level summary
embeddings get indexed into FAISS — the core of VISTA's box-clustering thesis.
"""
from typing import Dict, List, Any, Optional, Tuple
import numpy as np

try:
    from Backend.Embeddings.embedder import MedicalEmbedder
except ImportError:  # allow running as a script from repo root
    import sys
    from pathlib import Path

    ROOT_DIR = Path(__file__).resolve().parent.parent.parent
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))
    from Backend.Embeddings.embedder import MedicalEmbedder


class BoxSummarizer:
    """Builds per-box summary texts and their dense embeddings for FAISS."""

    def __init__(self, embedder: Optional[MedicalEmbedder] = None):
        self.embedder = embedder or MedicalEmbedder()

    @staticmethod
    def build_box_summary_text(
        box_id: int,
        members: List[Dict[str, Any]],
        keywords: Optional[List[str]] = None,
        max_members: int = 8,
        max_chars: int = 1500,
    ) -> str:
        """
        Composes a dense text description of a semantic box from its members:
        label, size, dominant specialties, and representative diagnostic summaries.

        The text is intentionally compact: one embedding per box instead of one
        per document.
        """
        from collections import Counter

        categories = Counter(m.get("category", "Unknown") for m in members)
        dom_cats = ", ".join(f"{c} ({n})" for c, n in categories.most_common(5))

        parts = [
            f"Medical semantic box #{box_id} containing {len(members)} clinical reports.",
            f"Dominant specialties: {dom_cats}.",
        ]
        if keywords:
            parts.append(f"Representative clinical concepts: {', '.join(keywords[:10])}.")

        # Representative member summaries (most salient diagnostic content)
        sample = members[:max_members]
        summaries = []
        for m in sample:
            title = m.get("title") or m.get("doc_id", "report")
            summary = (m.get("diagnostic_summary") or m.get("raw_text") or "").strip()
            # Use a tight per-member excerpt to keep the box embedding compact
            summaries.append(f"- {title}: {summary[:220]}")

        parts.append("Sample reports in this box:")
        parts.extend(summaries)

        text = "\n".join(parts)
        if len(text) > max_chars:
            text = text[:max_chars].rsplit(" ", 1)[0] + "..."
        return text

    def build_box_embeddings(
        self,
        boxes: Dict[int, List[Dict[str, Any]]],
        box_summaries: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """
        Embeds every box summary into a 384-D unit-normalized vector.

        Args:
            boxes: mapping box_id -> member records.
            box_summaries: optional precomputed summaries from BoxClusterer.summarize_boxes().

        Returns:
            (box_embeddings (K, 384), box_metadata list aligned with rows)
        """
        if box_summaries is None:
            raise ValueError(
                "box_summaries is required. Generate with BoxClusterer.summarize_boxes() first."
            )

        texts, metadata = [], []
        for s in box_summaries:
            box_id = s["box_id"]
            members = boxes.get(box_id, [])
            text = self.build_box_summary_text(
                box_id=box_id, members=members, keywords=s.get("keywords")
            )
            texts.append(text)
            metadata.append(
                {
                    "box_id": box_id,
                    "label": s.get("label", f"Box {box_id}"),
                    "size": s.get("size", len(members)),
                    "keywords": s.get("keywords", []),
                    "summary_text": text,
                }
            )

        embeddings = self.embedder.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )
        return embeddings.astype(np.float32), metadata
