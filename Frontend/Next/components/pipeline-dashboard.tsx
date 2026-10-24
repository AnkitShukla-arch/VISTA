"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type FormEvent } from "react";
import { Activity, ArrowRight, BrainCircuit, Check, ChevronDown, CircleAlert, Database, FileText, LoaderCircle, Search, Upload, Workflow } from "lucide-react";
import { askWarehouse, createIngestionJob, getDatasetImport, getHealth, getIngestionJob, getIngestionJobs, startDatasetImport } from "@/lib/api";
import type { DatasetImport, IngestionJob, VistaHealth, WarehouseQuery } from "@/lib/types";

const phases = [
  { id: "phase1", label: "Ingest & extract", detail: "OCR · ETL", icon: Upload },
  { id: "phase2", label: "Fingerprint & embed", detail: "Clinical profile · 384-D", icon: BrainCircuit },
  { id: "phase3", label: "Compare meaning", detail: "Cosine similarity", icon: Activity },
  { id: "phase4", label: "Assign a box", detail: "FAISS · semantic groups", icon: Workflow },
  { id: "phase5", label: "Store & query", detail: "DuckDB · SQL", icon: Database },
];

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function statusFor(job: IngestionJob | null, phaseIndex: number) {
  if (!job) return "ready";
  if (job.status === "complete") return "done";
  if (phaseIndex === 0) {
    const states = job.steps.slice(0, 2).map((step) => step.status);
    return states.includes("failed") ? "failed" : states.includes("running") ? "running" : states.every((state) => state === "done") ? "done" : "ready";
  }
  if (phaseIndex === 1) {
    const states = job.steps.slice(2, 4).map((step) => step.status);
    return states.includes("failed") ? "failed" : states.includes("running") ? "running" : states.every((state) => state === "done") ? "done" : "ready";
  }
  if (phaseIndex === 2) return job.steps[4]?.status ?? "ready";
  if (phaseIndex === 3) return job.steps[5]?.status ?? "ready";
  const states = job.steps.slice(6).map((step) => step.status);
  return states.includes("failed") ? "failed" : states.includes("running") ? "running" : states.every((state) => state === "done") ? "done" : "ready";
}

function StepStatus({ status }: { status: string }) {
  if (status === "done") return <Check size={14} />;
  if (status === "running") return <LoaderCircle size={14} className="pipeline-spin" />;
  if (status === "failed") return <CircleAlert size={14} />;
  return <span className="phase-step-dot" />;
}

export function PipelineDashboard() {
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [question, setQuestion] = useState("");
  const [query, setQuery] = useState<WarehouseQuery | null>(null);
  const [queryError, setQueryError] = useState("");
  const [querying, setQuerying] = useState(false);
  const [datasetImport, setDatasetImport] = useState<DatasetImport | null>(null);
  const [importStarting, setImportStarting] = useState(false);
  const [health, setHealth] = useState<VistaHealth | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getIngestionJobs().then(setJobs).catch(() => undefined);
    getHealth().then(setHealth).catch(() => setHealth(null));
    getDatasetImport().then(setDatasetImport).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (datasetImport?.status !== "queued" && datasetImport?.status !== "running") return;
    const timer = window.setInterval(() => getDatasetImport().then((fresh) => {
      setDatasetImport(fresh);
      if (fresh.status === "complete") getHealth().then(setHealth).catch(() => undefined);
    }).catch(() => undefined), 1600);
    return () => window.clearInterval(timer);
  }, [datasetImport?.status]);

  useEffect(() => {
    const activeJobs = jobs.filter((job) => job.status === "queued" || job.status === "running");
    if (!activeJobs.length) return;
    const timer = window.setInterval(() => {
      activeJobs.forEach((job) => getIngestionJob(job.job_id).then((fresh) => {
        setJobs((current) => current.map((item) => item.job_id === fresh.job_id ? fresh : item));
      }).catch(() => undefined));
    }, 1100);
    return () => window.clearInterval(timer);
  }, [jobs]);

  const latestActive = jobs.find((job) => job.status === "running" || job.status === "queued") ?? null;
  const latestComplete = jobs.find((job) => job.status === "complete") ?? null;
  const displayedJob = latestActive ?? latestComplete ?? jobs[0] ?? null;
  const recordCount = useMemo(() => jobs.reduce((total, job) => total + (job.result?.record_count ?? 0), 0), [jobs]);

  const chooseFiles = useCallback((incoming: FileList | File[]) => {
    setFiles(Array.from(incoming).slice(0, 10));
    setUploadError("");
  }, []);

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    if (event.dataTransfer.files.length) chooseFiles(event.dataTransfer.files);
  };

  const submitFiles = async (event: FormEvent) => {
    event.preventDefault();
    if (!files.length || uploading) return;
    setUploading(true);
    setUploadError("");
    try {
      const created: IngestionJob[] = [];
      for (const file of files) created.push(await createIngestionJob(file));
      setJobs((current) => [...created.reverse(), ...current.filter((job) => !created.some((next) => next.job_id === job.job_id))]);
      setFiles([]);
      if (fileInput.current) fileInput.current.value = "";
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Could not start the upload.");
    } finally {
      setUploading(false);
    }
  };

  const submitQuery = async (event: FormEvent) => {
    event.preventDefault();
    if (!question.trim() || querying) return;
    setQuerying(true);
    setQueryError("");
    try { setQuery(await askWarehouse(question.trim())); }
    catch (error) { setQueryError(error instanceof Error ? error.message : "The warehouse query could not be completed."); }
    finally { setQuerying(false); }
  };

  const importDataset = async () => {
    if (importStarting || datasetImport?.status === "running" || datasetImport?.status === "queued") return;
    setImportStarting(true);
    try { setDatasetImport(await startDatasetImport()); }
    catch (error) { setUploadError(error instanceof Error ? error.message : "Could not start the Phase 2 dataset import."); }
    finally { setImportStarting(false); }
  };

  return <div className="page pipeline-page">
    <header className="pipeline-page-heading">
      <div><span className="eyebrow">VISTA WORKSPACE</span><h1>Bring a report into VISTA</h1><p>Upload clinical data. VISTA extracts, fingerprints, embeds, and files it for semantic search.</p></div>
      <div className="corpus-chip"><span className={`pulse ${health ? "" : "pulse-offline"}`} />{health ? `${health.document_count.toLocaleString()} searchable reports` : "API not connected"}<i />{health ? `${health.box_count} semantic boxes · ${health.embedding_dimension}-D` : "Start the VISTA API to process uploads"}</div>
    </header>

    <section className="pipeline-flow" aria-label="VISTA processing phases">
      {phases.map((phase, index) => {
        const status = statusFor(displayedJob, index);
        const Icon = phase.icon;
        return <div className={`phase-card phase-${status}`} key={phase.id}>
          <div className="phase-card-top"><span className="phase-number">0{index + 1}</span><span className="phase-state"><StepStatus status={status} />{status === "ready" ? "Ready" : status === "running" ? "Running" : status === "failed" ? "Issue" : "Done"}</span></div>
          <div className="phase-card-name"><Icon size={16} /><strong>{phase.label}</strong></div>
          <span className="phase-card-detail">{phase.detail}</span>
        </div>;
      })}
    </section>

    <section className="card dataset-import-card">
      <div><span className="eyebrow">LOCAL DATASET</span><h2>Import the Phase 2 report collection</h2><p>Batch process the prepared dataset manifest on this machine. The source files stay in the dataset folder.</p></div>
      <div className="dataset-import-action">
        <button type="button" onClick={importDataset} disabled={importStarting || datasetImport?.status === "running" || datasetImport?.status === "queued" || datasetImport?.status === "complete"}>
          {datasetImport?.status === "running" || datasetImport?.status === "queued" ? <><LoaderCircle size={15} className="pipeline-spin" /> Importing</> : datasetImport?.status === "complete" ? <><Check size={15} /> Imported</> : importStarting ? <><LoaderCircle size={15} className="pipeline-spin" /> Starting</> : <>Import Phase 2 dataset <ArrowRight size={15} /></>}
        </button>
        {datasetImport && <span className={`dataset-import-status ${datasetImport.status === "failed" ? "is-error" : ""}`}>
          {datasetImport.status === "complete" ? `${datasetImport.record_count.toLocaleString()} reports indexed` : datasetImport.status === "failed" ? datasetImport.error : datasetImport.status === "running" || datasetImport.status === "queued" ? `${datasetImport.processed.toLocaleString()} / ${datasetImport.total.toLocaleString()} files · ${datasetImport.record_count.toLocaleString()} reports ready` : "Uses phase1_selection.txt"}
        </span>}
      </div>
      {(datasetImport?.status === "running" || datasetImport?.status === "queued") && <div className="dataset-import-progress"><i style={{ width: `${datasetImport.total ? Math.round(datasetImport.processed / datasetImport.total * 100) : 0}%` }} /></div>}
    </section>

    <div className="pipeline-content-grid">
      <section className={`card upload-card ${dragging ? "is-dragging" : ""}`} onDragEnter={(event) => { event.preventDefault(); setDragging(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragging(false); }} onDrop={handleDrop}>
        <div className="upload-title"><div className="upload-icon"><Upload size={18} /></div><div><h2>Add medical data</h2><p>One file can contain a report or a table of records.</p></div></div>
        <form onSubmit={submitFiles}>
          <div className="upload-dropzone" role="button" tabIndex={0} onClick={() => fileInput.current?.click()} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") fileInput.current?.click(); }}>
            <input ref={fileInput} type="file" multiple accept=".pdf,.docx,.csv,.tsv,.json,.jsonl,.xlsx,.txt,.text,.md,.xml,.html,.htm,.png,.jpg,.jpeg,.tif,.tiff" onChange={(event) => event.target.files && chooseFiles(event.target.files)} />
            <span className="drop-icon"><FileText size={20} /></span>
            <strong>{files.length ? `${files.length} file${files.length === 1 ? "" : "s"} selected` : "Drop files here or browse"}</strong>
            <span>PDF · DOCX · CSV/TSV · JSON · XLSX · TXT · XML/HTML · PNG/JPG · up to 50 MB</span>
          </div>
          {files.length > 0 && <ul className="selected-files">{files.map((file) => <li key={`${file.name}-${file.lastModified}`}><span><FileText size={14} />{file.name}</span><small>{formatBytes(file.size)}</small></li>)}</ul>}
          {uploadError && <p className="pipeline-error"><CircleAlert size={14} />{uploadError}</p>}
          <div className="upload-actions"><span>Original files remain in the raw layer.</span><button type="submit" disabled={!files.length || uploading}>{uploading ? <><LoaderCircle size={15} className="pipeline-spin" /> Sending</> : <>Start pipeline <ArrowRight size={15} /></>}</button></div>
        </form>
      </section>

      <section className="card query-card">
        <div className="query-card-title"><div className="upload-icon"><Search size={17} /></div><div><h2>Ask the VISTA data agent</h2><p>Turn a count question into a DuckDB query.</p></div></div>
        <form className="warehouse-query-form" onSubmit={submitQuery}><input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="How many reports mention hypertension?" aria-label="Ask the VISTA warehouse" /><button disabled={querying || !question.trim()} aria-label="Run query">{querying ? <LoaderCircle size={16} className="pipeline-spin" /> : <ArrowRight size={16} />}</button></form>
        <div className="query-suggestions">{["How many reports are in total?", "How many mention diabetes?"].map((suggestion) => <button key={suggestion} onClick={() => setQuestion(suggestion)}>{suggestion}</button>)}</div>
        {queryError && <p className="pipeline-error"><CircleAlert size={14} />{queryError}</p>}
        {query && <div className="query-result"><div><span>Query result</span><strong>{query.result.toLocaleString()} <small>reports</small></strong></div><p>{query.plan}</p><code>{query.sql}</code><span className="query-source"><Database size={12} />{query.source}</span></div>}
      </section>
    </div>

    <section className="pipeline-jobs-section">
      <div className="pipeline-section-heading"><div><span className="eyebrow">LIVE PIPELINE</span><h2>Recent uploads</h2></div><span>{recordCount.toLocaleString()} record{recordCount === 1 ? "" : "s"} added this session</span></div>
      {jobs.length === 0 ? <div className="card empty-jobs"><FileText size={18} /><span>Uploaded reports and their processing steps will appear here.</span></div> : <div className="pipeline-jobs">{jobs.slice(0, 10).map((job) => <article className="card pipeline-job" key={job.job_id}>
        <div className="pipeline-job-summary"><div className="job-file-icon"><FileText size={17} /></div><div className="job-file-name"><strong title={job.filename}>{job.filename}</strong><span>{formatBytes(job.size_bytes)} · {job.result ? `${job.result.record_count} record${job.result.record_count === 1 ? "" : "s"}` : job.status === "failed" ? "Processing stopped" : job.steps.find((step) => step.status === "running")?.label ?? "Queued"}</span></div><div className={`job-status job-status-${job.status}`}>{job.status === "complete" ? <Check size={14} /> : job.status === "failed" ? <CircleAlert size={14} /> : <LoaderCircle size={14} className="pipeline-spin" />}{job.status}</div><span className="job-progress-value">{job.progress}%</span></div>
        <div className="job-progress"><i style={{ width: `${job.progress}%` }} /></div>
        <details className="job-details"><summary>View pipeline details <ChevronDown size={14} /></summary>
          <div className="job-step-list">{job.steps.map((step) => <div className={`job-step job-step-${step.status}`} key={step.key}><span className="job-step-icon"><StepStatus status={step.status} /></span><div><strong>{step.label}</strong><span>{step.message === "Waiting" ? step.detail : step.message}</span></div></div>)}</div>
          {job.error && <p className="pipeline-error"><CircleAlert size={14} />{job.error}</p>}
          {job.result && <div className="job-result-summary"><span><Database size={13} />{job.result.storage}</span><span><BrainCircuit size={13} />{job.result.embedding_dimension}-D fingerprint</span><span><Workflow size={13} />{job.result.profiles[0]?.box_label ?? "Semantic box assigned"}</span><span><Search size={13} />SQL confirmed {job.result.sql_count.toLocaleString()} record{job.result.sql_count === 1 ? "" : "s"}</span></div>}
          {job.result?.profiles?.length ? <div className="job-records"><strong>Extracted fingerprints</strong>{job.result.profiles.slice(0, 4).map((profile) => <div className="job-record" key={profile.doc_id}><span className="record-id">{profile.doc_id}</span><span className="record-title" title={profile.title}>{profile.title}</span><span className="record-patient">{profile.patient_name}{profile.age ? ` · ${profile.age} y` : ""}</span><span className="record-box">{profile.box_label}</span><span className="record-conditions">{[...profile.conditions, ...Object.entries(profile.vitals ?? {}).map(([label, value]) => `${label} ${value}`)].join(" · ")}</span></div>)}{job.result.profiles.length > 4 && <small>Showing 4 of {job.result.record_count} extracted records.</small>}</div> : null}
        </details>
      </article>)}</div>}
    </section>
  </div>;
}
