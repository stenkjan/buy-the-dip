// Small presentation helpers shared across components.

export function relativeTime(date: Date, now: Date = new Date()): string {
  const sec = Math.round((now.getTime() - date.getTime()) / 1000);
  if (sec < 0) return "just now";
  if (sec < 60) return `${sec}s ago`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  return `${day}d ago`;
}

export function pctSigned(v: number | null | undefined, digits = 1): string {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(digits)}%`;
}
