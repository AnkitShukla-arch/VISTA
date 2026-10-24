"""
VISTA Dashboard Visual Theme.

A clean, sober, editorial interface: white surfaces, hairline borders,
generous whitespace and a single restrained teal accent. Injected as
global CSS over Streamlit plus a few small HTML helpers (hero, section
headers, chips, status rows) that pages compose with plain widgets.
"""
import streamlit as st

# Single restrained accent
ACCENT = "#0f766e"

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
    --vista-accent: #0f766e;
    --vista-accent-soft: #f0fdfa;
    --vista-text: #1e293b;
    --vista-strong: #0f172a;
    --vista-muted: #64748b;
    --vista-line: #e2e8f0;
    --vista-bg: #f8fafc;
    --vista-card: #ffffff;
}

/* ---------- App shell ---------- */
html, body, [class*="css"] {
    font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
    color: var(--vista-text);
}
.stApp {
    background: var(--vista-bg);
    color: var(--vista-text);
}
h1, h2, h3 { letter-spacing: -0.015em; }
h1, h2, h3, h4 { color: var(--vista-strong) !important; }
a { color: var(--vista-accent) !important; }
code {
    font-family: 'JetBrains Mono', ui-monospace, monospace !important;
    background: #f1f5f9 !important;
    color: #334155 !important;
    border-radius: 5px;
    padding: 1px 5px;
    font-size: 0.85em;
}
pre code { font-size: 0.85rem; background: #f1f5f9 !important; }
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
.stTabs [data-baseweb="tab-list"] { gap: 0; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {
    background: var(--vista-card);
    border-right: 1px solid var(--vista-line);
}
.vista-brand {
    display: flex;
    align-items: center;
    gap: 11px;
    padding: 16px 2px 12px 2px;
    border-bottom: 1px solid var(--vista-line);
    margin-bottom: 12px;
}
.vista-brand-logo {
    width: 38px; height: 38px; flex: 0 0 38px;
    display: flex; align-items: center; justify-content: center;
    color: #ffffff; font-weight: 700; font-size: 1.05rem;
    border-radius: 9px;
    background: var(--vista-accent);
    letter-spacing: 0.02em;
}
.vista-brand-name {
    color: var(--vista-strong);
    font-size: 1.3rem;
    font-weight: 700;
    line-height: 1.1;
    letter-spacing: -0.02em;
}
.vista-brand-sub {
    color: var(--vista-muted);
    font-size: 0.74rem;
    margin-top: 2px;
    line-height: 1.35;
}

/* nav pills */
[data-testid="stSidebar"] .stRadio [role="radiogroup"] > label {
    padding: 9px 12px !important;
    border-radius: 9px;
    color: var(--vista-text);
    font-weight: 500 !important;
    font-size: 0.92rem !important;
    transition: background 0.12s ease;
}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] > label:hover {
    background: #f1f5f9;
}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] > label[data-checked="true"] {
    background: var(--vista-accent-soft) !important;
    color: var(--vista-accent) !important;
    border-left: 2px solid var(--vista-accent) !important;
    border-radius: 9px;
}

/* sidebar status rows */
.vista-status {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    font-size: 0.84rem;
    border-bottom: 1px solid #f1f5f9;
}
.vista-status:last-of-type { border-bottom: none; }
.vista-status .k { color: var(--vista-muted); }
.vista-status .ok { color: #15803d; font-weight: 600; }
.vista-status .off { color: #b91c1c; font-weight: 600; }
.vista-status .mono {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.78rem;
    font-weight: 600;
}
.vista-side-stat {
    padding: 14px 16px;
    margin: 10px 0;
    border-radius: 11px;
    background: var(--vista-card);
    border: 1px solid var(--vista-line);
}
.vista-side-stat .cap { color: var(--vista-muted); font-size: 0.76rem; font-weight: 600; margin-bottom: 3px; }
.vista-side-stat .val {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--vista-strong);
}

/* sidebar footer */
.vista-footer { color: var(--vista-muted); font-size: 0.74rem; padding-top: 2px; }

/* ---------- Hero banner ---------- */
.vista-hero {
    background: var(--vista-card);
    border: 1px solid var(--vista-line);
    border-radius: 14px;
    padding: 22px 28px 20px 28px;
    margin: 4px 0 24px 0;
}
.vista-hero .icon { font-size: 1.35rem; margin-right: 10px; }
.vista-hero h1 {
    display: flex;
    align-items: center;
    font-weight: 700 !important;
    font-size: 1.65rem !important;
    margin: 0 !important;
    padding: 0;
}
.vista-hero .sub { color: var(--vista-muted); font-size: 0.93rem; margin: 7px 0 0 0; }
.vista-hero .badge {
    display: inline-block;
    margin-left: 12px;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.7rem;
    font-weight: 600;
    vertical-align: middle;
    background: var(--vista-accent-soft);
    border: 1px solid #99f6e4;
    color: var(--vista-accent);
    -webkit-text-fill-color: var(--vista-accent);
    letter-spacing: 0.01em;
}

/* ---------- Section headers ---------- */
.vista-section {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 20px 0 10px 0;
    font-size: 0.98rem;
    font-weight: 700;
    color: var(--vista-strong);
    text-transform: none;
}
.vista-section::after {
    content: "";
    flex: 1;
    height: 1px;
    background: var(--vista-line);
}

/* ---------- Cards & widgets ---------- */
[data-testid="stMetric"] {
    background: var(--vista-card);
    border: 1px solid var(--vista-line);
    border-radius: 12px;
    padding: 14px 18px 10px 18px;
}
[data-testid="stMetricLabel"] p { color: var(--vista-muted) !important; font-weight: 600; font-size: 0.8rem; }
[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    color: var(--vista-strong);
    font-weight: 600;
}

.stButton > button {
    background: var(--vista-accent) !important;
    color: #ffffff !important;
    border: none;
    border-radius: 9px;
    font-weight: 600;
    font-size: 0.92rem;
    padding: 8px 26px;
    transition: background 0.12s ease;
}
.stButton > button:hover { background: #115e59 !important; }
.stButton > button[kind="secondary"] { background: #f1f5f9 !important; color: var(--vista-strong) !important; }

.stTextInput input, .stTextArea textarea {
    border-radius: 9px;
    border-color: var(--vista-line);
    background: var(--vista-card);
}
.stTextInput input:focus {
    border-color: var(--vista-accent) !important;
    box-shadow: none !important;
}
[data-baseweb="select"] > div { border-radius: 9px; border-color: var(--vista-line); background: var(--vista-card); }

[data-testid="stExpander"] {
    background: var(--vista-card);
    border: 1px solid var(--vista-line) !important;
    border-radius: 12px !important;
    overflow: hidden;
    margin-bottom: 12px;
}
[data-testid="stExpander"] summary {
    padding: 11px 16px;
    font-weight: 600;
    color: var(--vista-strong);
    transition: background 0.12s ease;
}
[data-testid="stExpander"] summary:hover { background: #f8fafc; }

[data-testid="stDataFrame"] {
    border: 1px solid var(--vista-line);
    border-radius: 12px;
    overflow: hidden;
}

/* ---------- Chips ---------- */
.vista-pill {
    display: inline-block;
    padding: 3px 11px;
    margin: 3px 5px 3px 0;
    border-radius: 999px;
    font-size: 0.76rem;
    font-weight: 500;
    background: #f1f5f9;
    border: 1px solid var(--vista-line);
    color: #475569;
}
.vista-pill.alt {
    background: var(--vista-accent-soft);
    border-color: #99f6e4;
    color: var(--vista-accent);
}
.vista-tag { color: var(--vista-muted); font-size: 0.82rem; font-weight: 600; }

/* Search workspace */
[data-testid="stMainBlockContainer"] { padding-top: 2.2rem; max-width: 1480px; }
.search-intro { max-width: 720px; margin: 5.5rem auto 1.8rem; text-align: center; }
.search-intro .eyebrow { color: var(--vista-accent); font-size: .72rem; font-weight: 700; letter-spacing: .14em; margin-bottom: 1.15rem; }
.search-intro h1 { font-size: clamp(2.4rem, 5vw, 3.75rem); line-height: 1.08; letter-spacing: -.055em; font-weight: 600; margin: 0; }
.search-intro p { max-width: 600px; margin: 1rem auto 0; color: var(--vista-muted); font-size: 1.02rem; line-height: 1.7; }
.search-footnote { text-align: center; color: #94a3b8; font-size: .78rem; margin-top: 2.4rem; }
.suggestion-label { color: #94a3b8; font-size: .68rem; font-weight: 700; letter-spacing: .12em; text-align: center; margin: 1.4rem 0 .65rem; }
.result-count { color: var(--vista-muted); font-size: .78rem; font-weight: 500; margin-left: .45rem; }
.score-badge { color: var(--vista-accent); text-align: right; font-weight: 700; font-size: .82rem; padding-top: .2rem; }
[data-testid="stVerticalBlockBorderWrapper"] { border-color: var(--vista-line) !important; border-radius: 12px !important; }
[data-testid="stProgressBar"] > div > div { background-color: var(--vista-accent); }
[data-testid="stRadio"] [role="radiogroup"] { gap: .35rem; }
[data-testid="stRadio"] label { padding: .5rem .65rem; border: 1px solid var(--vista-line); border-radius: 9px; background: white; }
[data-testid="stRadio"] label:hover { border-color: #99f6e4; background: #f0fdfa; }
.stButton > button { min-height: 2.65rem; }
.stTextInput input { min-height: 3.1rem; font-size: 1rem; }
.stForm { border: 1px solid var(--vista-line); border-radius: 14px; padding: 1rem; background: white; box-shadow: 0 2px 10px rgba(15,23,42,.035); }
@media (max-width: 760px) {
    .search-intro { margin-top: 2.3rem; }
    [data-testid="stMainBlockContainer"] { padding: 1rem 1rem 2rem; }
}
</style>
"""


def apply_theme() -> None:
    """Inject the global VISTA stylesheet. Call once after set_page_config()."""
    st.markdown(_CSS, unsafe_allow_html=True)


def brand_block() -> None:
    """Simple VISTA brand header for the sidebar."""
    st.markdown(
        """
        <div class="vista-brand">
            <div class="vista-brand-logo">V</div>
            <div>
                <div class="vista-brand-name">VISTA</div>
                <div class="vista-brand-sub">Semantic search for medical reports</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def hero(icon: str, title: str, subtitle: str, badge: str = None) -> None:
    """Plain card page header."""
    badge_html = f'<span class="badge">{badge}</span>' if badge else ""
    st.markdown(
        f"""
        <div class="vista-hero">
            <h1><span class="icon">{icon}</span>{title}{badge_html}</h1>
            <p class="sub">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section(text: str) -> None:
    """Section header with a fading rule to the right."""
    st.markdown(f'<div class="vista-section">{text}</div>', unsafe_allow_html=True)


def pills(items, alt: bool = False) -> None:
    """Render a row of keyword chips."""
    cls = "vista-pill alt" if alt else "vista-pill"
    html = "".join(f'<span class="{cls}">{i}</span>' for i in items)
    st.markdown(html, unsafe_allow_html=True)


def status_row(key: str, ok: bool) -> str:
    """One sidebar system-status row as HTML."""
    state = "✅ Ready" if ok else "❌ Missing"
    cls = "ok" if ok else "off"
    return f'<div class="vista-status"><span class="k">{key}</span><span class="{cls}">{state}</span></div>'


def status_value_row(key: str, value: str) -> str:
    """One sidebar status row with a custom value."""
    return f'<div class="vista-status"><span class="k">{key}</span><span class="mono">{value}</span></div>'


def side_stat(caption: str, value) -> None:
    """Small sidebar stat card."""
    st.markdown(
        f'<div class="vista-side-stat"><div class="cap">{caption}</div><div class="val">{value}</div></div>',
        unsafe_allow_html=True,
    )
