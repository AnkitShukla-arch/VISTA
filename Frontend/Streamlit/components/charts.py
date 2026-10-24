"""
Plotly chart builders for the VISTA NLP Dashboard.
"""
from typing import Dict, List, Any, Optional
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# Muted, sober categorical palette for boxes
BOX_COLORS = px.colors.qualitative.Safe


def cluster_scatter(
    projection: np.ndarray,
    labels: np.ndarray,
    titles: List[str],
    categories: List[str],
    highlight_box: Optional[int] = None,
    height: int = 520,
) -> "go.Figure":
    """2-D PCA scatter of the document space, colored by semantic box."""
    df = {
        "PC1": projection[:, 0],
        "PC2": projection[:, 1],
        "Box": [f"Box #{l}" for l in labels],
        "Title": titles,
        "Specialty": categories,
    }
    fig = px.scatter(
        df,
        x="PC1",
        y="PC2",
        color="Box",
        hover_data={"Title": True, "Specialty": True, "PC1": False, "PC2": False},
        color_discrete_sequence=BOX_COLORS,
        template="plotly_white",
        height=height,
    )
    fig.update_traces(marker=dict(size=6, opacity=0.75, line=dict(width=0)))
    if highlight_box is not None:
        # Dim every trace except the highlighted box
        for trace in fig.data:
            if trace.name != f"Box #{highlight_box}":
                trace.marker.opacity = 0.12
    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", y=-0.12, title_text=""),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def box_size_bar(box_summaries: List[Dict[str, Any]], height: int = 420) -> "go.Figure":
    """Document count per semantic box, sorted descending."""
    summaries = sorted(box_summaries, key=lambda s: s["size"], reverse=True)
    fig = go.Figure(
        go.Bar(
            x=[f"#{s['box_id']}" for s in summaries],
            y=[s["size"] for s in summaries],
            text=[s["size"] for s in summaries],
            textposition="outside",
            marker_color=[BOX_COLORS[i % len(BOX_COLORS)] for i in range(len(summaries))],
            customdata=[s.get("label", "") for s in summaries],
            hovertemplate="Box #%{x}<br>%{customdata}<br>%{y} docs<extra></extra>",
        )
    )
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_title="Semantic Box",
        yaxis_title="Documents",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def k_sweep_chart(k_sweep: Dict[str, Any], height: int = 380) -> "go.Figure":
    """Silhouette score vs K from the optimal-K sweep."""
    scores = k_sweep.get("scores", [])
    ks = [s[0] for s in scores]
    sils = [s[1] for s in scores]
    best_k = k_sweep.get("best_k")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=ks,
            y=sils,
            mode="lines+markers",
            line=dict(color="#0f766e", width=2),
            marker=dict(size=7),
            name="Silhouette",
        )
    )
    if best_k in ks:
        best_sil = sils[ks.index(best_k)]
        fig.add_trace(
            go.Scatter(
                x=[best_k],
                y=[best_sil],
                mode="markers+text",
                marker=dict(size=14, color="#c2410c", symbol="star"),
                text=[f"K={best_k}"],
                textposition="top center",
                name="Selected K",
            )
        )
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        font=dict(family="Inter, system-ui, sans-serif", size=12, color="#64748b"),
        xaxis_title="K (number of semantic boxes)",
        yaxis_title="Mean Silhouette Score",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def similarity_heatmap(
    similarity_matrix: np.ndarray,
    sample: int = 40,
    seed: int = 42,
    height: int = 560,
) -> "go.Figure":
    """Sampled pairwise cosine-similarity heatmap."""
    rng = np.random.RandomState(seed)
    N = similarity_matrix.shape[0]
    idx = rng.choice(N, size=min(sample, N), replace=False)
    sub = similarity_matrix[np.ix_(idx, idx)]

    fig = go.Figure(
        go.Heatmap(
            z=sub,
            colorscale="RdBu_r",
            zmid=0.0,
            showscale=True,
            hovertemplate="doc %{y} vs doc %{x}<br>cosine=%{z:.3f}<extra></extra>",
        )
    )
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_title="Document index (sampled)",
        yaxis_title="Document index (sampled)",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def category_by_box_sunburst(
    labels: np.ndarray,
    categories: List[str],
    box_summaries: List[Dict[str, Any]],
    height: int = 560,
) -> "go.Figure":
    """Hierarchical view: semantic box -> medical specialty distribution."""
    id_to_label = {s["box_id"]: s.get("label", f"Box {s['box_id']}") for s in box_summaries}
    parents, ids, values, names = [], [], [], []
    agg: Dict[str, Dict[str, int]] = {}
    for l, c in zip(labels, categories):
        label = id_to_label.get(int(l), f"Box {int(l)}")
        agg.setdefault(label, {}).setdefault(c, 0)
        agg[label][c] += 1

    for box_label, cat_counts in agg.items():
        parents.append("")
        ids.append(box_label)
        values.append(sum(cat_counts.values()))
        names.append(box_label)
        for cat, n in sorted(cat_counts.items(), key=lambda kv: -kv[1])[:6]:
            child_id = f"{box_label} / {cat}"
            parents.append(box_label)
            ids.append(child_id)
            values.append(n)
            names.append(cat)

    fig = go.Figure(
        go.Sunburst(
            ids=ids,
            labels=names,
            parents=parents,
            values=values,
            branchvalues="total",
            maxdepth=2,
        )
    )
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig
