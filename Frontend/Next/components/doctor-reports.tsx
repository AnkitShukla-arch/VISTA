"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, FileSearch, PieChart as PieIcon, X } from "lucide-react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { getBoxes, getDocuments, getDocumentLabResults, getMetrics } from "@/lib/api";
import { boxes as mockBoxes } from "@/mocks/data";
import type { Box, ClinicalDocument, Metrics, ParsedLabResults } from "@/lib/types";

export function DoctorReports() {
  const [groups, setGroups] = useState<Box[]>(mockBoxes);
  const [active, setActive] = useState<Box | null>(null);
  const [reports, setReports] = useState<ClinicalDocument[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [preview, setPreview] = useState<ClinicalDocument | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [labResults, setLabResults] = useState<ParsedLabResults | null>(null);
  const [labError, setLabError] = useState(false);
  const [showRaw, setShowRaw] = useState(false);
  const pageSize = 12;

  useEffect(() => {
    getBoxes().then(setGroups).catch(() => undefined);
    getMetrics().then(setMetrics).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!active) return;
    getDocuments({ box: String(active.box_id), page, page_size: pageSize })
      .then(({ items, total: count }) => { setReports(items); setTotal(count); })
      .catch(() => { setReports([]); setTotal(0); });
  }, [active, page]);

  useEffect(() => {
    if (!preview) return;
    let current = true;
    setLabResults(null);
    setLabError(false);
    setShowRaw(false);
    getDocumentLabResults(preview.doc_id)
      .then((value) => { if (current) setLabResults(value); })
      .catch(() => { if (current) setLabError(true); });
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") setPreview(null); };
    window.addEventListener("keydown", close);
    return () => { current = false; window.removeEventListener("keydown", close); };
  }, [preview]);

  const chart = useMemo(() => (metrics?.problem_counts ?? []).filter((item) => item.count > 0).slice(0, 7), [metrics]);
  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  return <div className="page doctor-reports-page">
    <header className="page-heading"><div className="eyebrow">DOCTOR WORKSPACE / REPORTS</div><h1>Clinical report groups</h1><p>Choose a clinical box to browse its reports. Select any report to open a clear, full-width preview.</p></header>

    <div className="doctor-group-grid">
      {groups.map((group) => <button key={group.box_id} className={`card doctor-group-card ${active?.box_id === group.box_id ? "active" : ""}`} onClick={() => { setActive(group); setPage(1); }}>
        <span className="doctor-group-top"><i className="color-dot" style={{ background: group.color }} /><span className="mono">{group.doc_count.toLocaleString()} reports</span></span>
        <strong>{group.label}</strong>
        <span className="doctor-group-keywords">{group.keywords.slice(0, 4).join(" · ") || "Clinical reports"}</span>
        <span className="doctor-group-open">Open group <ArrowRight size={14} /></span>
      </button>)}
    </div>

    <section className="doctor-report-browser">
      <div className="doctor-browser-heading">
        <div><span className="eyebrow">{active ? "SELECTED CLINICAL BOX" : "REPORT BROWSER"}</span><h2>{active?.label ?? "Select a clinical box"}</h2><p>{active ? `${total.toLocaleString()} reports in this group` : "Reports are grouped by the semantic box that best matches their clinical content."}</p></div>
        {active && <button className="doctor-clear" onClick={() => { setActive(null); setReports([]); }}><ArrowLeft size={14} /> All groups</button>}
      </div>

      {active ? reports.length ? <>
        <div className="doctor-report-cards">{reports.map((report, index) => <button className="card doctor-report-card" key={report.doc_id} onClick={() => setPreview(report)}>
          <span className="doctor-report-card-top"><FileSearch size={16} /><span className="mono">{String((page - 1) * pageSize + index + 1).padStart(2, "0")}</span></span>
          <strong title={report.title}>{report.title}</strong>
          <span>{report.patient_name && report.patient_name !== "Not found" ? report.patient_name : report.specialty} · {report.specialty}</span>
          <small>{report.snippet || "Open the report to review the extracted clinical text."}</small>
          <em>Open report <ArrowRight size={13} /></em>
        </button>)}</div>
        <div className="pagination"><span>{total ? `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} of ${total} reports` : "0 reports"}</span><div className="doctor-pager"><button className="page-btn" aria-label="Previous reports" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>‹</button><span className="mono">{page} / {pageCount}</span><button className="page-btn" aria-label="Next reports" disabled={page >= pageCount} onClick={() => setPage((value) => value + 1)}>›</button></div></div>
      </> : <div className="card doctor-reports-empty"><FileSearch size={21} /><strong>No reports are assigned to this group yet</strong><span>Import the Phase 2 dataset or upload reports from the technician workspace.</span></div> : <div className="card doctor-reports-empty"><PieIcon size={21} /><strong>Clinical reports, organized by topic</strong><span>Choose a box above to browse report cards and open the full report viewer.</span></div>}
    </section>

    {preview && <div className="doctor-preview-backdrop" onMouseDown={() => setPreview(null)}><section className="card doctor-preview-modal" role="dialog" aria-modal="true" aria-label="Clinical report preview" onMouseDown={(event) => event.stopPropagation()}>
      <header className="doctor-modal-header"><div><span className="eyebrow">REPORT PREVIEW</span><h2>{preview.title}</h2><div className="doctor-preview-meta"><span className="mono">{preview.doc_id}</span><span>{preview.specialty}</span>{preview.patient_name && preview.patient_name !== "Not found" && <span>{preview.patient_name}</span>}</div></div><button className="icon-plain" aria-label="Close preview" onClick={() => setPreview(null)}><X size={18} /></button></header>
      <div className="doctor-modal-content">
        <article className="doctor-readable-report">
          <div className="doctor-note-heading"><FileSearch size={16} /><strong>Extracted clinical report</strong></div>
          {labResults && <div className="lab-summary"><strong>{labResults.summary.abnormal} abnormal</strong> of {labResults.summary.total} results <button type="button" className="lab-raw-toggle" aria-expanded={showRaw} onClick={() => setShowRaw((value) => !value)}>{showRaw ? "Hide raw text" : "Raw text"}</button></div>}
          {labError && <div className="lab-summary">Structured results are unavailable. Showing the original extraction. <button type="button" className="lab-raw-toggle" aria-expanded={showRaw} onClick={() => setShowRaw((value) => !value)}>{showRaw ? "Hide raw text" : "Raw text"}</button></div>}
          {!labResults && !labError && <div className="doctor-report-body">Parsing extracted results…</div>}
          {labResults && <>
            {labResults.results.length ? <div className="lab-table-wrap"><table className="lab-results-table"><thead><tr><th>Test</th><th className="lab-number">Result</th><th>Unit</th><th>Reference range</th><th>Method</th></tr></thead>
              {Object.entries(labResults.results.reduce<Record<string, typeof labResults.results>>((groups, row) => { const key = row.section || ""; (groups[key] ??= []).push(row); return groups; }, {})).map(([section, rows]) => <tbody key={section}>{section && <tr className="lab-section-row"><th colSpan={5}>{section}</th></tr>}{rows.map((row, index) => <tr key={`${section}-${row.test}-${index}`}><th scope="row" className="lab-test-name">{row.test}</th><td className={`lab-number lab-status-${row.status}`}>{row.status === "high" ? "↑ " : row.status === "low" ? "↓ " : ""}{row.value}</td><td>{row.unit || "—"}</td><td className="lab-muted">{row.reference_range || "—"}</td><td className="lab-muted">{row.method || "—"}</td></tr>)}</tbody>)}
            </table></div> : <div className="lab-empty">No structured lab rows could be recognized in this report.</div>}
            {!!labResults.unparsed.length && <details className="lab-unparsed"><summary>Unparsed text ({labResults.unparsed.length} tokens)</summary><pre>{labResults.unparsed.join("\n")}</pre></details>}
          </>}
          {showRaw && <pre className="lab-raw-text">{preview.full_text || preview.snippet || "No extracted report text is available."}</pre>}
        </article>
        <aside className="doctor-findings-panel"><div className="doctor-note-heading"><PieIcon size={16} /><strong>Findings across VISTA</strong></div><p>Share of detected report findings in the searchable collection.</p>
          {chart.length ? <><div className="doctor-findings-chart"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={chart} dataKey="count" nameKey="problem" innerRadius="58%" outerRadius="82%" paddingAngle={2}>{chart.map((item, index) => <Cell key={item.problem} fill={groups[index % groups.length]?.color ?? "var(--accent)"} />)}</Pie><Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--foreground)" }} /></PieChart></ResponsiveContainer><span>{chart.reduce((sum, item) => sum + item.count, 0).toLocaleString()}<small>finding tags</small></span></div>
          <div className="doctor-findings-legend">{chart.map((item, index) => { const totalTags = chart.reduce((sum, row) => sum + row.count, 0); return <div key={item.problem}><i style={{ background: groups[index % groups.length]?.color ?? "var(--accent)" }} /><span>{item.problem.replace(/^./, (letter) => letter.toUpperCase())}</span><b>{Math.round(item.count / totalTags * 100)}%</b></div>; })}</div></> : <div className="doctor-findings-empty">Problem distribution will appear as reports are indexed.</div>}
          <div className="doctor-report-tags">{(preview.conditions ?? []).map((condition) => <span key={condition}>{condition}</span>)}</div>
        </aside>
      </div>
    </section></div>}
  </div>;
}
