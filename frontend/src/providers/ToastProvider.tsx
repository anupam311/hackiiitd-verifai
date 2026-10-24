"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";

type Tone = "success" | "error" | "info";
interface Toast {
  id: number;
  tone: Tone;
  title: string;
  body?: string;
}
const Ctx = createContext<{ toast: (t: Omit<Toast, "id">) => void } | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const seq = useRef(0);

  const dismiss = useCallback((id: number) => setItems((xs) => xs.filter((x) => x.id !== id)), []);
  const toast = useCallback(
    (t: Omit<Toast, "id">) => {
      const id = ++seq.current;
      setItems((xs) => [...xs.slice(-3), { ...t, id }]);
      window.setTimeout(() => dismiss(id), t.tone === "error" ? 8000 : 5000);
    },
    [dismiss],
  );
  const value = useMemo(() => ({ toast }), [toast]);

  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="toast-region" role="region" aria-label="Notifications" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast toast-${t.tone}`} role={t.tone === "error" ? "alert" : "status"}>
            {t.tone === "success" ? <CheckCircle2 size={18} aria-hidden /> : t.tone === "error" ? <AlertTriangle size={18} aria-hidden /> : <Info size={18} aria-hidden />}
            <div>
              <strong>{t.title}</strong>
              {t.body && <p>{t.body}</p>}
            </div>
            <button className="icon-btn" aria-label="Dismiss notification" onClick={() => dismiss(t.id)}>
              <X size={14} aria-hidden />
            </button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useToast() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useToast must be used within ToastProvider");
  return v.toast;
}
