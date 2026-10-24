import { motion } from "framer-motion";
import type { Box, ClinicalDocument } from "@/lib/types";

export function BoxCard({box,similarity,compact=false}:{box:Box;similarity?:number;compact?:boolean}){
  return <motion.article className="card box-card" initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} transition={{duration:.25}}>
    <div className="box-top"><div className="box-name"><i className="color-dot" style={{background:box.color}}/><span>{box.label}</span></div><span className="score">{similarity===undefined?`${box.doc_count} docs`:`${Math.round(similarity*100)}%`}</span></div>
    {similarity!==undefined&&<div className="progress"><span style={{width:`${Math.max(2,similarity*100)}%`}}/></div>}
    {!compact&&<div className="keyword-row">{box.keywords.slice(0,4).map(k=><span className="keyword" key={k}>{k}</span>)}</div>}
  </motion.article>
}
export function ResultCard({doc,rank,selected,query,onClick}:{doc:ClinicalDocument;rank:number;selected:boolean;query:string;onClick:()=>void}){
  const terms=query.trim().split(/\s+/).filter(t=>t.length>3).map(t=>t.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"));
  const parts=terms.length?doc.snippet.split(new RegExp(`(${terms.join("|")})`,"ig")):[doc.snippet];
  return <motion.article layout initial={{opacity:0,y:10}} animate={{opacity:1,y:0}} transition={{duration:.22,delay:Math.min(rank*.035,.2)}} className={`card result-card ${selected?"selected":""}`} role="button" tabIndex={0} onClick={onClick} onKeyDown={e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();onClick()}}}>
    <div className="result-title-row"><span className="rank">{String(rank).padStart(2,"0")}</span><div style={{flex:1}}><h3 className="result-title">{doc.title}</h3><span className="specialty">{doc.specialty}</span></div><span className="doc-id">{doc.doc_id}</span></div>
    <p className="snippet">{parts.map((part,i)=>terms.some(term=>new RegExp(`^${term}$`,"i").test(part))?<mark key={i}>{part}</mark>:<span key={i}>{part}</span>)}</p><div className="score-lines"><div><div className="score-line-head"><span>Cosine similarity</span><b>{Math.round(doc.cosine_similarity*100)}%</b></div><div className="progress"><span style={{width:`${doc.cosine_similarity*100}%`}}/></div></div><div><div className="score-line-head"><span>Priority score</span><b>{doc.priority_score.toFixed(2)}</b></div><div className="progress"><span style={{width:`${doc.priority_score*100}%`}}/></div></div></div>
  </motion.article>
}
