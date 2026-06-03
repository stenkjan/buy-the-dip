import { useCallback, useEffect, useState } from "react";
import {
  adminApi,
  AdminApiError,
  type BacktestResult,
  type Bot,
  type SignalRecord,
} from "../api/admin";

const KEY_STORAGE = "btd_api_key";

// buy_the_dip strategy thresholds, mirroring BuyTheDipConfig defaults. These
// are stored on the bot's config_json and consumed by the executor when it
// builds the strategy for that bot.
const THRESHOLD_FIELDS: { key: string; label: string; step: number; default: number }[] = [
  { key: "rsi_threshold_stufe1", label: "Stufe 1 (RSI 12H)", step: 0.5, default: 30 },
  { key: "rsi_threshold_stufe2", label: "Stufe 2 (RSI 1D)", step: 0.5, default: 30 },
  { key: "rsi_threshold_stufe3", label: "Stufe 3 (RSI 1W)", step: 0.5, default: 30 },
  { key: "rsi_threshold_stufe1_liberal", label: "Stufe 1 liberal", step: 0.5, default: 35 },
  { key: "rsi_threshold_stufe2_liberal", label: "Stufe 2 liberal", step: 0.5, default: 30.5 },
  { key: "rsi_threshold_stufe3_liberal", label: "Stufe 3 liberal", step: 0.5, default: 32 },
  { key: "macro_reclaim_window_weeks", label: "Macro-reclaim weeks", step: 1, default: 8 },
];

function BotConfigEditor({
  bot,
  apiKey,
  onSaved,
}: {
  bot: Bot;
  apiKey: string;
  onSaved: () => void;
}) {
  const cfg = bot.config_json ?? {};
  const initial: Record<string, number> = {};
  for (const f of THRESHOLD_FIELDS) {
    initial[f.key] = typeof cfg[f.key] === "number" ? (cfg[f.key] as number) : f.default;
  }
  const [values, setValues] = useState<Record<string, number>>(initial);
  const [liberal, setLiberal] = useState<boolean>(
    typeof cfg.liberal === "boolean" ? (cfg.liberal as boolean) : true,
  );
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<BacktestResult | null>(null);
  const [previewing, setPreviewing] = useState(false);

  async function save() {
    setBusy(true);
    try {
      // Merge over any unknown keys so we never drop config the UI doesn't model.
      const config_json = { ...cfg, ...values, liberal };
      await adminApi.updateBot(apiKey, bot.id, { config_json });
      onSaved();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function runPreview() {
    setPreviewing(true);
    setPreview(null);
    try {
      const result = await adminApi.backtest(apiKey, {
        asset: bot.asset_symbol,
        config: { ...values, liberal },
      });
      setPreview(result);
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    } finally {
      setPreviewing(false);
    }
  }

  return (
    <div className="bot-config">
      <p className="muted">RSI thresholds — a Stufe triggers when its RSI ≤ the value below.</p>
      <div className="bot-config-grid">
        {THRESHOLD_FIELDS.map((f) => (
          <label key={f.key}>
            {f.label}
            <input
              type="number"
              step={f.step}
              value={values[f.key]}
              onChange={(e) =>
                setValues((v) => ({ ...v, [f.key]: Number(e.target.value) }))
              }
            />
          </label>
        ))}
        <label className="bot-config-check">
          <input
            type="checkbox"
            checked={liberal}
            onChange={(e) => setLiberal(e.target.checked)}
          />
          Use liberal thresholds
        </label>
      </div>
      <div className="bot-actions">
        <button disabled={busy} onClick={save}>Save thresholds</button>
        <button className="btn-secondary" disabled={previewing} onClick={runPreview}>
          {previewing ? "Running…" : "Preview history"}
        </button>
        <button className="btn-secondary" disabled={busy} onClick={() => { setValues(initial); setLiberal(true); }}>
          Reset to defaults
        </button>
      </div>

      {previewing && (
        <p className="muted">Replaying ~20 years against these thresholds…</p>
      )}
      {preview && (
        <div className="bot-preview">
          <p className="muted">
            {preview.summary.total} triggers over {preview.n_bars} bars
            {" · "}per Stufe:{" "}
            {[1, 2, 3].map((s) => `S${s} ${preview.summary.per_stufe[String(s)] ?? 0}`).join(" / ")}
          </p>
          <table>
            <thead>
              <tr><th>horizon</th><th>n</th><th>mean</th><th>win rate</th></tr>
            </thead>
            <tbody>
              {["fwd_30d", "fwd_90d", "fwd_365d"].map((h) => {
                const f = preview.summary.forward_returns[h];
                return (
                  <tr key={h}>
                    <td>{h.replace("fwd_", "").replace("d", " days")}</td>
                    <td>{f ? f.n : "—"}</td>
                    <td>{f ? `${(f.mean * 100).toFixed(1)}%` : "—"}</td>
                    <td>{f ? `${(f.win_rate * 100).toFixed(0)}%` : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

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
  const [editing, setEditing] = useState(false);

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
        <button className="btn-secondary" disabled={busy} onClick={() => setEditing((e) => !e)}>
          {editing ? "Close thresholds" : "Thresholds"}
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

      {editing && (
        <BotConfigEditor
          bot={bot}
          apiKey={apiKey}
          onSaved={() => { setEditing(false); onChanged(); }}
        />
      )}

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

  async function emergencyStop() {
    if (!confirm("Pause ALL bots and cancel their open orders?")) return;
    try {
      const r = await adminApi.emergencyStop(apiKey);
      const errs = r.errors.length ? `\n\nErrors:\n- ${r.errors.join("\n- ")}` : "";
      alert(`Paused ${r.bots_paused} bot(s), cancelled ${r.orders_cancelled} order(s).${errs}`);
      load();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
  }

  const hasBots = (bots?.length ?? 0) > 0;

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
        {apiKey && hasBots && (
          <button className="btn-danger" onClick={emergencyStop} title="Pause all bots and cancel open orders">
            ■ Stop all
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
