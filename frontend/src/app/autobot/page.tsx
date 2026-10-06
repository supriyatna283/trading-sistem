"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { API_URL } from "@/lib/utils";

interface Position {
  symbol: string;
  side: "LONG" | "SHORT";
  entry_price: number;
  qty: number;
  peak_pnl: number;
  opened_at: string;
}

interface BotStatus {
  enabled: boolean;
  running: boolean;
  open_positions: Position[];
  tp_usd: number;
  sl_usd: number;
  leverage: number;
  margin_usd: number;
}

interface TradeLog {
  event: "ENTRY" | "EXIT";
  symbol: string;
  side?: string;
  direction?: string;
  entry_price?: number;
  close_price?: number;
  pnl_usd?: number;
  reason?: string;
  qty?: number;
  time: string;
}

const REFRESH_MS = 4000;

function fmt(n: number, d = 2) {
  return n.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
}
function fmtPnl(n: number) {
  return `${n >= 0 ? "+" : ""}$${fmt(Math.abs(n))}`;
}
function elapsed(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  const s = Math.floor((diff % 60000) / 1000);
  if (m >= 60) return `${Math.floor(m / 60)}h ${m % 60}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function StatCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 12, padding: "14px 18px", display: "flex", flexDirection: "column", gap: 4 }}>
      <span style={{ fontSize: "0.65rem", color: "rgba(255,255,255,0.4)", textTransform: "uppercase" as const, letterSpacing: "0.08em" }}>{label}</span>
      <span style={{ fontSize: "1.4rem", fontWeight: 800, color: color || "var(--text-primary)", fontFamily: "'JetBrains Mono', monospace" }}>{value}</span>
      {sub && <span style={{ fontSize: "0.65rem", color: "rgba(255,255,255,0.35)" }}>{sub}</span>}
    </div>
  );
}

function Badge({ children, color }: { children: React.ReactNode; color: string }) {
  return (
    <span style={{ background: `${color}20`, border: `1px solid ${color}50`, color, borderRadius: 6, padding: "2px 10px", fontSize: "0.68rem", fontWeight: 700 }}>
      {children}
    </span>
  );
}

const cardStyle: React.CSSProperties = {
  background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.07)",
  borderRadius: 14, padding: "18px 20px", display: "flex", flexDirection: "column", gap: 14,
};

const cardTitle: React.CSSProperties = {
  fontSize: "0.78rem", fontWeight: 800, color: "var(--text-primary)", letterSpacing: "0.02em",
};

const labelSt: React.CSSProperties = {
  fontSize: "0.62rem", color: "rgba(255,255,255,0.35)", display: "block", marginBottom: 4,
};

const inputStyle: React.CSSProperties = {
  width: "100%", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: 8, padding: "8px 12px", color: "var(--text-primary)",
  fontSize: "0.82rem", fontFamily: "'JetBrains Mono', monospace",
  outline: "none", boxSizing: "border-box" as const,
};

function btnStyle(color: string, outline = false): React.CSSProperties {
  return {
    background: outline ? "transparent" : `${color}18`,
    border: `1px solid ${color}50`, color, borderRadius: 8, padding: "8px 16px",
    cursor: "pointer", fontWeight: 700, fontSize: "0.78rem",
    display: "flex", alignItems: "center", gap: 6, transition: "all 0.15s",
  };
}

export default function AutoBotPage() {
  const [status, setStatus] = useState<BotStatus | null>(null);
  const [trades, setTrades] = useState<TradeLog[]>([]);
  const [tickers, setTickers] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const [entrySymbol, setEntrySymbol] = useState("BTCUSDT");
  const [entryDir, setEntryDir] = useState<"BUY" | "SELL">("BUY");
  const [entryMargin, setEntryMargin] = useState(20);
  const [entryLoading, setEntryLoading] = useState(false);

  const [cfgTp, setCfgTp] = useState(10);
  const [cfgSl, setCfgSl] = useState(3);
  const [cfgLev, setCfgLev] = useState(10);
  const [cfgMargin, setCfgMargin] = useState(20);
  const [cfgLoading, setCfgLoading] = useState(false);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const notify = useCallback((type: "ok" | "err", text: string) => {
    setActionMsg({ type, text });
    setTimeout(() => setActionMsg(null), 4000);
  }, []);

  const fetchStatus = useCallback(async () => {
    try {
      const r = await fetch(`${API_URL}/api/v1/autobot/status`);
      if (!r.ok) throw new Error(await r.text());
      const data: BotStatus = await r.json();
      setStatus(data);
      setCfgTp(data.tp_usd); setCfgSl(data.sl_usd); setCfgLev(data.leverage); setCfgMargin(data.margin_usd);
      setError(null);
    } catch (e: any) { setError(e.message || "Cannot reach backend"); }
    finally { setLoading(false); }
  }, []);

  const fetchTrades = useCallback(async () => {
    try {
      const r = await fetch(`${API_URL}/api/v1/autobot/trades?limit=30`);
      if (!r.ok) return;
      const data = await r.json();
      setTrades(data.trades || []);
    } catch { }
  }, []);

  const fetchTickers = useCallback(async (symbols: string[]) => {
    if (!symbols.length) return;
    try {
      const qs = symbols.map(s => `symbol=${s}`).join("&");
      const r = await fetch(`${API_URL}/api/v1/market/prices?${qs}`);
      if (!r.ok) return;
      const data = await r.json();
      setTickers(data);
    } catch { }
  }, []);

  useEffect(() => {
    fetchStatus(); fetchTrades();
    intervalRef.current = setInterval(() => { fetchStatus(); fetchTrades(); }, REFRESH_MS);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [fetchStatus, fetchTrades]);

  useEffect(() => {
    if (status?.open_positions?.length) fetchTickers(status.open_positions.map(p => p.symbol));
  }, [status?.open_positions, fetchTickers]);

  const doPost = useCallback(async (path: string, body?: object) => {
    const r = await fetch(`${API_URL}${path}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!r.ok) { const err = await r.json().catch(() => ({ detail: r.statusText })); throw new Error(err.detail || r.statusText); }
    return r.json();
  }, []);

  const handleStart = async () => {
    try { await doPost("/api/v1/autobot/start"); notify("ok", "✅ AutoBot started"); await fetchStatus(); }
    catch (e: any) { notify("err", `❌ ${e.message}`); }
  };
  const handleStop = async () => {
    try { await doPost("/api/v1/autobot/stop"); notify("ok", "⏹️ AutoBot stopped"); await fetchStatus(); }
    catch (e: any) { notify("err", `❌ ${e.message}`); }
  };
  const handleCloseAll = async () => {
    if (!confirm("⚠️ Close ALL open positions sekarang?")) return;
    try { await doPost("/api/v1/autobot/close-all"); notify("ok", "🚨 All positions closed"); await fetchStatus(); await fetchTrades(); }
    catch (e: any) { notify("err", `❌ ${e.message}`); }
  };
  const handleEntry = async (dir: "BUY" | "SELL") => {
    setEntryDir(dir); setEntryLoading(true);
    try {
      await doPost("/api/v1/autobot/entry", { symbol: entrySymbol, direction: dir, margin_usd: entryMargin });
      notify("ok", `✅ ${dir} ${entrySymbol} opened`); await fetchStatus(); await fetchTrades();
    } catch (e: any) { notify("err", `❌ ${e.message}`); }
    finally { setEntryLoading(false); }
  };
  const handleClosePosition = async (symbol: string) => {
    try { await doPost(`/api/v1/autobot/close/${symbol}`); notify("ok", `✅ ${symbol} closed`); await fetchStatus(); await fetchTrades(); }
    catch (e: any) { notify("err", `❌ ${e.message}`); }
  };
  const handleConfig = async () => {
    setCfgLoading(true);
    try { await doPost("/api/v1/autobot/config", { tp_usd: cfgTp, sl_usd: cfgSl, leverage: cfgLev, margin_usd: cfgMargin }); notify("ok", "✅ Config updated"); await fetchStatus(); }
    catch (e: any) { notify("err", `❌ ${e.message}`); }
    finally { setCfgLoading(false); }
  };

  const totalPnl = status?.open_positions.reduce((sum, p) => {
    const mark = tickers[p.symbol]; if (!mark) return sum;
    return sum + (p.side === "LONG" ? (mark - p.entry_price) * p.qty : (p.entry_price - mark) * p.qty);
  }, 0) ?? 0;

  const completedTrades = trades.filter(t => t.event === "EXIT");
  const totalRealised = completedTrades.reduce((s, t) => s + (t.pnl_usd ?? 0), 0);
  const winRate = completedTrades.length ? Math.round(completedTrades.filter(t => (t.pnl_usd ?? 0) > 0).length / completedTrades.length * 100) : 0;
  const isRunning = status?.running && status?.enabled;

  if (loading) return <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "80vh", color: "rgba(255,255,255,0.4)" }}>Loading AutoBot...</div>;

  if (error) return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "80vh", gap: 12 }}>
      <span style={{ fontSize: "2rem" }}>⚠️</span>
      <span style={{ color: "#f87171", fontWeight: 700 }}>AutoBot unavailable</span>
      <span style={{ color: "rgba(255,255,255,0.4)", fontSize: "0.8rem", maxWidth: 400, textAlign: "center" }}>{error}</span>
      <span style={{ color: "rgba(255,255,255,0.3)", fontSize: "0.72rem" }}>Set BINANCE_API_KEY dan BINANCE_API_SECRET di HuggingFace Secrets</span>
    </div>
  );

  return (
    <div style={{ padding: "24px 28px", maxWidth: 1200, margin: "0 auto", display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap" as const, gap: 12 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: "1.6rem", fontWeight: 900, background: "linear-gradient(135deg,#34d399,#60a5fa)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            🤖 AutoBot Dashboard
          </h1>
          <p style={{ margin: "4px 0 0", color: "rgba(255,255,255,0.4)", fontSize: "0.78rem" }}>
            Binance Futures · TP ${status?.tp_usd} · SL ${status?.sl_usd} · {status?.leverage}x Leverage · auto-refresh {REFRESH_MS / 1000}s
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <Badge color={isRunning ? "#34d399" : "#f59e0b"}>{isRunning ? "🟢 LIVE" : "🟡 STOPPED"}</Badge>
          {isRunning
            ? <button id="bot-stop-btn" onClick={handleStop} style={btnStyle("#ef4444")}>⏹ Stop</button>
            : <button id="bot-start-btn" onClick={handleStart} style={btnStyle("#34d399")}>▶ Start</button>
          }
          <button id="bot-closeall-btn" onClick={handleCloseAll} style={btnStyle("#ef4444", true)}>🚨 Close All</button>
        </div>
      </div>

      {/* Toast notification */}
      {actionMsg && (
        <div style={{
          background: actionMsg.type === "ok" ? "rgba(52,211,153,0.1)" : "rgba(239,68,68,0.1)",
          border: `1px solid ${actionMsg.type === "ok" ? "rgba(52,211,153,0.3)" : "rgba(239,68,68,0.3)"}`,
          borderRadius: 10, padding: "10px 16px", color: actionMsg.type === "ok" ? "#34d399" : "#f87171",
          fontWeight: 700, fontSize: "0.82rem",
        }}>{actionMsg.text}</div>
      )}

      {/* Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
        <StatCard label="Open Positions" value={String(status?.open_positions.length ?? 0)} sub="active trades" />
        <StatCard label="Unrealised PnL" value={totalPnl >= 0 ? `+$${fmt(totalPnl)}` : `-$${fmt(Math.abs(totalPnl))}`} color={totalPnl >= 0 ? "#34d399" : "#f87171"} sub="across all open" />
        <StatCard label="Realised PnL" value={totalRealised >= 0 ? `+$${fmt(totalRealised)}` : `-$${fmt(Math.abs(totalRealised))}`} color={totalRealised >= 0 ? "#34d399" : "#f87171"} sub={`${completedTrades.length} closed`} />
        <StatCard label="Win Rate" value={`${winRate}%`} sub={`${completedTrades.filter(t => (t.pnl_usd ?? 0) > 0).length}W / ${completedTrades.filter(t => (t.pnl_usd ?? 0) <= 0).length}L`} color={winRate >= 50 ? "#34d399" : "#f87171"} />
        <StatCard label="TP / SL" value={`$${status?.tp_usd} / $${status?.sl_usd}`} color="#facc15" sub="trailing at 30% pullback" />
        <StatCard label="Leverage" value={`${status?.leverage ?? 10}×`} sub={`Margin $${status?.margin_usd}/trade`} />
      </div>

      {/* Main grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        {/* Positions */}
        <div style={cardStyle}>
          <div style={cardTitle}>📊 Open Positions</div>
          {!status?.open_positions.length ? (
            <div style={{ color: "rgba(255,255,255,0.3)", textAlign: "center" as const, padding: "24px 0", fontSize: "0.78rem" }}>No open positions</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {status.open_positions.map(pos => {
                const mark = tickers[pos.symbol];
                const pnl = mark ? (pos.side === "LONG" ? (mark - pos.entry_price) * pos.qty : (pos.entry_price - mark) * pos.qty) : null;
                const pnlColor = pnl === null ? "rgba(255,255,255,0.5)" : pnl >= 0 ? "#34d399" : "#f87171";
                const tpPct = status.tp_usd > 0 && pnl !== null ? Math.min(100, Math.max(0, (pnl / status.tp_usd) * 100)) : 0;
                return (
                  <div key={pos.symbol} style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 10, padding: "12px 14px", display: "flex", flexDirection: "column", gap: 8 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                        <span style={{ fontWeight: 800, fontSize: "0.9rem" }}>{pos.symbol}</span>
                        <Badge color={pos.side === "LONG" ? "#34d399" : "#f87171"}>{pos.side}</Badge>
                      </div>
                      <button id={`close-${pos.symbol}`} onClick={() => handleClosePosition(pos.symbol)}
                        style={{ background: "rgba(239,68,68,0.15)", border: "1px solid rgba(239,68,68,0.3)", color: "#f87171", borderRadius: 6, padding: "3px 10px", cursor: "pointer", fontSize: "0.7rem", fontWeight: 700 }}>
                        ✕ Close
                      </button>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6, fontSize: "0.72rem" }}>
                      <div><span style={labelSt}>Entry</span><span style={{ fontFamily: "monospace" }}>{fmt(pos.entry_price, 4)}</span></div>
                      <div><span style={labelSt}>Mark</span><span style={{ fontFamily: "monospace" }}>{mark ? fmt(mark, 4) : "..."}</span></div>
                      <div><span style={labelSt}>Qty</span><span style={{ fontFamily: "monospace" }}>{pos.qty}</span></div>
                    </div>
                    <div>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                        <span style={{ fontSize: "0.65rem", color: "rgba(255,255,255,0.4)" }}>PnL → TP</span>
                        <span style={{ fontWeight: 800, color: pnlColor, fontFamily: "monospace", fontSize: "0.8rem" }}>{pnl !== null ? fmtPnl(pnl) : "—"}</span>
                      </div>
                      <div style={{ height: 6, borderRadius: 3, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
                        <div style={{ width: `${tpPct}%`, height: "100%", background: pnl !== null && pnl < 0 ? "#f87171" : "#34d399", borderRadius: 3, transition: "width 0.5s" }} />
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.58rem", color: "rgba(255,255,255,0.25)", marginTop: 3 }}>
                        <span>🛑 SL -${status.sl_usd}</span>
                        <span>⏱ {elapsed(pos.opened_at)}</span>
                        <span>🎯 TP +${status.tp_usd}</span>
                      </div>
                    </div>
                    {pos.peak_pnl > 0 && <div style={{ fontSize: "0.64rem", color: "#facc15" }}>⛰ Peak: {fmtPnl(pos.peak_pnl)}</div>}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right col */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Entry */}
          <div style={cardStyle}>
            <div style={cardTitle}>🚀 Open New Position</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <div>
                  <label style={labelSt}>Symbol</label>
                  <input id="entry-symbol" value={entrySymbol} onChange={e => setEntrySymbol(e.target.value.toUpperCase())} style={inputStyle} placeholder="BTCUSDT" />
                </div>
                <div>
                  <label style={labelSt}>Margin (USDT)</label>
                  <input id="entry-margin" type="number" value={entryMargin} onChange={e => setEntryMargin(Number(e.target.value))} style={inputStyle} min={5} />
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <button id="entry-buy-btn" onClick={() => handleEntry("BUY")} disabled={entryLoading} style={btnStyle("#34d399")}>
                  {entryLoading && entryDir === "BUY" ? "⏳..." : "▲ BUY / LONG"}
                </button>
                <button id="entry-sell-btn" onClick={() => handleEntry("SELL")} disabled={entryLoading} style={btnStyle("#f87171")}>
                  {entryLoading && entryDir === "SELL" ? "⏳..." : "▼ SELL / SHORT"}
                </button>
              </div>
              <div style={{ fontSize: "0.63rem", color: "rgba(255,255,255,0.3)" }}>
                Notional ≈ ${entryMargin * (status?.leverage ?? 10)} @ {status?.leverage ?? 10}× leverage · Monitor setiap {REFRESH_MS / 1000}s
              </div>
            </div>
          </div>

          {/* Config */}
          <div style={cardStyle}>
            <div style={cardTitle}>⚙️ Configuration</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div><label style={labelSt}>TP Target ($)</label><input id="cfg-tp" type="number" value={cfgTp} onChange={e => setCfgTp(Number(e.target.value))} style={inputStyle} step={0.5} /></div>
              <div><label style={labelSt}>SL Limit ($)</label><input id="cfg-sl" type="number" value={cfgSl} onChange={e => setCfgSl(Number(e.target.value))} style={inputStyle} step={0.5} /></div>
              <div><label style={labelSt}>Leverage</label><input id="cfg-lev" type="number" value={cfgLev} onChange={e => setCfgLev(Number(e.target.value))} style={inputStyle} min={1} max={125} /></div>
              <div><label style={labelSt}>Margin / Trade ($)</label><input id="cfg-margin" type="number" value={cfgMargin} onChange={e => setCfgMargin(Number(e.target.value))} style={inputStyle} step={5} /></div>
            </div>
            <button id="cfg-save-btn" onClick={handleConfig} disabled={cfgLoading} style={{ ...btnStyle("#60a5fa"), marginTop: 4, width: "100%", justifyContent: "center" as const }}>
              {cfgLoading ? "Saving..." : "💾 Save Config"}
            </button>
            <p style={{ margin: 0, fontSize: "0.62rem", color: "rgba(255,255,255,0.25)" }}>
              Trailing: closes when PnL drops 30% from peak (after 50% TP reached)
            </p>
          </div>
        </div>
      </div>

      {/* Trade Log */}
      <div style={cardStyle}>
        <div style={{ ...cardTitle, display: "flex", justifyContent: "space-between" }}>
          <span>📋 Trade Log</span>
          <span style={{ fontSize: "0.65rem", color: "rgba(255,255,255,0.3)", fontWeight: 400 }}>Last {trades.length} entries</span>
        </div>
        {!trades.length ? (
          <div style={{ color: "rgba(255,255,255,0.3)", textAlign: "center" as const, padding: "20px 0", fontSize: "0.78rem" }}>No trades yet</div>
        ) : (
          <div style={{ overflowX: "auto" as const }}>
            <table style={{ width: "100%", borderCollapse: "collapse" as const, fontSize: "0.72rem" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                  {["Time", "Event", "Symbol", "Side", "Price", "Qty", "PnL", "Reason"].map(h => (
                    <th key={h} style={{ padding: "6px 10px", textAlign: "left" as const, color: "rgba(255,255,255,0.35)", fontWeight: 600, whiteSpace: "nowrap" as const }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {trades.map((t, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.03)", background: i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.01)" }}>
                    <td style={{ padding: "7px 10px", color: "rgba(255,255,255,0.4)", whiteSpace: "nowrap" as const }}>{new Date(t.time).toLocaleTimeString()}</td>
                    <td style={{ padding: "7px 10px" }}><Badge color={t.event === "ENTRY" ? "#60a5fa" : "#a78bfa"}>{t.event}</Badge></td>
                    <td style={{ padding: "7px 10px", fontWeight: 700 }}>{t.symbol}</td>
                    <td style={{ padding: "7px 10px" }}>{(t.side || t.direction) && <Badge color={(t.side || t.direction) === "LONG" || (t.side || t.direction) === "BUY" ? "#34d399" : "#f87171"}>{t.side || t.direction}</Badge>}</td>
                    <td style={{ padding: "7px 10px", fontFamily: "monospace" }}>{t.entry_price ? fmt(t.entry_price, 4) : t.close_price ? fmt(t.close_price, 4) : "—"}</td>
                    <td style={{ padding: "7px 10px", fontFamily: "monospace" }}>{t.qty ?? "—"}</td>
                    <td style={{ padding: "7px 10px", fontWeight: 700, color: t.pnl_usd !== undefined ? (t.pnl_usd >= 0 ? "#34d399" : "#f87171") : "rgba(255,255,255,0.3)" }}>
                      {t.pnl_usd !== undefined ? fmtPnl(t.pnl_usd) : "—"}
                    </td>
                    <td style={{ padding: "7px 10px", color: "rgba(255,255,255,0.4)" }}>{t.reason?.replace(/_/g, " ") ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Risk warning */}
      <div style={{ background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.2)", borderRadius: 10, padding: "12px 16px", fontSize: "0.72rem", color: "rgba(245,158,11,0.8)" }}>
        ⚠️ <strong>Risk Warning:</strong> Bot ini menggunakan akun Binance Futures REAL. API Key hanya boleh punya permission <em>Futures Trading</em> bukan Withdrawal. Gunakan 🚨 Close All untuk emergency exit.
      </div>
    </div>
  );
}
