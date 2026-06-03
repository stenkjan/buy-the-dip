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

export interface HistoryBar {
  timestamp: string;
  close: number;
  ema200_daily: number;
  ema200_weekly: number;
  rsi_1d: number | null;
  rsi_1w: number | null;
  stufe: 1 | 2 | 3;
  triggered: boolean;
}

export interface HistoryPayload {
  schema_version: number;
  generated_at: string;
  assets: Record<string, HistoryBar[]>;
}

// Default to the static JSON published by the scheduled GitHub Action to the
// `data` branch. Override via VITE_SIGNALS_URL for local dev (e.g. point at
// the FastAPI server at http://localhost:8000/signals).
const SIGNALS_URL =
  import.meta.env.VITE_SIGNALS_URL ??
  "https://raw.githubusercontent.com/stenkjan/buy-the-dip/data/signals.json";

// Per-asset daily history (close/EMA200/RSI) for the dashboard charts.
// Derived from VITE_SIGNALS_URL when it points at the data branch, or set
// explicitly via VITE_HISTORY_URL.
const HISTORY_URL =
  import.meta.env.VITE_HISTORY_URL ??
  "https://raw.githubusercontent.com/stenkjan/buy-the-dip/data/history.json";

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

// History is best-effort: the dashboard still renders signal cards if the
// history payload is missing (e.g. before the first publish). Returns null on
// any fetch/parse failure rather than throwing.
export async function fetchHistory(): Promise<HistoryPayload | null> {
  try {
    const r = await fetch(HISTORY_URL, { cache: "no-store" });
    if (!r.ok) return null;
    return (await r.json()) as HistoryPayload;
  } catch {
    return null;
  }
}

export interface DcaSeriesPoint {
  month: string;
  cum_invested: number;
  dca_value: number;
  lump_value: number;
}

export interface DcaSummary {
  schema_version: number;
  generated_at: string;
  asset: string;
  alpaca_symbol: string;
  n_months: number;
  first_bar: string;
  last_bar: string;
  total_invested: number;
  final_value: number;
  total_return_pct: number;
  cagr: number | null;
  max_drawdown_pct: number;
  sharpe_annual: number | null;
  monthly_contribution: number;
  benchmark_lump_sum: {
    final_value: number;
    total_return_pct: number;
    cagr: number | null;
  };
  dca_vs_lump_sum_delta_pct: number;
  history_truncation_warning?: string;
  series: DcaSeriesPoint[];
}

// Per-asset DCA backtest results published by the manual `dca-backtest`
// workflow to the `data` branch under dca/<safe>.json.
const DCA_BASE_URL =
  import.meta.env.VITE_DCA_BASE_URL ??
  "https://raw.githubusercontent.com/stenkjan/buy-the-dip/data/dca";

// Mirrors the CLI's filename derivation (`^NDX` -> `ndx`).
export function toSafeSymbol(symbol: string): string {
  return symbol.replace(/\^/g, "").toLowerCase();
}

// Best-effort: returns null when no DCA result has been published for the
// asset yet (the workflow is manual / opt-in).
export async function fetchDca(symbol: string): Promise<DcaSummary | null> {
  try {
    const r = await fetch(`${DCA_BASE_URL}/${toSafeSymbol(symbol)}.json`, { cache: "no-store" });
    if (!r.ok) return null;
    return (await r.json()) as DcaSummary;
  } catch {
    return null;
  }
}
