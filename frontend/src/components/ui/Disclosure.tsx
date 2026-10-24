import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";

/** Native <details> disclosure — keyboard accessible with no JS. */
export function Disclosure({ summary, children, open }: { summary: ReactNode; children: ReactNode; open?: boolean }) {
  return (
    <details className="disclosure" open={open}>
      <summary>
        {summary}
        <ChevronDown size={14} aria-hidden className="disclosure-chevron" />
      </summary>
      <div className="disclosure-body">{children}</div>
    </details>
  );
}
