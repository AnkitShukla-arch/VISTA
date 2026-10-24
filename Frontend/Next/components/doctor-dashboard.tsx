"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { ArrowRight, Check, Copy, FileSearch, Search, ShieldCheck, Stethoscope, X } from "lucide-react";
import { getDocuments, getHealth, searchReports } from "@/lib/api";
import type { ClinicalDocument, SearchResponse, VistaHealth } from "@/lib/types";

const prompts = ["Reports for Mr. Bhalla", "Patients with high sugar", "Cancer case reports", "Reports mentioning high blood pressure"];

export function DoctorDashboard() {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [recent, setRecent] = useState<ClinicalDocument[]>([]);
  const [selected, setSelected] = useState<ClinicalDocument | null>(null);
  const [openReport, setOpenReport] = useState<ClinicalDocument | null>(null);
  const [health, setHealth] = useState<VistaHealth | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => undefined);
    getDocuments({ page: 1, page_size: 6 }).then(({ items }) => setRecent(items)).catch(() => undefined);
  }, []);

  const search = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!query.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      const data = await searchReports(query.trim(), 5, 4);
      setResponse(data);
      setSelected(data.documents[0] ?? null);
    } catch {
      setError("Could not search the reports. Check the VISTA connection and try again.");
    } finally {
      setBusy(false);
    }
  };

  const shown = response?.documents ?? recent;
  const preview = selected ?? shown[0] ?? null;
  const reportText = (document: ClinicalDocument) => (document.full_text || document.snippet || "No extracted report text is available.")
    .replace(/\r\n?/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  const resultLabel = useMemo(() => response ? `${response.documents.length} matching reports` : "Recently added reports", [response]);

  useEffect(() => {
    if (!openReport) return;
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") setOpenReport(null); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [openReport]);

  return <div className="page doctor-page">
    <header className="doctor-heading">
      <div><span className="eyebrow">DOCTOR WORKSPACE</span><h1>Find the report you need.</h1><p>Search by patient name, symptom, condition, or ask for a group of reports.</p></div>
      <div className="doctor-secure"><ShieldCheck size={15}/> Clinical reports workspace</div>
    </header>

    <form className="doctor-search" onSubmit={search}>
      <Search size={19}/>
      <input value={query} onChange={event => setQuery(event.target.value)} placeholder="Try “Show me Mr. Bhalla’s report” or “Patients with diabetes”" aria-label="Search patient reports"/>
      <button type="submit" disabled={busy || !query.trim()}>{busy ? "Searching…" : <>Search reports <ArrowRight size={15}/></>}</button>
    </form>
    <div className="doctor-prompts"><span>Try asking</span>{prompts.map(prompt => <button key={prompt} onClick={() => setQuery(prompt)}>{prompt}</button>)}</div>
    {error && <p className="pipeline-error">{error}</p>}

    <section className="doctor-stats" aria-label="Report collection summary">
      <div className="card doctor-stat"><span>Searchable reports</span><strong>{health?.document_count.toLocaleString() ?? "—"}</strong><small>Across the VISTA collection</small></div>
      <div className="card doctor-stat"><span>Clinical groups</span><strong>{health?.box_count ?? "—"}</strong><small>Organized by report similarity</small></div>
      <div className="card doctor-stat"><span>Search response</span><strong>{response ? `${(response.latency_ms / 1000).toFixed(2)}s` : "Ready"}</strong><small>{response ? "Latest report search" : "Ask in everyday language"}</small></div>
    </section>

    <div className="doctor-results-heading"><div><span className="eyebrow">REPORTS</span><h2>{resultLabel}</h2></div>{response && <button className="doctor-clear" onClick={() => { setResponse(null); setSelected(null); setQuery(""); }}>Clear search</button>}</div>
    <section className="doctor-report-layout">
      <div className="card doctor-report-list">
        {shown.length ? shown.map((doc, index) => <button className={`doctor-report-item ${preview?.doc_id === doc.doc_id ? "active" : ""}`} key={doc.doc_id} aria-label={`Open report ${doc.title}`} aria-pressed={preview?.doc_id === doc.doc_id} onClick={() => { setSelected(doc); setOpenReport(doc); }}>
          <span className="doctor-report-icon"><FileSearch size={17}/></span><span className="doctor-report-text"><strong>{doc.title}</strong><span>{doc.patient_name && doc.patient_name !== "Not found" ? `${doc.patient_name} · ` : ""}{doc.specialty} · {doc.doc_id}</span><small>{doc.snippet || "Report text is ready to review."}</small></span><span className="doctor-report-number">{String(index + 1).padStart(2, "0")}</span>
        </button>) : <div className="doctor-empty"><Stethoscope size={20}/><strong>{response ? "No matching reports found" : "No reports are available yet"}</strong><span>{response ? "Try another patient name or clinical phrase." : "Newly processed reports will appear here."}</span></div>}
      </div>

      <aside className="card doctor-preview">
        {preview ? <>
          <div className="doctor-preview-head"><div><span className="eyebrow">REPORT PREVIEW</span><h2>{preview.title}</h2></div><div className="doctor-preview-actions"><button className="copy-button" onClick={() => setOpenReport(preview)}><FileSearch size={14}/><span>Open report</span></button><button className="copy-button" aria-label="Copy report text" onClick={async () => { await navigator.clipboard?.writeText(reportText(preview)); setCopied(true); setTimeout(() => setCopied(false), 1300); }}>{copied ? <Check size={14}/> : <Copy size={14}/>}<span>{copied ? "Copied" : "Copy"}</span></button></div></div>
          <div className="doctor-preview-meta"><span className="mono">{preview.doc_id}</span><span>{preview.specialty}</span>{preview.patient_name && preview.patient_name !== "Not found" && <span>{preview.patient_name}</span>}</div>
          <div className="doctor-note"><span>CLINICAL REPORT</span><p>{reportText(preview)}</p></div>
          <div className="doctor-preview-footer"><span>Semantic match</span><strong>{Math.round(preview.cosine_similarity * 100)}%</strong></div>
        </> : <div className="doctor-empty"><FileSearch size={20}/><strong>Select a report to review</strong><span>Full extracted report text will appear here.</span></div>}
      </aside>
    </section>
    {openReport && <div className="doctor-full-report-backdrop" onMouseDown={() => setOpenReport(null)}><section className="card doctor-full-report" role="dialog" aria-modal="true" aria-label="Full clinical report" onMouseDown={(event) => event.stopPropagation()}>
      <header className="doctor-full-report-header"><div><span className="eyebrow">FULL CLINICAL REPORT</span><h2>{openReport.title}</h2><div className="doctor-preview-meta"><span className="mono">{openReport.doc_id}</span><span>{openReport.specialty}</span>{openReport.patient_name && openReport.patient_name !== "Not found" && <span>{openReport.patient_name}</span>}</div></div><button className="icon-plain" aria-label="Close report" onClick={() => setOpenReport(null)}><X size={18}/></button></header>
      <div className="doctor-full-report-body">{reportText(openReport)}</div>
    </section></div>}
  </div>;
}
