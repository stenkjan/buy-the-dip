export interface Signal {
  symbol: string;
  timestamp: string;
  triggered: boolean;
  stufe: 1 | 2 | 3;
  rsi_value: number;
  rsi_threshold: number;
  price: number;
  tranche_pct_range: [number, number] | null;
  extras: Record<string, unknown>;
}

const BASE = "/api";

export async function fetchSignals(symbols?: string[]): Promise<Signal[]> {
  const qs = symbols?.length ? "?" + symbols.map((s) => `symbols=${encodeURIComponent(s)}`).join("&") : "";
  const r = await fetch(`${BASE}/signals${qs}`);
  if (!r.ok) throw new Error(`API ${r.status}: ${await r.text()}`);
  return r.json();
}
