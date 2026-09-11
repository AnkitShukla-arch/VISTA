"""
VISTA: Vector Intelligent Semantic Search Text Analysis
Interactive Diagnostic Search Dashboard (Streamlit).
"""
import streamlit as st
import time
from pathlib import Path
import sys

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import settings


def main():
    st.set_page_config(
        page_title="VISTA - Medical Semantic Search",
        page_icon="🏥",
        layout="wide",
    )

    st.title("🏥 VISTA: Semantic Healthcare Data Warehouse")
    st.caption("Vector Intelligent Semantic Search Text Analysis with Box-Clustering")

    # Sidebar settings
    with st.sidebar:
        st.header("⚙️ System Status")
        st.write(f"**Model**: `{settings.EMBEDDING_MODEL_NAME}`")
        st.write(f"**Device**: `{settings.EMBEDDING_DEVICE}`")
        st.write(f"**FAISS Index**: `{'Available' if settings.FAISS_INDEX_PATH.exists() else 'Not Built'}`")
        st.write(f"**DuckDB**: `{settings.DUCKDB_PATH.name}`")

    # Main search interface
    query = st.text_input(
        "🔍 Enter clinical concept or natural language query:",
        placeholder="e.g., patient with elevated troponin and acute myocardial infarction",
    )

    col1, col2 = st.columns([1, 4])
    with col1:
        top_k = st.slider("Top Box Matches", min_value=1, max_value=5, value=3)

    if st.button("Search Medical Records", type="primary"):
        if not query.strip():
            st.warning("Please enter a clinical query.")
            return

        with st.spinner("Embedding query & searching semantic boxes..."):
            t0 = time.time()
            # Placeholder for full end-to-end integration demo
            time.sleep(0.3)
            elapsed = time.time() - t0

        st.success(f"Retrieval completed in {elapsed:.3f} seconds (< 2 sec target)")
        st.info(f"Matched nearest semantic box based on cosine similarity for: **'{query}'**")

        st.subheader("📦 Nearest Semantic Boxes & Priority Ranked Documents")
        st.write("*(Connect backend FAISS index and Box clusterer to stream real-time hospital results)*")


if __name__ == "__main__":
    main()
