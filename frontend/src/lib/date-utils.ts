/** Date helpers. Storage is UTC/ISO; display uses the viewer's locale. */

export function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Calendar-day difference using local midnight, so "today" is 0. */
export function daysUntil(isoDate: string | null | undefined, now: Date = new Date()): number | null {
  const d = parseDate(isoDate);
  if (!d) return null;
  const a = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const b = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  return Math.round((a - b) / 86_400_000);
}

export function formatDate(value: string | null | undefined, fallback = "Unknown"): string {
  const d = parseDate(value);
  if (!d) return fallback;
  // Date-only strings are parsed as UTC; format in UTC so the day does not shift.
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(value ?? "");
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric", ...(dateOnly ? { timeZone: "UTC" } : {}) });
}

export function formatDateTime(value: string | null | undefined, fallback = "Not recorded"): string {
  const d = parseDate(value);
  if (!d) return fallback;
  return d.toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function relativeTime(value: string | null | undefined, now: Date = new Date()): string {
  const d = parseDate(value);
  if (!d) return "Never checked";
  const diffMs = now.getTime() - d.getTime();
  const mins = Math.round(diffMs / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days < 45) return `${days} day${days === 1 ? "" : "s"} ago`;
  return formatDate(value);
}

/** Words describing a deadline relative to today; never invents a date. */
export function deadlineLabel(isoDate: string | null | undefined, now: Date = new Date()): { text: string; tone: "neutral" | "soon" | "past" | "unknown" } {
  const n = daysUntil(isoDate, now);
  if (n === null) return { text: "Deadline unknown", tone: "unknown" };
  if (n < 0) return { text: `Listed deadline passed (${formatDate(isoDate)})`, tone: "past" };
  if (n === 0) return { text: "Listed deadline is today", tone: "soon" };
  if (n <= 14) return { text: `${formatDate(isoDate)} · ${n} day${n === 1 ? "" : "s"} left`, tone: "soon" };
  return { text: formatDate(isoDate), tone: "neutral" };
}
