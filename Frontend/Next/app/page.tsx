"use client";

import Link from "next/link";
import { Activity, ArrowRight, BrainCircuit, Database, FileSearch, ScanText, Stethoscope, Upload, Workflow } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";

export default function Home() {
  return <main className="role-page">
    <header className="role-topbar"><Link href="/" className="role-brand"><span className="role-brand-mark">V</span>VISTA</Link><ThemeToggle /></header>
    <section className="role-layout">
      <div className="role-intro">
        <span className="eyebrow">CLINICAL INTELLIGENCE</span>
        <h1>Better insight for <em>better care.</em></h1>
        <p>VISTA connects medical reports with the tools people need to manage clinical data and make informed decisions.</p>
        <div className="role-trust"><span><i className="pulse"/> Secure clinical workspace</span><span>Semantic search across reports</span></div>
      </div>
      <div className="role-options">
        <div className="role-options-heading"><span>CHOOSE YOUR WORKSPACE</span><span>Continue as</span></div>
        <Link className="role-card role-technician" href="/technician">
          <span className="role-icon"><Workflow size={20}/></span>
          <span className="role-card-main"><strong>Technician</strong><span>Manage data and the VISTA pipeline</span></span>
          <ArrowRight size={17} className="role-arrow"/>
          <span className="role-card-features"><span><Upload size={14}/> Ingestion & ETL</span><span><ScanText size={14}/> OCR & extraction</span><span><BrainCircuit size={14}/> Embeddings</span><span><Activity size={14}/> Analytics</span><span><Database size={14}/> Storage & boxes</span></span>
        </Link>
        <Link className="role-card role-doctor" href="/doctor">
          <span className="role-icon"><Stethoscope size={20}/></span>
          <span className="role-card-main"><strong>Doctor</strong><span>Find and review clinical reports</span></span>
          <ArrowRight size={17} className="role-arrow"/>
          <span className="role-card-features"><span><FileSearch size={14}/> Patient report search</span><span><Activity size={14}/> Clear clinical summaries</span><span><Stethoscope size={14}/> Ask in plain language</span></span>
        </Link>
        <p className="role-help">Choose a workspace to continue. You can switch roles at any time.</p>
      </div>
    </section>
    <footer className="role-footer"><span>VISTA Clinical Intelligence</span><span>Medical data workspace</span></footer>
  </main>;
}
