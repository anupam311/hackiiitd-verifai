import { hueFor, initials } from "@/lib/formatters";

/** Monogram avatar; no third-party logos are fetched or implied. */
export function OrgAvatar({ name, size = 44 }: { name: string | null; size?: number }) {
  const hue = hueFor(name);
  return (
    <span className="org-avatar" style={{ width: size, height: size, fontSize: size * 0.4, background: `hsl(${hue} 70% 94%)`, color: `hsl(${hue} 55% 32%)` }} aria-hidden>
      {initials(name)}
    </span>
  );
}
