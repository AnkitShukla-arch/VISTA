"use client";
import { useEffect, useMemo, useState } from "react";
import { ArrowDownUp, ChevronLeft, ChevronRight, Search, SlidersHorizontal } from "lucide-react";
import { getDocuments } from "@/lib/api";
import { boxes } from "@/mocks/data";
import { PreviewDrawer } from "@/components/preview-drawer";
import type { ClinicalDocument } from "@/lib/types";

const PAGE_SIZE=12;
function DocumentsView({doctorMode=false}:{doctorMode?:boolean}){
  const [items,setItems]=useState<ClinicalDocument[]>([]);const [total,setTotal]=useState(0);const [q,setQ]=useState("");const [box,setBox]=useState("");const [specialty,setSpecialty]=useState("");const [page,setPage]=useState(1);const [sort,setSort]=useState<"title"|"specialty"|"doc_id">("title");const [asc,setAsc]=useState(true);const [preview,setPreview]=useState<ClinicalDocument|null>(null);
  const [dense,setDense]=useState(true);
  useEffect(()=>{const timer=setTimeout(()=>{getDocuments({box,specialty,q,page,page_size:PAGE_SIZE}).then(r=>{setItems(r.items);setTotal(r.total)})},180);return()=>clearTimeout(timer)},[box,specialty,q,page]);
  useEffect(()=>{const handler=(e:Event)=>{setBox(String((e as CustomEvent<number>).detail));setPage(1)};window.addEventListener("vista:box-filter",handler);return()=>window.removeEventListener("vista:box-filter",handler)},[]);
  const specialties=useMemo(()=>[...new Set(items.map(d=>d.specialty))].sort(),[items]);
  const filtered=useMemo(()=>items.filter(d=>(!box||d.box_id===Number(box))&&(!specialty||d.specialty===specialty)&&(!q||`${d.title} ${d.doc_id} ${d.snippet}`.toLowerCase().includes(q.toLowerCase()))).sort((a,b)=>{const cmp=String(a[sort]).localeCompare(String(b[sort]));return asc?cmp:-cmp}),[items,box,specialty,q,sort,asc]);
  const pages=Math.max(1,Math.ceil(total/PAGE_SIZE));const rows=filtered;
  const sortBy=(key:typeof sort)=>{if(sort===key)setAsc(!asc);else{setSort(key);setAsc(true)}};
  return <div className="page"><header className="page-heading"><div className="eyebrow">{doctorMode?"DOCTOR WORKSPACE / REPORTS":"REPORT COLLECTION / 03"}</div><h1>{doctorMode?"Patient reports":"Documents"}</h1><p>{doctorMode?"Browse and inspect extracted clinical reports.":"Browse, filter, and inspect the reports in your clinical workspace."}</p></header>
    <div className="table-tools"><label style={{position:"relative",flex:1,display:"flex",alignItems:"center"}}><Search size={14} style={{position:"absolute",left:11,color:"var(--muted)"}}/><input className="filter-input" style={{paddingLeft:33}} placeholder="Filter by title, ID, or clinical phrase…" value={q} onChange={e=>{setQ(e.target.value);setPage(1)}}/></label><select className="filter-select" aria-label="Filter by box" value={box} onChange={e=>{setBox(e.target.value);setPage(1)}}><option value="">All boxes</option>{boxes.map(b=><option key={b.box_id} value={b.box_id}>{b.label}</option>)}</select><select className="filter-select" aria-label="Filter by specialty" value={specialty} onChange={e=>{setSpecialty(e.target.value);setPage(1)}}><option value="">All specialties</option>{specialties.map(s=><option key={s}>{s}</option>)}</select><button className="page-btn" onClick={()=>setDense(!dense)}>{dense?"Comfortable rows":"Compact rows"}</button><button className="page-btn" onClick={()=>{setQ("");setBox("");setSpecialty("")}}><SlidersHorizontal size={13} style={{verticalAlign:"-2px",marginRight:6}}/>Reset</button></div>
    <div className={`table-wrap ${dense?"dense":"comfortable"}`}><table><thead><tr><th><button onClick={()=>sortBy("doc_id")} style={{background:"none",border:0,color:"inherit",cursor:"pointer"}}>DOCUMENT ID <ArrowDownUp size={10}/></button></th><th><button onClick={()=>sortBy("title")} style={{background:"none",border:0,color:"inherit",cursor:"pointer"}}>REPORT TITLE <ArrowDownUp size={10}/></button></th><th><button onClick={()=>sortBy("specialty")} style={{background:"none",border:0,color:"inherit",cursor:"pointer"}}>SPECIALTY <ArrowDownUp size={10}/></button></th><th>SEMANTIC BOX</th><th>SIMILARITY</th></tr></thead><tbody>{rows.map(d=><tr key={d.doc_id} onClick={()=>setPreview(d)}><td className="doc-id">{d.doc_id}</td><td style={{maxWidth:370,fontWeight:520}}>{d.title}</td><td><span className="specialty" style={{margin:0}}>{d.specialty}</span></td><td><span style={{display:"inline-flex",alignItems:"center",gap:6,color:"var(--muted)"}}><i className="color-dot" style={{background:boxes[d.box_id]?.color,width:6,height:6}}/>{boxes[d.box_id]?.label}</span></td><td className="mono">{Math.round(d.cosine_similarity*100)}%</td></tr>)}</tbody></table>{rows.length===0&&<div className="empty-state" style={{border:0}}>No documents match these filters.</div>}</div>
    <div className="pagination"><span>{total?`${(page-1)*PAGE_SIZE+1}–${Math.min(page*PAGE_SIZE,total)} of ${total} reports`:"0 reports"}</span><div style={{display:"flex",gap:6,alignItems:"center"}}><button className="page-btn" disabled={page<=1} onClick={()=>setPage(p=>p-1)} aria-label="Previous page"><ChevronLeft size={14}/></button><span className="mono">{page} / {pages}</span><button className="page-btn" disabled={page>=pages} onClick={()=>setPage(p=>p+1)} aria-label="Next page"><ChevronRight size={14}/></button></div></div>
    <PreviewDrawer doc={preview} onClose={()=>setPreview(null)}/>
  </div>
}

export default function DocumentsPage(){ return <DocumentsView />; }
