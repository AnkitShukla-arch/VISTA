"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Activity, ChevronLeft, ChevronRight, Files, Search, Settings2, Shapes, Stethoscope, Upload } from "lucide-react";
import { getBoxes } from "@/lib/api";
import { boxes as defaults } from "@/mocks/data";
import type { Box } from "@/lib/types";
import { ThemeToggle } from "./theme-toggle";

const technicianLinks = [
  { href: "/technician", label: "Ingestion pipeline", Icon: Upload },
  { href: "/search", label: "Search", Icon: Search },
  { href: "/boxes", label: "Box Explorer", Icon: Shapes },
  { href: "/analytics", label: "Analytics", Icon: Activity },
  { href: "/documents", label: "Documents", Icon: Files },
];
const doctorLinks = [
  { href: "/doctor", label: "Clinical workspace", Icon: Stethoscope },
  { href: "/doctor/reports", label: "Reports", Icon: Files },
];

function BrandMark() {
  return <svg width="19" height="19" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M3 5.2 10 2.8l7 2.4v9.4L10 17l-7-2.4V5.2Z" stroke="currentColor" strokeWidth="1.35"/><path d="M3.5 5.4 10 7.7l6.5-2.3M10 7.7V16" stroke="currentColor" strokeWidth="1.15"/><circle cx="14.7" cy="4.1" r="2" fill="var(--surface)" stroke="currentColor" strokeWidth="1.25"/></svg>;
}

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const isDoctor = pathname.startsWith("/doctor");
  const links = isDoctor ? doctorLinks : technicianLinks;
  const [collapsed, setCollapsed] = useState(false);
  const [allBoxes, setAllBoxes] = useState<Box[]>(defaults);
  useEffect(() => { getBoxes().then(setAllBoxes).catch(() => undefined); }, []);
  const selectBox = (id: number) => {
    if (["/search", "/boxes", "/documents"].includes(pathname)) window.dispatchEvent(new CustomEvent("vista:box-filter", { detail: id }));
    else router.push(`/search?box=${id}`);
  };

  return <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
    <div className="sidebar-brand"><Link href="/" className="brand"><span className="brand-icon"><BrandMark /></span>{!collapsed && <span>VISTA</span>}</Link><button className="collapse-button" aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} onClick={() => setCollapsed(!collapsed)}>{collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}</button></div>
    <nav className="side-nav" aria-label="Workspace navigation">{links.map(({ href, label, Icon }) => <Link title={collapsed ? label : undefined} key={href} href={href} className={`side-link ${pathname === href ? "active" : ""}`}><Icon size={16} />{!collapsed && <span>{label}</span>}</Link>)}</nav>
    {!isDoctor && !collapsed && <><div className="side-section-label"><span>BOXES</span><span className="mono">{allBoxes.length}</span></div><div className="side-boxes">{allBoxes.map(box => <button key={box.box_id} title={`${box.label} · ${box.doc_count} reports`} onClick={() => selectBox(box.box_id)} className="side-box"><i className="color-dot" style={{ background: box.color }} /><span className="side-box-name">{box.label}</span><span className="side-box-count mono">{box.doc_count}</span></button>)}</div></>}
    <div className="sidebar-bottom"><div className={`system-line ${collapsed ? "centered" : ""}`} title={isDoctor ? "Patient report workspace" : "Semantic index ready"}><i className="pulse" />{!collapsed && <span>{isDoctor ? "Report search ready" : "Index ready · 12 boxes · 384-D"}</span>}</div><div className="sidebar-actions"><div title="Theme"><ThemeToggle /></div><Link className="side-link settings-link" href="/" title="Switch workspace"><Settings2 size={16} />{!collapsed && <span>Switch workspace</span>}</Link></div></div>
  </aside>;
}
