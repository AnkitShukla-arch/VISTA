"""Step 3 — summarise the cleaned data (summaries layer).

For every clean parquet we build a profile summary:
  structured  -> row/col counts, dtypes, nulls, numeric describe, top categories
  text        -> doc count, avg/median length, vocabulary size, top category values

A combined `phase1_summary.md` is also generated so the whole phase-one
dataset can be eyeballed from the MinIO console at a glance.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import WORK_DIR, get_logger

log = get_logger("summarize")

CLEAN_DIR = WORK_DIR / "clean"
SUMMARY_DIR = WORK_DIR / "summaries"


def _top_values(series: pd.Series, n: int = 8) -> dict:
    counts = series.value_counts().head(n)
    return {str(k): int(v) for k, v in counts.items()}


def summarize_structured(df: pd.DataFrame) -> dict:
    summary = {
        "kind": "structured",
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "columns_detail": {},
    }
    for col in df.columns:
        col_info = {
            "dtype": str(df[col].dtype),
            "nulls": int(df[col].isna().sum()),
            "distinct": int(df[col].nunique(dropna=True)),
        }
        if pd.api.types.is_numeric_dtype(df[col]):
            desc = df[col].describe()
            col_info["min"] = _safe(desc.get("min"))
            col_info["max"] = _safe(desc.get("max"))
            col_info["mean"] = _safe(desc.get("mean"))
        else:
            top = _top_values(df[col].dropna())
            if top:
                col_info["top_values"] = top
        summary["columns_detail"][col] = col_info
    return summary


def summarize_text(df: pd.DataFrame, text_col: str = "text") -> dict:
    lengths = df[text_col].str.len()
    # Approximate token counts without materialising per-word lists.
    total_tokens = int(df[text_col].str.count(r"\S+").sum()) if len(df) else 0
    # Vocabulary via capped sample so 50k-doc bundles stay cheap.
    vocab = 0
    if len(df):
        sample = df[text_col] if len(df) <= 20000 else df[text_col].sample(20000, random_state=0)
        vocab = int(sample.str.lower().str.findall(r"[a-z]+").explode().nunique())
    summary = {
        "kind": "text",
        "documents": int(len(df)),
        "avg_length": round(float(lengths.mean()), 1) if len(df) else 0,
        "median_length": float(lengths.median()) if len(df) else 0,
        "total_tokens_approx": total_tokens,
        "vocabulary_size": vocab,
    }
    for extra in ("category", "bundle_source", "source"):
        if extra in df.columns:
            summary[f"top_{extra}"] = _top_values(df[extra].dropna())
    return summary


def _safe(v):
    try:
        return round(float(v), 3)
    except (TypeError, ValueError):
        return None


def build_markdown(manifest: dict, summaries: dict) -> str:
    lines = ["# VISTA Phase 1 — Cleaned Data Summary", ""]
    total_raw = total_clean = 0
    for name, info in manifest.items():
        total_raw += info.get("rows_raw", 0)
        total_clean += info.get("rows_clean", 0)
    lines += [
        f"**Sources:** {len(manifest)}  |  **Rows raw:** {total_raw:,}  |  "
        f"**Rows clean:** {total_clean:,}  |  **Removed:** {total_raw - total_clean:,}",
        "",
        "| source | kind | raw | clean | removed |",
        "|---|---|---:|---:|---:|",
    ]
    for name, info in manifest.items():
        kind = summaries.get(name, {}).get("kind", "?")
        removed = info.get("rows_raw", 0) - info.get("rows_clean", 0)
        lines.append(f"| {name} | {kind} | {info.get('rows_raw', 0):,} | {info.get('rows_clean', 0):,} | {removed:,} |")

    lines += ["", "## Source details", ""]
    for name, s in summaries.items():
        lines.append(f"### {name}")
        if s["kind"] == "structured":
            lines.append(f"- rows: {s['rows']:,} | columns: {s['columns']}")
            for col, ci in list(s["columns_detail"].items())[:12]:
                extra = ""
                if "mean" in ci and ci["mean"] is not None:
                    extra = f", mean {ci['mean']}, min {ci['min']}, max {ci['max']}"
                elif "top_values" in ci:
                    top3 = list(ci["top_values"].items())[:3]
                    extra = ", top: " + ", ".join(f"{k} ({v})" for k, v in top3)
                lines.append(f"  - `{col}`: {ci['dtype']}, {ci['nulls']:,} nulls, {ci['distinct']:,} distinct{extra}")
        else:
            lines.append(
                f"- documents: {s['documents']:,} | avg len {s['avg_length']} | "
                f"vocab {s['vocabulary_size']:,} | ~{s['total_tokens_approx']:,} tokens"
            )
        lines.append("")
    return "\n".join(lines)


def run() -> dict:
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    clean_manifest_path = WORK_DIR / "clean" / "_manifest.json"
    if not clean_manifest_path.exists():
        raise FileNotFoundError("Run clean step first (outputs/pipeline/clean/_manifest.json missing)")
    manifest = json.loads(clean_manifest_path.read_text(encoding="utf-8"))

    summaries = {}
    for parquet in sorted(CLEAN_DIR.glob("*.parquet")):
        name = parquet.stem
        df = pd.read_parquet(parquet)
        if "text" in df.columns:
            summaries[name] = summarize_text(df)
        else:
            summaries[name] = summarize_structured(df)
        (SUMMARY_DIR / f"{name}.json").write_text(json.dumps(summaries[name], indent=2), encoding="utf-8")

    md = build_markdown(manifest, summaries)
    (SUMMARY_DIR / "phase1_summary.md").write_text(md, encoding="utf-8")
    log.info("Wrote %d summaries + phase1_summary.md", len(summaries))
    return summaries


if __name__ == "__main__":
    run()
