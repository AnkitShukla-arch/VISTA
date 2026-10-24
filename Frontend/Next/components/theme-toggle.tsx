"use client";
import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme(); const [ready,setReady]=useState(false);
  useEffect(()=>setReady(true),[]);
  return <button className="top-action icon-button" aria-label="Toggle color theme" title="Toggle theme" onClick={()=>setTheme((ready&&theme==="dark")?"light":"dark")}>
    {ready&&theme==="dark"?<Sun size={16}/>:<Moon size={16}/>}</button>;
}
