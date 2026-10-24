"use client";
import { useEffect, useMemo, useState } from "react";
import { ScatterMap } from "@/components/scatter-map";
import { PreviewDrawer } from "@/components/preview-drawer";
import { getBoxes,getDocument,getDocuments,getProjection } from "@/lib/api";
import { boxes as mockBoxes } from "@/mocks/data";
import type { Box,ClinicalDocument,ProjectionPoint } from "@/lib/types";

export default function BoxesPage(){
  const [points,setPoints]=useState<ProjectionPoint[]>([]);const [allBoxes,setAllBoxes]=useState<Box[]>(mockBoxes);const [active,setActive]=useState<number|null>(0);const [preview,setPreview]=useState<ClinicalDocument|null>(null);const [docs,setDocs]=useState<ClinicalDocument[]>([]);
  useEffect(()=>{getProjection().then(setPoints);getBoxes().then(setAllBoxes);const initial=new URLSearchParams(window.location.search).get("box");if(initial!==null)setActive(Number(initial));const handler=(e:Event)=>setActive((e as CustomEvent<number>).detail);window.addEventListener("vista:box-filter",handler);return()=>window.removeEventListener("vista:box-filter",handler)},[]);
  useEffect(()=>{getDocuments({box:active===null?undefined:String(active),page_size:8}).then(r=>setDocs(r.items))},[active]);
  const selected=active===null?null:allBoxes.find(b=>b.box_id===active)??allBoxes[0];
  const docsForBox=useMemo(()=>docs,[docs]);
  return <div className="page explorer-page"><header className="page-heading"><div className="eyebrow">SEMANTIC WORKSPACE / EXPLORER</div><h1>Box Explorer</h1><p>Inspect how clinical reports cluster by meaning. Select a box to see its reports.</p></header>
    <div className="explorer-layout"><section className="card map-panel"><div className="panel-topline"><div><h2>Clinical embedding map</h2><span>Principal component projection · {points.length.toLocaleString()} reports</span></div><div className="map-legend-summary"><i className="pulse"/>12 active boxes</div></div><ScatterMap points={points} activeBox={active} onBox={setActive} onPoint={async p=>{const d=await getDocument(p.doc_id);if(d)setPreview(d);else setPreview({doc_id:p.doc_id,title:p.title,specialty:p.specialty,box_id:p.box_id,cosine_similarity:0,priority_score:0,snippet:p.title,full_text:p.title})}}/><div className="map-legend">{allBoxes.map(b=><button key={b.box_id} onClick={()=>setActive(active===b.box_id?null:b.box_id)} className={active===b.box_id?"active":""}><i className="color-dot" style={{background:b.color}}/>{b.label}</button>)}</div><div className="map-hint">Scroll to zoom · drag to pan · select a point to open its report</div></section>
      <aside className="box-detail-panel"><section className="card detail-card"><div className="detail-heading"><i className="color-dot" style={{background:selected?.color}}/><div><span className="panel-label">{selected?"SELECTED BOX":"ALL BOXES"}</span><h2>{selected?.label??"Clinical reports"}</h2></div></div><div className="detail-count"><strong>{selected?.doc_count??1000}</strong><span>{selected?"reports in this cluster":"reports across 12 boxes"}</span></div>{selected&&<><div className="panel-label">KEYWORDS</div><div className="detail-keywords">{selected.keywords.map(k=><span key={k}>{k}</span>)}</div></>}<div className="detail-divider"/><div className="section-heading"><h2>Documents</h2><span>{docsForBox.length} shown</span></div><div className="doc-list">{docsForBox.map(d=><button className="doc-mini" key={d.doc_id} onClick={()=>setPreview(d)}><strong>{d.title}</strong><small>{d.specialty} · {d.doc_id}</small></button>)}</div></section>
        <section className="card detail-card size-card"><div className="section-heading"><h2>Box sizes</h2><span>reports</span></div><div className="size-list">{allBoxes.map(b=><button key={b.box_id} onClick={()=>setActive(b.box_id)} className={active===b.box_id?"active":""}><span>{b.label}</span><i><b style={{width:`${b.doc_count/1.16}%`,background:b.color}}/></i><small>{b.doc_count}</small></button>)}</div></section></aside></div>
    <PreviewDrawer doc={preview} onClose={()=>setPreview(null)}/>
  </div>
}
