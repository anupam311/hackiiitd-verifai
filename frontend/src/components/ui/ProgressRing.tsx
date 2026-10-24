import type { Tone } from "./Badge";

/** Circular meter. `percent` null renders an em dash (no score available). */
export function ProgressRing({ percent, tone = "green", label, size = 76 }: { percent: number | null; tone?: Tone; label?: string; size?: number }) {
  const deg = percent === null ? 0 : Math.round((percent / 100) * 360);
  return (
    <div
      className={`ring ring-${tone}`}
      style={{ width: size, height: size, ["--deg" as string]: `${deg}deg` }}
      role="img"
      aria-label={percent === null ? "No score available" : `${label ?? "Score"}: ${percent} percent`}
    >
      <div className="ring-inner">
        <strong>{percent === null ? "—" : `${percent}%`}</strong>
        {label && <small>{label}</small>}
      </div>
    </div>
  );
}
