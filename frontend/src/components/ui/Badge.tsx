import type { ReactNode } from "react";

export type Tone = "green" | "amber" | "red" | "gray" | "blue" | "purple";

export function Badge({ tone = "gray", children, icon, title }: { tone?: Tone; children: ReactNode; icon?: ReactNode; title?: string }) {
  return (
    <span className={`badge badge-${tone}`} title={title}>
      {icon}
      {children}
    </span>
  );
}

export function Dot({ tone }: { tone: Tone }) {
  return <i className={`dot dot-${tone}`} aria-hidden />;
}
