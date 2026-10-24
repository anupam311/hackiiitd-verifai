"use client";

import { ChevronRight } from "lucide-react";
import { Fragment, useState } from "react";
import type { Claim, SourceObservation } from "@/types";
import { EvidenceExcerpt } from "@/components/evidence/EvidenceExcerpt";
import { formatDate } from "@/lib/date-utils";
import { CLAIM_TYPE_LABEL } from "@/lib/formatters";
import { ClaimStatusBadge } from "./StatusBadges";

function ClaimDetail({ claim, sources }: { claim: Claim; sources: SourceObservation[] }) {
  const byId = new Map(sources.map((s) => [s.id, s]));
  return (
    <div className="claim-detail">
      <dl className="kv">
        <div>
          <dt>Original claim wording</dt>
          <dd>{claim.originalWording ?? <span className="muted">Not recorded</span>}</dd>
        </div>
        <div>
          <dt>Normalised value</dt>
          <dd>{claim.normalizedValue ?? <span className="muted">None — not determined</span>}</dd>
        </div>
      </dl>
      <p className="claim-explain">
        <strong>Why this status:</strong> {claim.explanation}
      </p>
      {claim.nextStep && (
        <p className="claim-next">
          <strong>Suggested next step:</strong> {claim.nextStep}
        </p>
      )}
      {claim.evidence.length > 0 ? (
        <div className="evidence-list">
          <h4>Evidence ({claim.evidence.length})</h4>
          {claim.evidence.map((e, i) => (
            <EvidenceExcerpt key={`${e.sourceId}-${i}`} evidence={e} source={byId.get(e.sourceId)} />
          ))}
        </div>
      ) : (
        <p className="muted small">No evidence was retrieved for this claim. That is a gap in coverage, not proof either way.</p>
      )}
    </div>
  );
}

/**
 * Claim-by-claim verification table.
 * `compact` mirrors the dashboard card (claim · finding · status); `full` adds expandable evidence.
 * On narrow screens rows stack into labelled cards.
 */
export function ClaimTable({ claims, sources, compact = false }: { claims: Claim[]; sources: SourceObservation[]; compact?: boolean }) {
  const [open, setOpen] = useState<Set<string>>(new Set());
  const toggle = (id: string) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  if (claims.length === 0) return <p className="muted">No claims have been extracted for this opportunity yet.</p>;

  return (
    <div className="table-wrap">
      <table className={`table claim-table ${compact ? "claim-table-compact" : ""}`}>
        <caption className="sr-only">Claim-level verification results</caption>
        <thead>
          <tr>
            <th scope="col">Claim</th>
            <th scope="col">Source finding</th>
            <th scope="col">Status</th>
            {!compact && (
              <th scope="col">
                <span className="sr-only">Evidence</span>
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {claims.map((c) => {
            const expanded = open.has(c.id);
            return (
              <Fragment key={c.id}>
                <tr className={expanded ? "row-open" : undefined}>
                  <th scope="row" data-label="Claim">
                    {CLAIM_TYPE_LABEL[c.type]}
                  </th>
                  <td data-label="Source finding">{c.normalizedValue ? (/^\d{4}-\d{2}-\d{2}$/.test(c.normalizedValue) ? formatDate(c.normalizedValue) : c.normalizedValue) : <span className="muted">Not found in retrieved sources</span>}</td>
                  <td data-label="Status">
                    <ClaimStatusBadge status={c.status} />
                  </td>
                  {!compact && (
                    <td className="cell-action">
                      <button className="row-toggle" aria-expanded={expanded} aria-controls={`claim-${c.id}`} onClick={() => toggle(c.id)}>
                        <ChevronRight size={15} aria-hidden className={expanded ? "rot90" : ""} />
                        <span>{expanded ? "Hide evidence" : `Evidence${c.evidence.length ? ` (${c.evidence.length})` : ""}`}</span>
                      </button>
                    </td>
                  )}
                </tr>
                {!compact && expanded && (
                  <tr className="row-detail" id={`claim-${c.id}`}>
                    <td colSpan={4}>
                      <ClaimDetail claim={c} sources={sources} />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
