"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ChevronUp, LogIn, LogOut, Moon, Sun, X, FlaskConical } from "lucide-react";
import { NAV_ITEMS, isActive } from "@/components/navigation/nav-items";
import { useSession } from "@/features/auth/SessionProvider";
import { useNotifications } from "@/features/notifications/useNotifications";
import { useApiHealth } from "@/hooks/useApiHealth";
import { initials } from "@/lib/formatters";
import { useDemo } from "@/providers/DemoProvider";
import { useTheme } from "@/providers/ThemeProvider";
import { LogoMark, Wordmark } from "./Logo";

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const { theme, toggle } = useTheme();
  const { demo, setDemo } = useDemo();
  const { user, status, logout } = useSession();
  const { unread } = useNotifications();
  const health = useApiHealth(!demo);
  const [menu, setMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menu) return;
    const onDoc = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenu(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMenu(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [menu]);

  return (
    <aside className={`sidebar ${open ? "sidebar-open" : ""}`} aria-label="Primary">
      <div className="sidebar-top">
        <Link href="/dashboard" className="brand" aria-label="VERIFAI home" onClick={onClose}>
          <LogoMark />
          <Wordmark />
        </Link>
        <button className="icon-btn sidebar-close" aria-label="Close navigation" onClick={onClose}>
          <X size={18} aria-hidden />
        </button>
      </div>

      <nav aria-label="Main navigation">
        <ul className="nav-list">
          {NAV_ITEMS.map((item) => {
            const active = isActive(pathname, item);
            const Icon = item.icon;
            const showBadge = item.href === "/notifications" && unread > 0;
            return (
              <li key={item.href}>
                <Link href={item.href} className={`nav-item ${active ? "nav-active" : ""}`} aria-current={active ? "page" : undefined} title={item.label} onClick={onClose}>
                  <Icon size={18} aria-hidden />
                  <span className="nav-label">{item.label}</span>
                  {showBadge && (
                    <span className="nav-badge" aria-label={`${unread} unread`}>
                      {unread}
                    </span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="sidebar-bottom">
        <div className="sidebar-controls">
          <button className="side-control" onClick={toggle} aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}>
            {theme === "light" ? <Moon size={16} aria-hidden /> : <Sun size={16} aria-hidden />}
            <span className="nav-label">{theme === "light" ? "Light theme" : "Dark theme"}</span>
          </button>
          <button className={`side-control ${demo ? "side-control-on" : ""}`} role="switch" aria-checked={demo} onClick={() => setDemo(!demo)} title="Use development fixtures instead of the backend">
            <FlaskConical size={16} aria-hidden />
            <span className="nav-label">Sample data</span>
            <span className="switch" aria-hidden>
              <i />
            </span>
          </button>
          {!demo && (
            <p className={`api-health api-${health}`} role="status">
              <i aria-hidden />
              <span className="nav-label">{health === "checking" ? "Checking API…" : health === "up" ? "API connected" : "API unreachable"}</span>
            </p>
          )}
        </div>

        <div className="profile-menu" ref={menuRef}>
          <button className="profile-btn" aria-haspopup="menu" aria-expanded={menu} onClick={() => setMenu((v) => !v)}>
            <span className="avatar" aria-hidden>
              {initials(user?.displayName ?? "Guest")}
            </span>
            <span className="profile-text nav-label">
              <strong>{user?.displayName ?? "Guest"}</strong>
              <small>{status === "authenticated" ? (demo ? "Sample profile" : "Signed in") : status === "loading" ? "Checking session…" : "Not signed in"}</small>
            </span>
            <ChevronUp size={14} aria-hidden className="nav-label" />
          </button>
          {menu && (
            <div className="menu" role="menu">
              <Link role="menuitem" href="/profile" onClick={() => { setMenu(false); onClose(); }}>
                View profile
              </Link>
              {status === "authenticated" && !demo ? (
                <button
                  role="menuitem"
                  onClick={async () => {
                    setMenu(false);
                    await logout();
                  }}
                >
                  <LogOut size={14} aria-hidden /> Log out
                </button>
              ) : (
                !demo && (
                  <Link role="menuitem" href="/login" onClick={() => setMenu(false)}>
                    <LogIn size={14} aria-hidden /> Sign in
                  </Link>
                )
              )}
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
