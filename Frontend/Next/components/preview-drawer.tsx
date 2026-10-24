"use client";
import { useEffect } from "react";
import { Copy, X } from "lucide-react";
import type { ClinicalDocument } from "@/lib/types";
import { boxes } from "@/mocks/data";

export function PreviewDrawer({doc,onClose}:{doc:ClinicalDocument|null;onClose:()=>void}){
  useEffect(()=>{if(!doc)return;const onKey=(e:KeyboardEvent)=>{if(e.key==="Escape")onClose()};window.addEventListener("keydown",onKey);return()=>window.removeEventListener("keydown",onKey)},[doc,onClose]);
  if(!doc)return null;const box=boxes[doc.box_id];
  return <div className="drawer-backdrop" onMouseDown={onClose}><aside className="drawer" role="dialog" aria-modal="true" aria-label="Document preview" onMouseDown={e=>e.stopPropagation()}>
    <div className="drawer-top"><span className="eyebrow">REPORT PREVIEW</span><button className="icon-plain" onClick={onClose} aria-label="Close preview"><X size={15}/></button></div>
    <div style={{display:"flex",justifyContent:"space-between",gap:16,alignItems:"flex-start"}}><h2 style={{margin:"0 0 13px"}}>{doc.title}</h2><button className="preview-copy" onClick={()=>navigator.clipboard?.writeText(doc.full_text)}><Copy size={12}/> Copy</button></div>
    <div className="meta-row"><span className="meta-pill mono">{doc.doc_id}</span><span className="meta-pill">{doc.specialty}</span><span className="meta-pill" style={{color:box?.color}}>Box {doc.box_id+1} · {box?.label}</span></div>
    <div className="score-lines" style={{margin:"20px 0"}}><div><div className="score-line-head"><span>Semantic similarity</span><b>{Math.round(doc.cosine_similarity*100)}%</b></div><div className="progress"><span style={{width:`${doc.cosine_similarity*100}%`}}/></div></div><div><div className="score-line-head"><span>Priority score</span><b>{doc.priority_score.toFixed(2)}</b></div><div className="progress"><span style={{width:`${doc.priority_score*100}%`}}/></div></div></div>
    <div className="eyebrow" style={{marginBottom:11}}>CLINICAL NOTE</div><div className="report-text">{doc.full_text}</div>
  </aside></div>
}
