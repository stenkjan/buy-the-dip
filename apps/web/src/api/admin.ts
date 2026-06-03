// Client for the bot control-plane API (FastAPI, Phase 6). Unlike the static
// JSON in client.ts, these endpoints are dynamic and gated behind an admin key
// (X-API-Key). The base URL points at the FastAPI server; override for local
// dev with VITE_API_BASE_URL (defaults to http://localhost:8000).

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export interface Bot {
  id: string;
  name: string;
  strategy_name: string;
  asset_symbol: string;
  mode: "paper" | "live";
  enabled: boolean;
  broker_name: string;
  config_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface BotCreate {
  name: string;
  asset_symbol: string;
  strategy_name?: string;
  mode?: "paper" | "live";
  enabled?: boolean;
  broker_name?: string;
  config_json?: Record<string, unknown>;
}

export interface BotUpdate {
  name?: string;
  mode?: "paper" | "live";
  enabled?: boolean;
  config_json?: Record<string, unknown>;
}

export interface SignalRecord {
  id: string;
  bot_id: string;
  timestamp: string;
  stufe: number;
  rsi_value: number;
  rsi_threshold: number;
  price: number;
  triggered: boolean;
  created_at: string;
}

export interface Position {
  id: string;
  bot_id: string;
  symbol: string;
  qty: number;
  avg_entry_price: number;
  market_value: number;
  unrealized_pl: number;
  updated_at: string;
}

// Carries the HTTP status so the UI can special-case 503 (admin disabled) and
// 401 (bad/missing key).
export class AdminApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "AdminApiError";
  }
}

async function request<T>(
  apiKey: string,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  let r: Response;
  try {
    r = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": apiKey,
        ...(init.headers ?? {}),
      },
    });
  } catch {
    throw new AdminApiError(0, `cannot reach API at ${API_BASE_URL}`);
  }
  if (r.status === 204) return undefined as T;
  if (!r.ok) {
    let detail = `${r.status} ${r.statusText}`;
    try {
      const body = await r.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep status text */
    }
    throw new AdminApiError(r.status, detail);
  }
  return (await r.json()) as T;
}

export const adminApi = {
  listBots: (key: string) => request<Bot[]>(key, "/bots"),
  createBot: (key: string, body: BotCreate) =>
    request<Bot>(key, "/bots", { method: "POST", body: JSON.stringify(body) }),
  updateBot: (key: string, id: string, body: BotUpdate) =>
    request<Bot>(key, `/bots/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  toggleBot: (key: string, id: string) =>
    request<Bot>(key, `/bots/${id}/toggle`, { method: "POST" }),
  deleteBot: (key: string, id: string) =>
    request<void>(key, `/bots/${id}`, { method: "DELETE" }),
  botSignals: (key: string, id: string) =>
    request<SignalRecord[]>(key, `/bots/${id}/signals?limit=20`),
  botPositions: (key: string, id: string) =>
    request<Position[]>(key, `/bots/${id}/positions`),
};
