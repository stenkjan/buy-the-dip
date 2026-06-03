import { useCallback, useEffect, useState } from "react";
import { adminApi, AdminApiError, type Bot, type SignalRecord } from "../api/admin";

const KEY_STORAGE = "btd_api_key";

function useApiKey(): [string, (k: string) => void] {
  const [key, setKey] = useState(() => localStorage.getItem(KEY_STORAGE) ?? "");
  const update = (k: string) => {
    setKey(k);
    if (k) localStorage.setItem(KEY_STORAGE, k);
    else localStorage.removeItem(KEY_STORAGE);
  };
  return [key, update];
}

function BotRow({
  bot,
  apiKey,
  onChanged,
}: {
  bot: Bot;
  apiKey: string;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [signals, setSignals] = useState<SignalRecord[] | null>(null);
  const [open, setOpen] = useState(false);

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    try {
      await fn();
      onChanged();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function toggleSignals() {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    if (signals === null) {
      try {
        setSignals(await adminApi.botSignals(apiKey, bot.id));
      } catch (e) {
        alert(e instanceof Error ? e.message : String(e));
        setSignals([]);
      }
    }
  }

  return (
    <article className={`card ${bot.enabled ? "is-triggered" : ""}`}>
      <header>
        <h2>{bot.name}</h2>
        <span className="badge">{bot.asset_symbol}</span>
      </header>
      <dl>
        <dt>Status</dt>
        <dd>
          <span className={bot.enabled ? "pill pill--on" : "pill"}>
            {bot.enabled ? "enabled" : "paused"}
          </span>
        </dd>
        <dt>Mode</dt><dd>{bot.mode}</dd>
        <dt>Strategy</dt><dd>{bot.strategy_name}</dd>
        <dt>Broker</dt><dd>{bot.broker_name}</dd>
      </dl>

      <div className="bot-actions">
        <button disabled={busy} onClick={() => act(() => adminApi.toggleBot(apiKey, bot.id))}>
          {bot.enabled ? "Pause" : "Enable"}
        </button>
        <button
          disabled={busy}
          onClick={() =>
            act(() =>
              adminApi.updateBot(apiKey, bot.id, { mode: bot.mode === "paper" ? "live" : "paper" }),
            )
          }
        >
          → {bot.mode === "paper" ? "live" : "paper"}
        </button>
        <button className="btn-secondary" disabled={busy} onClick={toggleSignals}>
          {open ? "Hide signals" : "Signals"}
        </button>
        <button
          className="btn-danger"
          disabled={busy}
          onClick={() => {
            if (confirm(`Delete bot "${bot.name}"?`)) act(() => adminApi.deleteBot(apiKey, bot.id));
          }}
        >
          Delete
        </button>
      </div>

      {open && (
        <div className="bot-signals">
          {signals === null ? (
            <p className="muted">Loading…</p>
          ) : signals.length === 0 ? (
            <p className="muted">No signal records yet.</p>
          ) : (
            <table>
              <thead>
                <tr><th>time</th><th>stufe</th><th>RSI</th><th>price</th><th>trig</th></tr>
              </thead>
              <tbody>
                {signals.map((s) => (
                  <tr key={s.id}>
                    <td>{new Date(s.timestamp).toISOString().slice(0, 10)}</td>
                    <td>{s.stufe}</td>
                    <td>{s.rsi_value.toFixed(1)}</td>
                    <td>{s.price.toFixed(2)}</td>
                    <td>{s.triggered ? "●" : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </article>
  );
}

function CreateBotForm({ apiKey, onCreated }: { apiKey: string; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [asset, setAsset] = useState("^NDX");
  const [mode, setMode] = useState<"paper" | "live">("paper");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      await adminApi.createBot(apiKey, { name: name.trim(), asset_symbol: asset.trim(), mode });
      setName("");
      onCreated();
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card bot-create" onSubmit={submit}>
      <h2>New bot</h2>
      <label>Name<input value={name} onChange={(e) => setName(e.target.value)} placeholder="ndx-dip" /></label>
      <label>Asset<input value={asset} onChange={(e) => setAsset(e.target.value)} placeholder="^NDX" /></label>
      <label>
        Mode
        <select value={mode} onChange={(e) => setMode(e.target.value as "paper" | "live")}>
          <option value="paper">paper</option>
          <option value="live">live</option>
        </select>
      </label>
      <button type="submit" disabled={busy || !name.trim()}>Create</button>
    </form>
  );
}

export function BotsPanel() {
  const [apiKey, setApiKey] = useApiKey();
  const [keyInput, setKeyInput] = useState(apiKey);
  const [bots, setBots] = useState<Bot[] | null>(null);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!apiKey) {
      setBots(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setBots(await adminApi.listBots(apiKey));
    } catch (e) {
      const status = e instanceof AdminApiError ? e.status : -1;
      setError({ status, message: e instanceof Error ? e.message : String(e) });
      setBots(null);
    } finally {
      setLoading(false);
    }
  }, [apiKey]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <section>
      <div className="bot-auth">
        <label>
          Admin API key
          <input
            type="password"
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            placeholder="X-API-Key…"
          />
        </label>
        <button onClick={() => setApiKey(keyInput)}>{apiKey ? "Update key" : "Connect"}</button>
        {apiKey && (
          <button className="btn-secondary" onClick={() => { setKeyInput(""); setApiKey(""); }}>
            Forget
          </button>
        )}
      </div>

      {!apiKey && (
        <p className="muted">
          Enter the admin API key to manage bots. The control plane is disabled unless the API
          server has <code>API_KEY</code> configured.
        </p>
      )}

      {error && (
        <p className="error" role="alert">
          {error.status === 503
            ? "Admin API is disabled (API_KEY not configured on the server)."
            : error.status === 401
              ? "Invalid API key."
              : `Error: ${error.message}`}
        </p>
      )}

      {apiKey && !error && (
        <>
          {loading && bots === null && <p className="muted">Loading bots…</p>}
          <div className="grid">
            <CreateBotForm apiKey={apiKey} onCreated={load} />
            {bots?.map((b) => (
              <BotRow key={b.id} bot={b} apiKey={apiKey} onChanged={load} />
            ))}
          </div>
          {bots?.length === 0 && <p className="muted">No bots yet — create one above.</p>}
        </>
      )}
    </section>
  );
}
