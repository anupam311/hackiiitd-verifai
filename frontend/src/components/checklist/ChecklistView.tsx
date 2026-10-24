"use client";

import { ExternalLink as ExtIcon } from "lucide-react";
import type { ChecklistItem } from "@/types";
import { Button, ExternalLink } from "@/components/ui/Button";
import { GROUP_LABEL, GROUP_ORDER } from "@/features/checklist/build";

export function ChecklistView({ items, isDone, onToggle, onReset }: { items: ChecklistItem[]; isDone: (id: string) => boolean; onToggle: (id: string) => void; onReset: () => void }) {
  const total = items.length;
  const done = items.filter((i) => isDone(i.id)).length;
  const pct = total ? Math.round((done / total) * 100) : 0;

  return (
    <div className="checklist">
      <div className="progress-row">
        <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={done} aria-label="Checklist progress">
          <i style={{ width: `${pct}%` }} />
        </div>
        <span className="small">{done} of {total} done</span>
        <Button size="sm" variant="ghost" onClick={onReset} disabled={done === 0}>Reset</Button>
      </div>
      {GROUP_ORDER.map((g) => {
        const group = items.filter((i) => i.group === g);
        if (group.length === 0) return null;
        return (
          <section key={g} aria-labelledby={`cl-${g}`} className="cl-group">
            <h3 id={`cl-${g}`}>{GROUP_LABEL[g]}</h3>
            <ul>
              {group.map((i) => (
                <li key={i.id} className={isDone(i.id) ? "cl-done" : ""}>
                  <label>
                    <input type="checkbox" checked={isDone(i.id)} onChange={() => onToggle(i.id)} />
                    <span>
                      <strong>{i.label}</strong>
                      {i.detail && <small>{i.detail}</small>}
                    </span>
                  </label>
                  {i.sourceUrl ? (
                    <ExternalLink href={i.sourceUrl} className="link small"><ExtIcon size={12} aria-hidden /> {i.sourceLabel ?? "Source"}</ExternalLink>
                  ) : (
                    <span className="small muted">No source recorded</span>
                  )}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
