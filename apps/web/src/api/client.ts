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

export interface SignalsPayload {
  schema_version: number;
  generated_at: string;
  signals: Signal[];
}

// Default to the static JSON published by the scheduled GitHub Action to the
// `data` branch. Override via VITE_SIGNALS_URL for local dev (e.g. point at
// the FastAPI server at http://localhost:8000/signals).
const SIGNALS_URL =
  import.meta.env.VITE_SIGNALS_URL ??
  "https://raw.githubusercontent.com/stenkjan/buy-the-dip/data/signals.json";

export async function fetchSignals(): Promise<SignalsPayload> {
  const r = await fetch(SIGNALS_URL, { cache: "no-store" });
  if (!r.ok) throw new Error(`signals fetch failed: ${r.status} ${r.statusText}`);
  const body = await r.json();
  // Accept both the wrapped payload and a bare array (forwards-compat).
  if (Array.isArray(body)) {
    return { schema_version: 0, generated_at: new Date().toISOString(), signals: body };
  }
  return body as SignalsPayload;
}
