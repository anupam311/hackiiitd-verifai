import { AlertTriangle, Inbox, RefreshCw, Info } from "lucide-react";
import type { ReactNode } from "react";
import { describeError } from "@/lib/api-errors";
import { Button } from "./Button";

export function EmptyState({ title, children, action, icon }: { title: string; children?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="empty-state" role="status">
      <div className="empty-icon" aria-hidden>
        {icon ?? <Inbox size={22} />}
      </div>
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action && <div className="empty-action">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry, title }: { error: unknown; onRetry?: () => void; title?: string }) {
  const d = describeError(error);
  return (
    <div className="error-state" role="alert">
      <AlertTriangle size={22} aria-hidden />
      <div>
        <h3>{title ?? d.title}</h3>
        <p>{d.message}</p>
        {d.retryable && onRetry && (
          <Button size="sm" icon={<RefreshCw size={14} aria-hidden />} onClick={onRetry}>
            Try again
          </Button>
        )}
      </div>
    </div>
  );
}

export function Notice({ tone = "info", title, children }: { tone?: "info" | "warn" | "danger" | "success"; title?: string; children: ReactNode }) {
  return (
    <div className={`notice notice-${tone}`} role={tone === "danger" ? "alert" : "note"}>
      {tone === "info" ? <Info size={17} aria-hidden /> : <AlertTriangle size={17} aria-hidden />}
      <div>
        {title && <strong>{title}</strong>}
        <p>{children}</p>
      </div>
    </div>
  );
}

export function SkeletonCards({ count = 3, label = "Loading" }: { count?: number; label?: string }) {
  return (
    <div className="stack-sm" aria-busy="true" aria-label={label} role="status">
      <span className="sr-only">{label}…</span>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="skeleton-card" aria-hidden>
          <div className="skeleton sk-avatar" />
          <div className="sk-lines">
            <div className="skeleton sk-line w60" />
            <div className="skeleton sk-line w40" />
            <div className="skeleton sk-line w90" />
          </div>
        </div>
      ))}
    </div>
  );
}
