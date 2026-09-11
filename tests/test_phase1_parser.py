"""
Unit & Integration Tests for Phase 1: Clinical Section Parser & Data Loader.
"""
import sys
from pathlib import Path

# Ensure project root is in path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import settings
from Backend.Embeddings.clinical_parser import (
    ClinicalSectionParser,
    ClinicalDataLoader,
)


def test_section_parsing_synthetic():
    print("Testing ClinicalSectionParser on synthetic SOAP report...")
    raw_report = """
    SUBJECTIVE: 54-year-old female presents with severe recurrent migraine.
    MEDICATIONS: Sumatriptan as needed.
    OBJECTIVE: Blood pressure 130/85. Neurological examination normal.
    ASSESSMENT: Chronic intractable migraine with aura.
    PLAN: Initiate prophylactic propranolol 40mg daily. Follow up in 4 weeks.
    """

    sections = ClinicalSectionParser.parse_sections(raw_report)
    assert "SUBJECTIVE" in sections, "Failed to extract SUBJECTIVE section"
    assert "ASSESSMENT" in sections, "Failed to extract ASSESSMENT section"
    assert "PLAN" in sections, "Failed to extract PLAN section"
    assert "Chronic intractable migraine" in sections["ASSESSMENT"]

    summary = ClinicalSectionParser.build_diagnostic_summary(
        text=raw_report,
        title="Neurology Consult",
        category="Neurology",
    )
    assert "Assessment:" in summary or "Specialty: Neurology" in summary
    assert "Chronic intractable migraine" in summary
    print("  [PASS] Synthetic section extraction & summary successful.")


def test_real_mtsamples_loading():
    csv_path = settings.MTSAMPLES_CSV
    print(f"Testing ClinicalDataLoader on real MTSamples CSV: {csv_path.name}...")

    if not csv_path.exists():
        print(f"  [SKIP] Dataset file not found at {csv_path}")
        return

    # Load small sample of 5 records
    records = ClinicalDataLoader.load_mtsamples_csv(csv_path, sample_size=5)
    assert len(records) == 5, f"Expected 5 records, got {len(records)}"

    first = records[0]
    assert "doc_id" in first
    assert "category" in first
    assert "title" in first
    assert "diagnostic_summary" in first
    assert len(first["diagnostic_summary"]) > 20

    print(f"  [PASS] Successfully loaded and parsed {len(records)} real clinical records.")
    print(f"  Example parsed record ({first['category']} - {first['title']}):")
    print("  " + "-" * 50)
    for line in first["diagnostic_summary"].split("\n")[:4]:
        print(f"  | {line}")
    print("  " + "-" * 50)


def test_real_unstructured_notes():
    notes_dir = settings.DATA_LAKE_DIR / "unstructured_notes"
    print(f"Testing ClinicalDataLoader on EHR notes directory: {notes_dir.name}...")

    if not notes_dir.exists():
        print(f"  [SKIP] Notes directory not found at {notes_dir}")
        return

    records = ClinicalDataLoader.load_unstructured_notes(notes_dir, max_notes=5)
    assert len(records) > 0, "Failed to load any EHR notes"

    first = records[0]
    assert "doc_id" in first
    assert "diagnostic_summary" in first
    print(f"  [PASS] Successfully loaded {len(records)} real hospital encounter notes.")
    print(f"  Sample Note ID: {first['doc_id']}")
    print(f"  Summary Preview: {first['diagnostic_summary'][:150]}...")


if __name__ == "__main__":
    print("=== RUNNING PHASE 1 CLINICAL PARSER VERIFICATION ===")
    test_section_parsing_synthetic()
    test_real_mtsamples_loading()
    test_real_unstructured_notes()
    print("=== PHASE 1 ALL TESTS COMPLETED SUCCESSFULLY! ===")
