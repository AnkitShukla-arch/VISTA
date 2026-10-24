"use client";
import { useMemo, useRef, useState } from "react";
import type { PointerEvent, WheelEvent } from "react";
import type { ProjectionPoint } from "@/lib/types";
import { boxes } from "@/mocks/data";

export function ScatterMap({points,activeBox,onBox,onPoint}:{points:ProjectionPoint[];activeBox:number|null;onBox:(id:number|null)=>void;onPoint:(point:ProjectionPoint)=>void}){
  const [zoom,setZoom]=useState(1);const [pan,setPan]=useState({x:0,y:0});const [drag,setDrag]=useState<{x:number;y:number;px:number;py:number}|null>(null);const [hover,setHover]=useState<ProjectionPoint|null>(null);const svg=useRef<SVGSVGElement>(null);
  const bounds=useMemo(()=>{const xs=points.map(p=>p.x),ys=points.map(p=>p.y);return {minX:Math.min(...xs)-.25,maxX:Math.max(...xs)+.25,minY:Math.min(...ys)-.25,maxY:Math.max(...ys)+.25}},[points]);
  const W=680,H=390,pad=20,base=(p:ProjectionPoint)=>({x:pad+(p.x-bounds.minX)/(bounds.maxX-bounds.minX)*(W-pad*2),y:H-pad-(p.y-bounds.minY)/(bounds.maxY-bounds.minY)*(H-pad*2)});
  const pos=(p:ProjectionPoint)=>{const b=base(p);return {x:W/2+(b.x-W/2)*zoom+pan.x,y:H/2+(b.y-H/2)*zoom+pan.y}};
  const pointer=(e:PointerEvent<SVGSVGElement>)=>{const r=e.currentTarget.getBoundingClientRect();return {x:(e.clientX-r.left)*W/r.width,y:(e.clientY-r.top)*H/r.height}};
  const start=(e:PointerEvent<SVGSVGElement>)=>{if(e.button!==0)return;const p=pointer(e);setDrag({x:p.x,y:p.y,px:pan.x,py:pan.y});e.currentTarget.setPointerCapture(e.pointerId)};
  const move=(e:PointerEvent<SVGSVGElement>)=>{if(drag){const p=pointer(e);setPan({x:drag.px+p.x-drag.x,y:drag.py+p.y-drag.y})}};
  const wheel=(e:WheelEvent<SVGSVGElement>)=>{e.preventDefault();setZoom(v=>Math.max(.7,Math.min(4,v*(e.deltaY<0?1.12:.9))))};
  return <div style={{position:"relative"}}><svg ref={svg} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Interactive PCA scatter plot of clinical reports" style={{width:"100%",height:"auto",touchAction:"none",cursor:drag?"grabbing":"grab"}} onPointerDown={start} onPointerMove={move} onPointerUp={()=>setDrag(null)} onPointerCancel={()=>setDrag(null)} onWheel={wheel}>
    {[0,1,2,3,4].map(i=><g key={i}><line x1={pad+i*(W-pad*2)/4} y1={pad} x2={pad+i*(W-pad*2)/4} y2={H-pad} stroke="var(--grid)"/><line x1={pad} y1={pad+i*(H-pad*2)/4} x2={W-pad} y2={pad+i*(H-pad*2)/4} stroke="var(--grid)"/></g>)}
    {points.map((p,i)=>{const xy=pos(p);const color=boxes[p.box_id]?.color??"#668";const faded=activeBox!==null&&activeBox!==p.box_id;return <circle key={`${p.doc_id}-${i}`} cx={xy.x} cy={xy.y} r={hover?.doc_id===p.doc_id?5:3.2} fill={color} opacity={faded ? .13 : .72} stroke={hover?.doc_id===p.doc_id?"var(--foreground)":"none"} strokeWidth="1.5" onPointerEnter={()=>setHover(p)} onPointerLeave={()=>setHover(null)} onClick={e=>{e.stopPropagation();onBox(p.box_id);onPoint(p)}}><title>{p.title} · {p.specialty}</title></circle>})}
    <text x={W/2} y={H-3} textAnchor="middle" fill="var(--muted)" fontSize="var(--text-meta)">Principal component 1</text><text x="10" y={H/2} textAnchor="middle" fill="var(--muted)" fontSize="var(--text-meta)" transform={`rotate(-90 10 ${H/2})`}>Principal component 2</text>
  </svg>
    {hover&&<div className="scatter-tooltip" style={{position:"absolute",left:`${Math.min(70,Math.max(3,(pos(hover).x/W)*100))}%`,top:`${Math.max(2,(pos(hover).y/H)*100)}%`,pointerEvents:"none",padding:"7px 9px",border:"1px solid var(--border)",background:"var(--surface)",borderRadius:7,boxShadow:"0 4px 16px #0002",maxWidth:200}}><strong>{hover.title}</strong><div style={{color:"var(--muted)",marginTop:3}}>{hover.specialty} · Box {hover.box_id+1}</div></div>}
    <div style={{position:"absolute",right:7,top:7,display:"flex",gap:4}}><button className="icon-plain" title="Zoom in" onClick={()=>setZoom(v=>Math.min(4,v*1.2))}>+</button><button className="icon-plain" title="Zoom out" onClick={()=>setZoom(v=>Math.max(.7,v/1.2))}>−</button><button className="icon-plain" title="Reset map" onClick={()=>{setZoom(1);setPan({x:0,y:0})}}>↺</button></div>
  </div>
}
