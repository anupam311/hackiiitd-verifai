import type { ClaimEvidence, SourceObservation } from "@/types";
import { Badge } from "@/components/ui/Badge";
import { ExternalLink } from "@/components/ui/Button";
import { formatDateTime } from "@/lib/date-utils";
import { SOURCE_TYPE_LABEL } from "@/lib/formatters";
import { Quote } from "lucide-react";

/** One piece of evidence. The excerpt is shown verbatim from the source record; the UI never writes one. */
export function EvidenceExcerpt({ evidence, source }: { evidence: ClaimEvidence; source: SourceObservation | undefined }) {
  return (
    <figure className="evidence">
      <figcaption>
        <span className="evidence-src">
          <strong>{source?.name ?? "Unknown source"}</strong>
          {source && <Badge tone={source.sourceType === "official" || source.sourceType === "institution" || source.sourceType === "employer" ? "green" : "gray"}>{SOURCE_TYPE_LABEL[source.sourceType]}</Badge>}
        </span>
        <span className="evidence-meta">
          Retrieved {formatDateTime(source?.retrievedAt)}
          {source && (
            <>
              {" · "}
              <ExternalLink href={source.url}>Open source ↗</ExternalLink>
            </>
          )}
        </span>
      </figcaption>
      {evidence.extractedValue && (
        <p className="evidence-value">
          <span>Extracted value</span> {evidence.extractedValue}
        </p>
      )}
      {evidence.excerpt ? (
        <blockquote>
          <Quote size={14} aria-hidden />
          <p>{evidence.excerpt}</p>
          {evidence.locator && <cite>{evidence.locator}</cite>}
        </blockquote>
      ) : (
        <p className="muted small">No excerpt was stored for this observation.</p>
      )}
    </figure>
  );
}
