"use client";
import { usePathname } from "next/navigation";
import { Command, Search } from "lucide-react";
const titles:Record<string,string>={"/":"Choose workspace","/technician":"Technician · Ingestion","/doctor":"Doctor · Clinical workspace","/doctor/reports":"Doctor · Reports","/search":"Technician · Search","/boxes":"Box Explorer","/analytics":"Analytics","/documents":"Documents"};
export function Topbar(){
  const pathname=usePathname();const title=titles[pathname]??"Workspace";
  return <header className="topbar"><div className="crumb"><span>VISTA</span><span className="crumb-sep">/</span><strong>{title}</strong></div><button className="command-trigger" onClick={()=>window.dispatchEvent(new Event("vista:palette"))}><Search size={14}/><span>Jump to…</span><kbd>Ctrl K</kbd></button></header>
}
