import { Globe } from "lucide-react";
import type { SourceObservation } from "@/types";
import { Badge, type Tone } from "@/components/ui/Badge";
import { ExternalLink } from "@/components/ui/Button";
import { formatDateTime } from "@/lib/date-utils";
import { SOURCE_TYPE_LABEL } from "@/lib/formatters";

const OUTCOME: Record<SourceObservation["outcome"], { label: string; tone: Tone }> = {
  ok: { label: "Retrieved", tone: "green" },
  partial: { label: "Partially retrieved", tone: "amber" },
  blocked: { label: "Blocked", tone: "gray" },
  timeout: { label: "Timed out", tone: "gray" },
  not_found: { label: "Not found", tone: "gray" },
  error: { label: "Retrieval error", tone: "gray" },
};

const AUTHORITATIVE = new Set(["official", "institution", "employer"]);

export function SourceCard({ source }: { source: SourceObservation }) {
  const outcome = OUTCOME[source.outcome];
  return (
    <article className={`source-card ${source.outcome !== "ok" ? "source-card-failed" : ""}`}>
      <div className="source-card-head">
        <span className="source-icon" aria-hidden>
          <Globe size={16} />
        </span>
        <div>
          <h3>{source.name}</h3>
          <p className="muted small">{source.domain}</p>
        </div>
      </div>
      <div className="badge-row">
        <Badge tone={AUTHORITATIVE.has(source.sourceType) ? "green" : "gray"} title="Source type is evidence about authority, not proof that every claim is true.">
          {SOURCE_TYPE_LABEL[source.sourceType]}
        </Badge>
        <Badge tone={outcome.tone}>{outcome.label}</Badge>
        {source.freshness === "stale" && <Badge tone="amber">Possibly stale</Badge>}
      </div>
      <dl className="kv small">
        <div>
          <dt>Retrieved</dt>
          <dd>{formatDateTime(source.retrievedAt)}</dd>
        </div>
        {source.httpStatus ? (
          <div>
            <dt>HTTP status</dt>
            <dd>{source.httpStatus}</dd>
          </div>
        ) : null}
      </dl>
      {source.note && <p className="source-note small">{source.note}</p>}
      <ExternalLink href={source.url}>Inspect original source ↗</ExternalLink>
    </article>
  );
}
