"use client";
import { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";
import { CommandPalette } from "./command-palette";
export function AppShell({children}:{children:ReactNode}){
  const pathname=usePathname();
  if(pathname==="/")return <>{children}</>;
  return <div className="app-shell"><Sidebar/><div className="main-shell"><Topbar/><main className="main-content">{children}</main></div><CommandPalette/></div>
}
