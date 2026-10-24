"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { usePathname } from "next/navigation";
import { Activity, Files, Search, Shapes, X } from "lucide-react";

const technicianDestinations=[{name:"Technician ingestion pipeline",href:"/technician",Icon:Files},{name:"Search medical reports",href:"/search",Icon:Search},{name:"Explore semantic boxes",href:"/boxes",Icon:Shapes},{name:"View analytics",href:"/analytics",Icon:Activity},{name:"Browse documents",href:"/documents",Icon:Files}];
const doctorDestinations=[{name:"Doctor clinical workspace",href:"/doctor",Icon:Search},{name:"Browse patient reports",href:"/doctor/reports",Icon:Files}];
export function CommandPalette(){
  const [open,setOpen]=useState(false);const [q,setQ]=useState("");const router=useRouter();const pathname=usePathname();const destinations=pathname.startsWith("/doctor")?doctorDestinations:technicianDestinations;
  useEffect(()=>{const openPalette=()=>setOpen(true);const keys=(e:KeyboardEvent)=>{if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==="k"){e.preventDefault();setOpen(v=>!v)}if(e.key==="Escape")setOpen(false)};window.addEventListener("vista:palette",openPalette);window.addEventListener("keydown",keys);return()=>{window.removeEventListener("vista:palette",openPalette);window.removeEventListener("keydown",keys)}},[]);
  if(!open)return null;
  const matches=destinations.filter(x=>x.name.toLowerCase().includes(q.toLowerCase()));
  return <div className="drawer-backdrop" style={{justifyContent:"center",alignItems:"flex-start",paddingTop:"16vh"}} onMouseDown={()=>setOpen(false)}><div className="card" style={{width:"min(540px,calc(100% - 28px))",overflow:"hidden"}} onMouseDown={e=>e.stopPropagation()}>
    <div style={{display:"flex",alignItems:"center",gap:10,padding:"13px 15px",borderBottom:"1px solid var(--border)"}}><Search size={16} color="var(--muted)"/><input autoFocus value={q} onChange={e=>setQ(e.target.value)} placeholder="Search pages and reports…" style={{flex:1,border:0,outline:0,background:"transparent",color:"var(--foreground)"}}/><button className="icon-plain" aria-label="Close" onClick={()=>setOpen(false)}><X size={15}/></button></div>
    <div style={{padding:8}}>{matches.map(({name,href,Icon})=><button key={href} className="box-list-item" style={{display:"flex",alignItems:"center",gap:10,color:"var(--muted)"}} onClick={()=>{setOpen(false);router.push(href)}}><Icon size={15}/>{name}<span style={{marginLeft:"auto"}}>↵</span></button>)}</div>
  </div></div>
}
