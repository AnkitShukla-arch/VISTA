import sys
from pathlib import Path
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import settings
from Backend.Embeddings.clinical_parser import ClinicalSectionParser

def main():
    df = pd.read_csv(settings.MTSAMPLES_CSV)
    
    # Let's inspect mtsamples-0 (Allergy/Immunology) and mtsamples-3 (Cardiovascular)
    targets = ["mtsamples-0", "mtsamples-3"]
    for tid in targets:
        match = df[df["doc_id"] == tid]
        if match.empty:
            continue
        row = match.iloc[0]
        
        print(f"============================================================")
        print(f"DOCUMENT ID : {row['doc_id']}")
        print(f"SPECIALTY   : {row['category']}")
        print(f"TITLE       : {row['title']}")
        print(f"============================================================")
        
        print("\n[1] RAW TEXT EXCERPT (Notice long, disorganized text):")
        print(row["text"][:350] + "...\n")
        
        sections = ClinicalSectionParser.parse_sections(row["text"])
        print("[2] DETECTED CLINICAL SECTIONS:")
        for k, v in sections.items():
            print(f"  * {k:15s} -> {v[:80]}...")
            
        summary = ClinicalSectionParser.build_diagnostic_summary(
            text=row["text"],
            title=row["title"],
            category=row["category"]
        )
        print("\n[3] HIGH-DENSITY SUMMARY CREATED FOR EMBEDDER (Phase 2 Input):")
        print(summary)
        print("\n")

if __name__ == "__main__":
    main()
