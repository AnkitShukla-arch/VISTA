"use client";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { ArrowRight, Check, Copy, Search, X } from "lucide-react";
import { searchReports } from "@/lib/api";
import type { ClinicalDocument, SearchResponse } from "@/lib/types";
import { boxes, documents as mockDocuments } from "@/mocks/data";

const examples=["Heart attack with elevated troponin","Knee pain after sports injury","Pediatric asthma exacerbation","Migraine with visual aura","Prenatal ultrasound findings"];
const Skeleton=()=> <div className="workspace-grid"><div className="skeleton-stack">{[1,2,3,4,5].map(i=><div className="skeleton" key={i} style={{height:i===1?78:56}}/>)}</div><div className="skeleton" style={{height:"calc(100vh - 170px)"}}/></div>;
function QueryOptions({boxesCount,setBoxesCount,topK,setTopK}:{boxesCount:number;setBoxesCount:(n:number)=>void;topK:number;setTopK:(n:number)=>void}){
  return <details className="options-popover"><summary>{boxesCount} boxes · {topK} results</summary><div className="options-menu"><label>Semantic boxes</label><div className="segmented">{[1,2,3,4].map(n=><button key={n} type="button" className={boxesCount===n?"selected":""} onClick={()=>setBoxesCount(n)}>{n}</button>)}</div><label>Results per box</label><div className="segmented">{[3,5,8].map(n=><button key={n} type="button" className={topK===n?"selected":""} onClick={()=>setTopK(n)}>{n}</button>)}</div></div></details>
}
function SearchRow({doc,index,selected,query="",onSelect,onKey}:{doc:ClinicalDocument;index:number;selected:boolean;query?:string;onSelect:()=>void;onKey:(key:string)=>void}){
  const terms=query.trim().split(/\s+/).filter(t=>t.length>3).map(t=>t.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"));const parts=terms.length?doc.snippet.split(new RegExp(`(${terms.join("|")})`,"ig")):[doc.snippet];
  return <div role="option" aria-selected={selected} tabIndex={0} className={`result-row ${selected?"selected":""}`} onClick={onSelect} onKeyDown={e=>{if(e.key==="ArrowDown"||e.key==="ArrowUp"){e.preventDefault();onKey(e.key)}if(e.key==="Enter"){e.preventDefault();onSelect()}}}>
    <span className="row-rank">{String(index+1).padStart(2,"0")}</span><span className="row-main"><strong>{doc.title}</strong><span className="row-sub"><i className="specialty-tag">{doc.specialty}</i><span className="snippet-inline">{parts.map((p,i)=>terms.some(t=>new RegExp(`^${t}$`,"i").test(p))?<mark key={i}>{p}</mark>:<span key={i}>{p}</span>)}</span></span></span>
    <span className="row-score"><span className="tiny-meter"><i style={{width:`${doc.cosine_similarity*100}%`}}/></span><b>{doc.cosine_similarity.toFixed(2)}</b></span><span className="row-score"><span className="tiny-meter priority"><i style={{width:`${doc.priority_score*100}%`}}/></span><b>{doc.priority_score.toFixed(2)}</b></span>
  </div>
}

export function SearchDashboard(){
  const [query,setQuery]=useState("");const [boxesCount,setBoxesCount]=useState(2);const [topK,setTopK]=useState(5);
  const [response,setResponse]=useState<SearchResponse|null>(null);const [selected,setSelected]=useState<ClinicalDocument|null>(mockDocuments[0]);
  const [loading,setLoading]=useState(false);const [error,setError]=useState("");const [copied,setCopied]=useState(false);const [recent,setRecent]=useState<string[]>([]);const [selectedBox,setSelectedBox]=useState<number|null>(null);
  useEffect(()=>{const params=new URLSearchParams(window.location.search);const initial=params.get("box");if(initial!==null)setSelectedBox(Number(initial));const onBox=(event:Event)=>{const id=(event as CustomEvent<number>).detail;setSelectedBox(id);setResponse(null)};window.addEventListener("vista:box-filter",onBox);return()=>window.removeEventListener("vista:box-filter",onBox)},[]);
  const search=async(e?:FormEvent)=>{e?.preventDefault();if(!query.trim()){setError("Enter a clinical phrase to search.");return}setError("");setLoading(true);try{const data=await searchReports(query.trim(),topK,boxesCount);setResponse(data);const first=data.documents.find(d=>selectedBox===null||d.box_id===selectedBox)??data.documents[0]??null;setSelected(first);setRecent(prev=>[query.trim(),...prev.filter(item=>item!==query.trim())].slice(0,5))}catch{setError("Search could not be completed. Please try again.")}finally{setLoading(false)}};
  const matched=useMemo(()=>response?.matched_boxes.filter(b=>selectedBox===null||b.box_id===selectedBox)??[],[response,selectedBox]);
  const resultDocs=useMemo(()=>response?.documents.filter(d=>selectedBox===null||d.box_id===selectedBox)??[],[response,selectedBox]);
  const initialDocs=useMemo(()=>mockDocuments.filter(d=>selectedBox===null||d.box_id===selectedBox),[selectedBox]);
  const setActive=(doc:ClinicalDocument)=>setSelected(doc);
  useEffect(()=>{if(!response)return;const onKeys=(e:KeyboardEvent)=>{if(e.key==="Escape"){setSelected(null);return}if(e.key!=="ArrowDown"&&e.key!=="ArrowUp")return;const index=resultDocs.findIndex(d=>d.doc_id===selected?.doc_id);const next=e.key==="ArrowDown"?Math.min(resultDocs.length-1,index+1):Math.max(0,index<=0?0:index-1);if(resultDocs[next]){e.preventDefault();setSelected(resultDocs[next])}};window.addEventListener("keydown",onKeys);return()=>window.removeEventListener("keydown",onKeys)},[response,resultDocs,selected]);
  const handleBox=(id:number)=>setSelectedBox(selectedBox===id?null:id);
  const previewDoc=selected??initialDocs[0]??mockDocuments[0];
  const preview=<aside className="card preview-pane"><div className="preview-head"><div><div className="panel-label">DOCUMENT PREVIEW</div><h2>{previewDoc.title}</h2></div><button className="copy-button" onClick={async()=>{await navigator.clipboard?.writeText(previewDoc.full_text);setCopied(true);setTimeout(()=>setCopied(false),1300)}} aria-label="Copy report text">{copied?<Check size={14}/>:<Copy size={14}/>}<span>{copied?"Copied":"Copy"}</span></button></div>
    <div className="preview-meta"><span className="mono">{previewDoc.doc_id}</span><span className="specialty-tag">{previewDoc.specialty}</span><button className="box-tag" onClick={()=>handleBox(previewDoc.box_id)}><i className="color-dot" style={{background:boxes[previewDoc.box_id]?.color}}/>Box {previewDoc.box_id+1} · {boxes[previewDoc.box_id]?.label}</button></div>
    <div className="preview-body"><div className="panel-label">CLINICAL NOTE</div><p>{previewDoc.full_text}</p></div><div className="preview-foot"><span>Similarity <b>{previewDoc.cosine_similarity.toFixed(2)}</b></span><span>Priority <b>{previewDoc.priority_score.toFixed(2)}</b></span></div>
  </aside>;
  const startSearch=(value:string)=>{setQuery(value);setError("");};
  return <div className="search-workspace">
    <div className="search-toolbar"><form className="workspace-search" onSubmit={search}><Search size={16} className="search-muted"/><input value={query} onChange={e=>setQuery(e.target.value)} aria-label="Search clinical reports" placeholder="Search by diagnosis, symptom, or clinical phrase…"/><QueryOptions boxesCount={boxesCount} setBoxesCount={setBoxesCount} topK={topK} setTopK={setTopK}/><span className="toolbar-key">Ctrl K</span><button type="submit" className="run-button" disabled={loading}>{loading?<span className="mini-spinner"/>:<><span>Run</span><ArrowRight size={14}/></>}</button></form>
      <div className="query-links"><span>Try</span>{examples.map(text=><button key={text} onClick={()=>startSearch(text)}>{text}</button>)}</div>{error&&<div className="error-line">{error}</div>}
    </div>
    {loading?<Skeleton/>:<div className="workspace-grid"><section className="workspace-center">
      {response?<>
        <div className="results-topline"><h1>Search results{selectedBox!==null&&<button className="filter-pill" onClick={()=>setSelectedBox(null)}>Box {selectedBox+1} <X size={11}/></button>}</h1><span className={`latency-readout ${response.latency_ms>=2000?"slow":""}`}>{resultDocs.length} results · {(response.latency_ms/1000).toFixed(2)}s</span></div>
        <section className="matched-section"><div className="section-heading"><h2>Matched boxes</h2><span>{matched.length} groups</span></div>{matched.length?<div className="matched-strip">{matched.map(box=><button key={box.box_id} className={`matched-box ${selectedBox===box.box_id?"active":""}`} onClick={()=>handleBox(box.box_id)}><i className="box-color-bar" style={{background:boxes[box.box_id]?.color}}/><span className="matched-box-name">{box.label}</span><b className="mono score-green">{Math.round(box.similarity*100)}%</b><span className="tiny-meter box-meter"><i style={{width:`${box.similarity*100}%`}}/></span><span className="matched-keywords">{box.keywords.slice(0,3).join(" · ")}</span></button>)}</div>:<div className="inline-empty">No matching boxes for this filter.</div>}</section>
        <div className="section-heading result-list-heading"><h2>Ranked reports</h2><span className="list-hint">Use ↑ ↓ to move · Enter to select</span></div>
        <div className="result-table-head"><span>#</span><span>REPORT</span><span>SIMILARITY</span><span>PRIORITY</span></div>
        <div className="result-list" role="listbox" aria-label="Ranked report results">{resultDocs.map((doc,index)=><SearchRow key={doc.doc_id} doc={doc} index={index} query={query} selected={previewDoc.doc_id===doc.doc_id} onSelect={()=>setActive(doc)} onKey={key=>{const next=Math.max(0,Math.min(resultDocs.length-1,index+(key==="ArrowDown"?1:-1)));if(resultDocs[next])setSelected(resultDocs[next])}}/>)}{!resultDocs.length&&<div className="inline-empty">No reports matched this description. Try a broader phrase.</div>}</div>
      </>:<>
        <div className="results-topline"><h1>{selectedBox===null?"Recent searches":"Browse by box"}</h1>{selectedBox!==null&&<button className="clear-box" onClick={()=>setSelectedBox(null)}>Clear filter</button>}</div>
        <section className="initial-section"><div className="section-heading"><h2>Recent searches</h2><span>{recent.length?`${recent.length} saved locally`:"Recent activity"}</span></div><div className="recent-list">{(recent.length?recent:examples.slice(0,3)).map(text=><button key={text} onClick={()=>startSearch(text)}><Search size={13}/><span>{text}</span><ArrowRight size={13}/></button>)}</div></section>
        <section className="initial-section"><div className="section-heading"><h2>Browse by box</h2><span>{selectedBox===null?"12 semantic groups":`Box ${selectedBox+1} selected`}</span></div><div className="browse-grid">{boxes.map(box=><button key={box.box_id} className={`browse-box ${selectedBox===box.box_id?"active":""}`} onClick={()=>handleBox(box.box_id)}><div className="browse-title"><i className="color-dot" style={{background:box.color}}/><strong>{box.label}</strong><span className="mono">{box.doc_count}</span></div><span className="browse-keywords">{box.keywords.slice(0,3).join(" · ")}</span></button>)}</div></section>
        <section className="initial-section"><div className="section-heading"><h2>{selectedBox===null?"Most accessed documents":"Reports in this box"}</h2><span>Priority ranked</span></div><div className="result-list">{initialDocs.slice(0,6).sort((a,b)=>b.priority_score-a.priority_score).map((doc,index)=><SearchRow key={doc.doc_id} doc={doc} index={index} selected={previewDoc.doc_id===doc.doc_id} onSelect={()=>setActive(doc)} onKey={()=>{}}/>)}</div></section>
      </>}
    </section>{preview}</div>}
  </div>;
}
