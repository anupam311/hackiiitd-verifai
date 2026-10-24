"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { Menu } from "lucide-react";
import { useEffect, useState } from "react";
import { LogoMark } from "./Logo";
import { SampleBanner } from "./SampleBanner";
import { Sidebar } from "./Sidebar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    document.body.classList.add("no-scroll");
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.classList.remove("no-scroll");
    };
  }, [open]);

  return (
    <div className="shell">
      <a href="#main" className="skip-link">
        Skip to main content
      </a>
      <Sidebar open={open} onClose={() => setOpen(false)} />
      {open && <div className="scrim" onClick={() => setOpen(false)} aria-hidden />}
      <div className="shell-main">
        <div className="mobile-bar">
          <button className="icon-btn" aria-label="Open navigation" aria-expanded={open} onClick={() => setOpen(true)}>
            <Menu size={22} aria-hidden />
          </button>
          <Link href="/dashboard" className="mobile-brand" aria-label="VERIFAI home">
            <LogoMark size={26} />
            <strong>VERIFAI</strong>
          </Link>
        </div>
        <SampleBanner />
        <main id="main" className="workspace" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  );
}
