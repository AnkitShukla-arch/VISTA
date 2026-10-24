"""
VISTA: Vector Intelligent Semantic Search Text Analysis
NLP Dashboard — semantic search over the box-clustered medical data warehouse.

Pages:
  1. Semantic Search    — natural-language query -> FAISS box match -> priority-ranked docs
  2. Box Explorer       — K-Means semantic boxes: labels, keywords, 2-D PCA map
  3. Cluster Analytics  — silhouette / purity / K-sweep / similarity structure
  4. Document Browser   — full corpus table with per-box filtering

Run:
    streamlit run Frontend/Streamlit/app.py
"""
import sys
import time
from pathlib import Path
from typing import Dict, List, Any

import streamlit as st
import pandas as pd

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import settings
from Frontend.Streamlit.components import data_loader
from Frontend.Streamlit.components import charts
from Frontend.Streamlit.components import theme

st.set_page_config(
    page_title="VISTA — Medical Semantic Search",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

theme.apply_theme()


# ----------------------------------------------------------------------
# Shared UI helpers
# ----------------------------------------------------------------------
def render_sidebar() -> str:
    with st.sidebar:
        theme.brand_block()

        page = st.radio(
            "Navigation",
            ["🔍 Semantic Search", "📦 Box Explorer", "📊 Cluster Analytics", "📁 Document Browser"],
            label_visibility="collapsed",
        )

        artifacts = data_loader.check_artifacts()
        theme.section("⚙️ System Status")
        st.markdown(
            theme.status_value_row("Model", settings.EMBEDDING_MODEL_NAME)
            + theme.status_value_row("Dimension", "384-D")
            + theme.status_row("Embeddings", artifacts["processed"])
            + theme.status_row("FAISS Box Index", artifacts["clustering"])
            + theme.status_row("Similarity Matrix", artifacts["similarity"]),
            unsafe_allow_html=True,
        )

        if artifacts["processed"] and artifacts["clustering"]:
            cluster = data_loader.load_cluster_data()
            metrics = cluster.get("metrics", {})
            if metrics:
                theme.section("📦 Cluster Health")
                theme.side_stat("Semantic Boxes", metrics.get("n_clusters", "—"))
                theme.side_stat("Silhouette Score", metrics.get("silhouette_score", "—"))
        return page


def render_missing_artifacts():
    st.error("## ⚠️ Pipeline artifacts not found")
    st.markdown(
        """
        The dashboard needs the embedding + clustering bundles. Build them with:

        ```bash
        # 1) Vectorize clinical reports (Phase 2/3)
        python Backend/Embeddings/pipeline.py --sample-size 1000

        # 2) K-Means box clustering + FAISS box index (Phase 4)
        python Backend/Clustering/pipeline.py --auto-k
        ```
        """
    )
    st.stop()


# ----------------------------------------------------------------------
# Page 1: Semantic Search
# ----------------------------------------------------------------------
def page_search():
    sample_queries = [
        "Heart attack with elevated troponin",
        "Knee pain after a sports injury",
        "Pediatric asthma exacerbation",
        "Severe migraine with aura",
        "Prenatal ultrasound findings",
    ]
    st.markdown(
        '<div class="search-intro"><div class="eyebrow">VISTA · CLINICAL INTELLIGENCE</div>'
        '<h1>Search medical reports<br>by meaning.</h1>'
        '<p>Find the right clinical context across your reports. Describe what you’re looking for in plain language.</p></div>',
        unsafe_allow_html=True,
    )

    if "vista_query" not in st.session_state:
        st.session_state.vista_query = ""
    if "vista_search" not in st.session_state:
        st.session_state.vista_search = None
    if "vista_recent" not in st.session_state:
        st.session_state.vista_recent = []

    with st.form("clinical_search", clear_on_submit=False):
        query = st.text_input(
            "Describe a clinical case",
            key="vista_query",
            placeholder="e.g. chest pain with elevated cardiac enzymes",
            label_visibility="collapsed",
        )
        c1, c2, c3 = st.columns([1, 1, 5])
        with c1:
            top_boxes = st.selectbox("Boxes", [1, 2, 3, 4], index=1, label_visibility="collapsed")
        with c2:
            top_docs = st.selectbox("Results per box", [3, 5, 8, 10], index=1, label_visibility="collapsed")
        with c3:
            run = st.form_submit_button("Search reports  →", type="primary", use_container_width=True)

    if not st.session_state.vista_search:
        st.markdown('<div class="suggestion-label">TRY A SEARCH</div>', unsafe_allow_html=True)
        chip_cols = st.columns(len(sample_queries))
        for col, sample in zip(chip_cols, sample_queries):
            with col:
                if st.button(sample, key=f"suggest_{sample}", use_container_width=True):
                    st.session_state.vista_query = sample
                    st.session_state.vista_run_suggestion = True
                    st.rerun()

    if run or st.session_state.pop("vista_run_suggestion", False):
        active_query = st.session_state.vista_query.strip()
        if not active_query:
            st.warning("Enter a clinical phrase to search the reports.")
            return
        with st.spinner("Finding related clinical reports…"):
            engine = data_loader.load_engine()
            started = time.perf_counter()
            result = engine.search(active_query, top_boxes=top_boxes, top_docs_per_box=top_docs)
            elapsed = time.perf_counter() - started
        st.session_state.vista_search = {"query": active_query, "result": result, "elapsed": elapsed}
        st.session_state.vista_recent = [active_query] + [q for q in st.session_state.vista_recent if q != active_query]
        st.session_state.vista_recent = st.session_state.vista_recent[:5]

    search_state = st.session_state.vista_search
    if not search_state:
        st.markdown(
            '<div class="search-footnote">Meaning-based retrieval · 1,000 clinical reports · Private workspace</div>',
            unsafe_allow_html=True,
        )
        return

    result, elapsed = search_state["result"], search_state["elapsed"]
    status = "success" if elapsed < 2 else "warning"
    if status == "success":
        st.success(f"Found in {elapsed:.2f}s · within the 2 second retrieval target")
    else:
        st.warning(f"Found in {elapsed:.2f}s · above the 2 second retrieval target")

    if not result.get("boxes"):
        st.info("No reports matched that description. Try a broader clinical concept.")
        return

    docs = [doc for box in result["boxes"] for doc in box.get("results", [])]
    if not docs:
        st.info("No reports matched that description. Try another query.")
        return

    left, right = st.columns([1.5, 1], gap="large")
    with left:
        st.markdown(f"#### Results <span class='result-count'>{len(docs)} reports</span>", unsafe_allow_html=True)
        st.caption(f"Closest clinical concepts for “{search_state['query']}”")
        theme.section("Matched boxes")
        for box in result["boxes"]:
            with st.container(border=True):
                bh, bs = st.columns([4, 1])
                bh.markdown(f"**{box.get('label', 'Clinical box')}**")
                bs.markdown(f"<div class='score-badge'>{box.get('similarity_score', 0):.0%} match</div>", unsafe_allow_html=True)
                if box.get("keywords"):
                    theme.pills(box["keywords"][:5], alt=True)
                st.progress(max(0.0, min(1.0, float(box.get("similarity_score", 0)))))
        theme.section("Ranked reports")
        doc_labels = {
            d.get("doc_id", str(i)): f"{d.get('title') or d.get('doc_id', 'Clinical report')} · {d.get('category', 'General') }"
            for i, d in enumerate(docs)
        }
        selected_id = st.radio(
            "Select a report to preview",
            options=list(doc_labels),
            format_func=lambda doc_id: doc_labels[doc_id],
            label_visibility="collapsed",
            key=f"selected_result_{search_state['query']}",
        )
        for rank, doc in enumerate(docs, 1):
            with st.container(border=True):
                st.markdown(f"**{rank:02d} · {doc.get('title') or 'Clinical report'}**")
                st.caption(f"{doc.get('category', 'General')}  ·  {doc.get('doc_id', '—')}")
                st.write(data_loader.get_doc_raw_text(doc)[:240].replace("\n", " ") + "…")
                sim, pri = st.columns(2)
                sim.metric("Semantic similarity", f"{doc.get('similarity_score', 0):.0%}")
                pri.metric("Priority score", f"{doc.get('priority_score', 0):.2f}")

    with right:
        selected_doc = next((d for d in docs if d.get("doc_id") == selected_id), docs[0])
        st.markdown("#### Report preview")
        with st.container(border=True):
            st.markdown(f"### {selected_doc.get('title') or 'Clinical report'}")
            st.caption(f"{selected_doc.get('doc_id', '—')}  ·  {selected_doc.get('category', 'General')}")
            st.divider()
            st.markdown("**Clinical note**")
            st.write(data_loader.get_doc_raw_text(selected_doc))
            st.divider()
            st.markdown("**Retrieval details**")
            st.write(f"Semantic similarity · {selected_doc.get('similarity_score', 0):.3f}")
            st.write(f"Priority score · {selected_doc.get('priority_score', 0):.3f}")
            st.write(f"Semantic box · #{selected_doc.get('box_id', '—')}")
        if st.session_state.vista_recent:
            with st.expander("Recent searches"):
                for previous in st.session_state.vista_recent:
                    st.write(f"· {previous}")


# ----------------------------------------------------------------------
# Page 2: Box Explorer
# ----------------------------------------------------------------------
def page_boxes():
    theme.hero(
        "📦",
        "Semantic Box Explorer",
        "K-Means clusters of 384-D clinical embeddings — VISTA's storage abstraction",
    )

    embeddings, metadata = data_loader.load_embeddings()
    cluster = data_loader.load_cluster_data()
    labels = cluster.get("labels")
    projection = cluster.get("projection")
    summaries = cluster.get("box_summaries", [])

    if labels is None or not summaries:
        st.error("Cluster artifacts missing. Run `python Backend/Clustering/pipeline.py --auto-k`.")
        return

    # PCA map + selected box detail side by side
    col_map, col_detail = st.columns([3, 2])

    with col_map:
        if projection is not None:
            st.plotly_chart(
                charts.cluster_scatter(
                    projection,
                    labels,
                    [m.get("title", "") for m in metadata],
                    [m.get("category", "") for m in metadata],
                    height=480,
                ),
                width='stretch',
            )
        else:
            st.info("PCA projection not found — run the Phase 4 pipeline to generate it.")

    with col_detail:
        theme.section("📂 Box directory")
        df = pd.DataFrame(
            [
                {
                    "Box": f"#{s['box_id']}",
                    "Label": s.get("label", "—")[:60],
                    "Docs": s["size"],
                    "Top concepts": ", ".join(s.get("keywords", [])[:4]),
                }
                for s in summaries
            ]
        )
        selection = st.dataframe(
            df, width='stretch', hide_index=True,
            on_select="rerun", selection_mode="single-row",
        )
        selected_rows = selection.get("selection", {}).get("rows", [])
        if selected_rows:
            sel = summaries[selected_rows[0]]
            st.markdown(f"### Box #{sel['box_id']} — {sel.get('label', '')}")
            st.caption("Keywords: " + ", ".join(sel.get("keywords", [])))
            member_ids = set(sel.get("doc_ids", []))
            member_docs = [m for m in metadata if m.get("doc_id") in member_ids]
            if member_docs:
                mdf = pd.DataFrame(
                    [
                        {
                            "Doc ID": m.get("doc_id"),
                            "Specialty": m.get("category", "—"),
                            "Title": (m.get("title") or "—")[:70],
                        }
                        for m in member_docs
                    ]
                )
                st.dataframe(mdf, width='stretch', hide_index=True, height=260)
                chosen = st.selectbox(
                    "Preview document",
                    member_docs,
                    format_func=lambda m: f"[{m.get('category', '—')}] {(m.get('title') or m.get('doc_id', ''))[:60]}",
                )
                if chosen:
                    preview = data_loader.get_doc_raw_text(chosen)
                    st.text_area("Text", preview[:1500], height=220, key="box_preview")

    st.divider()
    st.plotly_chart(charts.box_size_bar(summaries), width='stretch')


# ----------------------------------------------------------------------
# Page 3: Cluster Analytics
# ----------------------------------------------------------------------
def page_analytics():
    theme.hero(
        "📊",
        "Cluster Analytics",
        "How well did K-Means partition the clinical embedding space?",
    )

    cluster = data_loader.load_cluster_data()
    metrics = cluster.get("metrics", {})
    if not metrics:
        st.error("Cluster metrics missing. Run `python Backend/Clustering/pipeline.py --auto-k`.")
        return

    # Headline metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Silhouette Score", metrics.get("silhouette_score", "—"), help="[-1, 1]; higher = better-separated boxes")
    c2.metric("Davies-Bouldin", metrics.get("davies_bouldin_score", "—"), help="Lower is better")
    c3.metric("Calinski-Harabasz", metrics.get("calinski_harabasz_score", "—"), help="Higher is better")
    c4.metric("Specialty Purity", metrics.get("specialty_purity", "—"), help="Share of docs in their box's majority specialty")
    c5.metric("Boxes × Docs", f"{metrics.get('n_clusters', '—')} × {metrics.get('documents', '—')}")

    st.divider()
    left, right = st.columns(2)

    with left:
        if cluster.get("k_sweep"):
            st.plotly_chart(charts.k_sweep_chart(cluster["k_sweep"]), width='stretch')
        else:
            st.info("K-sweep not available — re-run pipeline with `--auto-k` to generate it.")

    with right:
        summaries = cluster.get("box_summaries", [])
        if summaries:
            st.plotly_chart(charts.box_size_bar(summaries, height=380), width='stretch')

    # Box → specialty composition
    if cluster.get("labels") is not None:
        embeddings, metadata = data_loader.load_embeddings()
        theme.section("Semantic Box ↔ Medical Specialty Composition")
        st.plotly_chart(
            charts.category_by_box_sunburst(
                cluster["labels"],
                [m.get("category", "Unknown") for m in metadata],
                cluster.get("box_summaries", []),
            ),
            width='stretch',
        )

    # Similarity matrix structure (Phase 3 handoff)
    sim = data_loader.load_similarity_matrix()
    if sim is not None:
        theme.section("Pairwise Cosine Similarity Structure (Phase 3)")
        st.caption(f"Full matrix shape {sim.shape} — showing a 40×40 random sample")
        st.plotly_chart(charts.similarity_heatmap(sim), width='stretch')

        manifest_path = Path(settings.DATA_PROCESSED_DIR) / "handoff_manifest.json"
        if manifest_path.exists():
            import json
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            sep = manifest.get("metrics", {})
            if sep:
                c1, c2, c3 = st.columns(3)
                c1.metric("Intra-Specialty Sim", sep.get("intra_specialty_mean_similarity", "—"))
                c2.metric("Inter-Specialty Sim", sep.get("inter_specialty_mean_similarity", "—"))
                c3.metric("Separability Ratio", f"{sep.get('separability_ratio', '—')}×")


# ----------------------------------------------------------------------
# Page 4: Document Browser
# ----------------------------------------------------------------------
def page_documents():
    theme.hero(
        "📁",
        "Document Browser",
        f"Corpus stored in {settings.DATA_PROCESSED_DIR} — filter, search and preview every embedded report",
    )

    embeddings, metadata = data_loader.load_embeddings()
    cluster = data_loader.load_cluster_data()
    labels = cluster.get("labels")
    summaries = {s["box_id"]: s for s in cluster.get("box_summaries", [])}

    df = pd.DataFrame(metadata)
    if labels is not None:
        df["box_id"] = labels
        df["box_label"] = [summaries.get(int(b), {}).get("label", f"Box #{int(b)}") for b in labels]

    # Filters
    c1, c2, c3 = st.columns([1, 2, 3])
    with c1:
        box_options = ["All boxes"] + sorted(
            [f"#{b}" for b in df["box_id"].unique()] if "box_id" in df else []
        )
        box_filter = st.selectbox("Semantic box", box_options)
    with c2:
        cats = ["All specialties"] + sorted(df.get("category", pd.Series(dtype=str)).dropna().unique().tolist())
        cat_filter = st.selectbox("Specialty", cats)
    with c3:
        text_filter = st.text_input("Filter by title / doc id", "")

    view = df
    if box_filter != "All boxes" and "box_id" in view:
        view = view[view["box_id"] == int(box_filter[1:])]
    if cat_filter != "All specialties" and "category" in view:
        view = view[view["category"] == cat_filter]
    if text_filter:
        mask = (
            view.get("title", "").astype(str).str.contains(text_filter, case=False, na=False)
            | view.get("doc_id", "").astype(str).str.contains(text_filter, case=False, na=False)
        )
        view = view[mask]

    st.caption(f"{len(view)} of {len(df)} documents")
    st.dataframe(
        view[["doc_id", "category", "title"] + (["box_id"] if "box_id" in view else [])].head(300),
        width='stretch',
        hide_index=True,
        height=420,
    )

    # Detail viewer
    st.divider()
    doc_id = st.selectbox("Open document", view["doc_id"].head(200), index=None, placeholder="Select a doc id...")
    if doc_id:
        doc = next((m for m in metadata if m.get("doc_id") == doc_id), None)
        if doc:
            box_id = int(doc["box_id"]) if "box_id" in doc and pd.notna(doc["box_id"]) else None
            st.markdown(
                f"**{doc.get('title', '—')}** · `{doc.get('doc_id')}` · "
                f"**{doc.get('category', '—')}**"
                + (f" · Box #{box_id} ({summaries.get(box_id, {}).get('label', '')})" if box_id is not None else "")
            )
            st.text_area("Full text", data_loader.get_doc_raw_text(doc), height=380, key="doc_browser_text")


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    page = render_sidebar()

    artifacts = data_loader.check_artifacts()
    if not (artifacts["processed"] and artifacts["clustering"]):
        render_missing_artifacts()

    if page == "🔍 Semantic Search":
        page_search()
    elif page == "📦 Box Explorer":
        page_boxes()
    elif page == "📊 Cluster Analytics":
        page_analytics()
    else:
        page_documents()

    st.sidebar.divider()
    st.sidebar.markdown(
        f'<div class="vista-footer">VISTA v{settings.PROJECT_VERSION} · '
        'box-clustered semantic warehouse</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
