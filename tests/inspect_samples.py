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
    
    # Select 3 contrasting records
    target_ids = ["mtsamples-3", "mtsamples-7", "mtsamples-14"]
    for tid in target_ids:
        match = df[df["doc_id"] == tid]
        if match.empty:
            continue
        r = match.iloc[0]
        print("=" * 70)
        print(f"ID       : {r['doc_id']}")
        print(f"CATEGORY : {r['category']}")
        print(f"TITLE    : {r['title'].strip()}")
        print("-" * 70)
        summary = ClinicalSectionParser.build_diagnostic_summary(
            r["text"], title=r["title"], category=r["category"]
        )
        print("DIAGNOSTIC SUMMARY:")
        print(summary[:400] + "...\n")

if __name__ == "__main__":
    main()
