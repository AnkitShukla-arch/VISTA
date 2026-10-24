"use client";

import { useEffect, useState } from "react";
import { Activity, FileText, Stethoscope } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getBoxes, getHealth, getMetrics } from "@/lib/api";
import { boxes as mockBoxes } from "@/mocks/data";
import type { Box, Metrics, VistaHealth } from "@/lib/types";

export default function DoctorAnalyticsPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [boxes, setBoxes] = useState<Box[]>(mockBoxes);
  const [health, setHealth] = useState<VistaHealth | null>(null);
  useEffect(() => { getMetrics().then(setMetrics).catch(() => undefined); getBoxes().then(setBoxes).catch(() => undefined); getHealth().then(setHealth).catch(() => undefined); }, []);
  const problems = (metrics?.problem_counts ?? []).filter((item) => item.count > 0);
  const totalFlags = problems.reduce((total, item) => total + item.count, 0);
  const colors = boxes.length ? boxes.map((box) => box.color) : ["#55a98b"];

  return <div className="page doctor-analytics-page">
    <header className="page-heading"><div className="eyebrow">DOCTOR WORKSPACE / ANALYSIS</div><h1>Clinical report analysis</h1><p>Explore how often common clinical findings appear across the reports indexed by VISTA.</p></header>
    <div className="doctor-analysis-stats">
      <article className="card doctor-analysis-stat"><FileText size={17} /><span>Searchable reports</span><strong>{health?.document_count.toLocaleString() ?? "—"}</strong></article>
      <article className="card doctor-analysis-stat"><Activity size={17} /><span>Finding mentions</span><strong>{totalFlags.toLocaleString()}</strong></article>
      <article className="card doctor-analysis-stat"><Stethoscope size={17} /><span>Clinical groups</span><strong>{health?.box_count ?? boxes.length}</strong></article>
    </div>
    <div className="doctor-analysis-grid">
      <section className="card doctor-analysis-card"><div className="doctor-browser-heading"><div><span className="eyebrow">REPORT COUNTS</span><h2>Reports mentioning each finding</h2><p>A report can mention more than one finding.</p></div></div>
        {problems.length ? <div className="doctor-analysis-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={problems} layout="vertical" margin={{ top: 5, right: 16, left: 5, bottom: 0 }}><CartesianGrid stroke="var(--grid)" horizontal={false} /><XAxis type="number" tick={{ fill: "var(--muted)", fontSize: 12 }} axisLine={false} tickLine={false} /><YAxis type="category" dataKey="problem" width={118} tick={{ fill: "var(--muted)", fontSize: 13 }} axisLine={false} tickLine={false} /><Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--foreground)" }} /><Bar dataKey="count" name="Reports" radius={[0, 5, 5, 0]}>{problems.map((item, index) => <Cell key={item.problem} fill={colors[index % colors.length]} />)}</Bar></BarChart></ResponsiveContainer></div> : <div className="doctor-findings-empty">Finding analysis will appear when report text is indexed.</div>}
      </section>
      <section className="card doctor-analysis-card"><div className="doctor-browser-heading"><div><span className="eyebrow">FINDING MIX</span><h2>Share of clinical finding mentions</h2><p>Percentages use all detected report finding tags.</p></div></div>
        {problems.length ? <><div className="doctor-analysis-pie"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={problems} dataKey="count" nameKey="problem" innerRadius="58%" outerRadius="82%" paddingAngle={2}>{problems.map((item, index) => <Cell key={item.problem} fill={colors[index % colors.length]} />)}</Pie><Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--foreground)" }} /></PieChart></ResponsiveContainer><span>{totalFlags.toLocaleString()}<small>finding tags</small></span></div><div className="doctor-findings-legend">{problems.map((item, index) => <div key={item.problem}><i style={{ background: colors[index % colors.length] }} /><span>{item.problem}</span><b>{totalFlags ? Math.round(item.count / totalFlags * 100) : 0}% · {item.count.toLocaleString()}</b></div>)}</div></> : <div className="doctor-findings-empty">No problem categories are available yet.</div>}
      </section>
    </div>
    <section className="card doctor-analysis-boxes"><div className="doctor-browser-heading"><div><span className="eyebrow">SEMANTIC BOXES</span><h2>Reports by clinical group</h2></div></div><div className="doctor-group-grid">{boxes.map((box) => <article className="card doctor-group-card doctor-group-static" key={box.box_id}><span className="doctor-group-top"><i className="color-dot" style={{ background: box.color }} /><span className="mono">{box.doc_count.toLocaleString()} reports</span></span><strong>{box.label}</strong><span className="doctor-group-keywords">{box.keywords.slice(0, 4).join(" · ")}</span></article>)}</div></section>
  </div>;
}
