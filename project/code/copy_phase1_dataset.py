import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = PROJECT_ROOT / "data" / "raw" / "dataset"
DEST_DIR_1 = PROJECT_ROOT / "data" / "processed" / "phase1_dataset"
DEST_DIR_2 = SOURCE_DIR / "phase1"
SELECTION_TXT = PROJECT_ROOT / "data" / "processed" / "phase1_selection.txt"

def copy_subset():
    print(f"Reading selection from {SELECTION_TXT}...")
    with open(SELECTION_TXT, "r") as f:
        rel_paths = [line.strip() for line in f if line.strip()]
        
    print(f"Found {len(rel_paths)} files to copy.")
    
    for dest in [DEST_DIR_1, DEST_DIR_2]:
        dest.mkdir(parents=True, exist_ok=True)
        copied = 0
        total_size = 0
        for rel in rel_paths:
            src_fp = SOURCE_DIR / rel
            dst_fp = dest / rel
            dst_fp.parent.mkdir(parents=True, exist_ok=True)
            if src_fp.exists():
                shutil.copy2(src_fp, dst_fp)
                copied += 1
                total_size += os.path.getsize(src_fp)
        print(f"Copied {copied} files ({total_size / (1024**2):.2f} MB / {total_size / 1000000000:.3f} GB) to {dest}.")

if __name__ == "__main__":
    copy_subset()
