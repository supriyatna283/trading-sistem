"use client";

import MainLayout from "@/components/layout/MainLayout";
import { useState } from "react";
import { api } from "@/lib/api";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";

const PRESETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "INJUSDT"];

function StatCard({ label, value, sub, color = "#fff", highlight = false }: any) {
  return (
    <div style={{
      background: highlight ? "rgba(59,130,246,0.06)" : "rgba(255,255,255,0.02)",
      border: `1px solid ${highlight ? "rgba(59,130,246,0.2)" : "rgba(255,255,255,0.06)"}`,
      borderRadius: 12, padding: "14px 16px", textAlign: "center",
    }}>
      <div style={{ fontSize: "0.58rem", fontWeight: 800, color: "var(--text-muted)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6 }}>{label}</div>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "1.15rem", fontWeight: 900, color, lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: "0.6rem", color: "var(--text-muted)", marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

export default function BacktestPage() {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState("");
  const [tradeFilter, setTradeFilter] = useState<"ALL" | "WIN" | "LOSS">("ALL");

  const [form, setForm] = useState({
    symbol: "BTCUSDT",
    timeframe: "1h",
    days: 60,
    initial_capital: 10000,
    risk_per_trade_pct: 1.0,
  });

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResults(null);
    try {
      const res = await api.runBacktest({
        symbol: form.symbol,
        timeframe: form.timeframe,
        days: parseInt(form.days.toString()),
        initial_capital: parseFloat(form.initial_capital.toString()),
        risk_per_trade_pct: parseFloat(form.risk_per_trade_pct.toString()),
      });
      setResults(res);
    } catch (err: any) {
      setError(err.message || "Failed to run backtest");
    } finally {
      setLoading(false);
    }
  };

  const s = results?.summary;
  const returnPct = s?.total_return_pct ?? 0;
  const returnColor = returnPct >= 0 ? "#10b981" : "#ef4444";
  const filteredTrades = (results?.trades ?? []).filter((t: any) =>
    tradeFilter === "ALL" ? true : t.result === tradeFilter
  );

  // Format equity curve for recharts
  const equityCurve = (results?.equity_curve ?? []).map((p: any) => ({
    time: new Date(p.time).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    equity: p.equity,
  }));
  const initCap = s?.initial_capital ?? form.initial_capital;

  return (
    <MainLayout>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: "1.5rem", fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>
          Strategy Simulator
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "4px 0 0" }}>
          Backtest the Confluence Engine (V4 · Phase 3 · min score 16/36) against historical data
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 20, alignItems: "start" }}>
        {/* ── Left: Form ─────────────────────────────── */}
        <div className="glass-card" style={{ position: "sticky", top: 20 }}>
          <h2 style={{ fontSize: "0.65rem", fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 16 }}>
            Simulation Parameters
          </h2>
          <form onSubmit={handleRun} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {/* Symbol */}
            <div>
              <label style={{ display: "block", fontSize: "0.6rem", fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 6 }}>Asset Pair</label>
              <input
                type="text"
                value={form.symbol}
                onChange={e => setForm({ ...form, symbol: e.target.value.toUpperCase() })}
                style={{ width: "100%", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: "8px 12px", fontSize: "0.85rem", color: "#fff", outline: "none", boxSizing: "border-box" }}
              />
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 6 }}>
                {PRESETS.map(p => (
                  <button key={p} type="button" onClick={() => setForm({ ...form, symbol: p })}
                    style={{ fontSize: "0.58rem", fontWeight: 700, padding: "2px 7px", borderRadius: 4, cursor: "pointer", border: "1px solid rgba(255,255,255,0.1)", background: form.symbol === p ? "rgba(59,130,246,0.2)" : "rgba(255,255,255,0.04)", color: form.symbol === p ? "#60a5fa" : "var(--text-muted)" }}>
                    {p.replace("USDT", "")}
                  </button>
                ))}
              </div>
            </div>

            {/* Timeframe + Days */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div>
                <label style={{ display: "block", fontSize: "0.6rem", fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 6 }}>Timeframe</label>
                <select value={form.timeframe} onChange={e => setForm({ ...form, timeframe: e.target.value })}
                  style={{ width: "100%", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: "8px 10px", fontSize: "0.85rem", color: "#fff", outline: "none", boxSizing: "border-box" }}>
                  <option value="15m">15m</option>
                  <option value="1h">1H</option>
                  <option value="4h">4H</option>
                  <option value="1d">1D</option>
                </select>
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.6rem", fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 6 }}>Days</label>
                <input type="number" max={365} min={7} value={form.days}
                  onChange={e => setForm({ ...form, days: e.target.value as any })}
                  style={{ width: "100%", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: "8px 10px", fontSize: "0.85rem", color: "#fff", outline: "none", boxSizing: "border-box" }} />
              </div>
            </div>

            {/* Capital + Risk */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div>
                <label style={{ display: "block", fontSize: "0.6rem", fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 6 }}>Capital ($)</label>
                <input type="number" value={form.initial_capital}
                  onChange={e => setForm({ ...form, initial_capital: e.target.value as any })}
                  style={{ width: "100%", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: "8px 10px", fontSize: "0.85rem", color: "#fff", outline: "none", boxSizing: "border-box" }} />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.6rem", fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 6 }}>Risk/Trade (%)</label>
                <input type="number" step="0.1" value={form.risk_per_trade_pct}
                  onChange={e => setForm({ ...form, risk_per_trade_pct: e.target.value as any })}
                  style={{ width: "100%", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: "8px 10px", fontSize: "0.85rem", color: "#fff", outline: "none", boxSizing: "border-box" }} />
              </div>
            </div>

            <button type="submit" disabled={loading}
              style={{ marginTop: 6, background: loading ? "rgba(59,130,246,0.4)" : "rgba(59,130,246,0.8)", color: "#fff", fontWeight: 800, fontSize: "0.85rem", padding: "12px", borderRadius: 10, border: "none", cursor: loading ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8, transition: "all 0.2s" }}>
              {loading ? (
                <><span style={{ width: 14, height: 14, border: "2px solid rgba(255,255,255,0.3)", borderTopColor: "#fff", borderRadius: "50%", animation: "spin 0.8s linear infinite", display: "inline-block" }} /> Running...</>
              ) : "▶  Run Backtest"}
            </button>
            {error && <div style={{ color: "#ef4444", fontSize: "0.75rem", textAlign: "center" }}>{error}</div>}
          </form>
        </div>

        {/* ── Right: Results ────────────────────────── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {loading ? (
            <div className="glass-card" style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 64, gap: 16 }}>
              <div style={{ width: 36, height: 36, border: "3px solid rgba(59,130,246,0.3)", borderTopColor: "#3b82f6", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
              <div style={{ color: "var(--text-secondary)", fontSize: "0.85rem", textAlign: "center" }}>
                Fetching {form.days} days of {form.symbol} data and simulating trades...
                <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: 6 }}>This may take 10-30 seconds depending on the date range.</div>
              </div>
            </div>
          ) : s ? (
            <>
              {/* ── Row 1: Key Metrics ── */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
                <StatCard label="Total Return" value={`${returnPct >= 0 ? "+" : ""}${returnPct.toFixed(2)}%`} color={returnColor} highlight />
                <StatCard label="Final Equity" value={`$${s.final_equity?.toFixed(2)}`} color="#fff" />
                <StatCard label="Net Profit" value={`${s.net_profit >= 0 ? "+" : ""}$${s.net_profit?.toFixed(2)}`} color={s.net_profit >= 0 ? "#10b981" : "#ef4444"} />
                <StatCard label="Total Fees" value={`$${s.total_fees?.toFixed(2)}`} color="#f59e0b" />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
                <StatCard label="Win Rate" value={`${s.win_rate?.toFixed(1)}%`} color="#60a5fa" sub={`${s.wins}W / ${s.losses}L`} />
                <StatCard label="Profit Factor" value={s.profit_factor >= 999 ? "∞" : s.profit_factor?.toFixed(2)} color={s.profit_factor >= 1.5 ? "#10b981" : s.profit_factor >= 1 ? "#f59e0b" : "#ef4444"} />
                <StatCard label="Avg R:R" value={`1:${s.avg_rr}`} color="#a78bfa" />
                <StatCard label="Max Drawdown" value={`-${s.max_drawdown_pct?.toFixed(2)}%`} color="#ef4444" />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
                <StatCard label="Sharpe Ratio" value={s.sharpe_ratio?.toFixed(2)} color={s.sharpe_ratio >= 1 ? "#10b981" : s.sharpe_ratio >= 0 ? "#f59e0b" : "#ef4444"} sub="Higher is better" />
                <StatCard label="Sortino Ratio" value={s.sortino_ratio?.toFixed(2)} color={s.sortino_ratio >= 1 ? "#10b981" : s.sortino_ratio >= 0 ? "#f59e0b" : "#ef4444"} sub="Downside risk adjusted" />
                <StatCard label="Calmar Ratio" value={s.calmar_ratio?.toFixed(2)} color="#c084fc" sub="Return / Max DD" />
                <StatCard label="Expectancy" value={`$${s.expectancy?.toFixed(2)}`} color={s.expectancy >= 0 ? "#10b981" : "#ef4444"} sub="Avg $ per trade" />
              </div>

              {/* ── Extended Stats ── */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
                <StatCard label="Largest Win" value={`+$${s.largest_win?.toFixed(2)}`} color="#10b981" />
                <StatCard label="Largest Loss" value={`$${s.largest_loss?.toFixed(2)}`} color="#ef4444" />
                <StatCard label="Max Consec. Losses" value={s.max_consecutive_losses} color="#f59e0b" />
                <StatCard label="Total Trades" value={s.total_trades} color="#94a3b8" sub={`${form.days}d · ${form.timeframe}`} />
              </div>

              {/* ── Signal Grade Breakdown ── */}
              {s.grade_counts && (
                <div className="glass-card" style={{ padding: "14px 16px" }}>
                  <div style={{ fontSize: "0.62rem", fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 12 }}>Signal Grade Distribution</div>
                  <div style={{ display: "flex", gap: 10 }}>
                    {(["A+", "A", "B", "C"] as const).map(grade => {
                      const count = s.grade_counts[grade] ?? 0;
                      const total = s.total_trades || 1;
                      const pct = Math.round((count / total) * 100);
                      const colors: Record<string, string> = { "A+": "#f59e0b", "A": "#10b981", "B": "#3b82f6", "C": "#94a3b8" };
                      return (
                        <div key={grade} style={{ flex: 1, textAlign: "center", background: "rgba(255,255,255,0.03)", borderRadius: 8, padding: "10px 8px" }}>
                          <div style={{ fontSize: "0.65rem", fontWeight: 900, color: colors[grade], marginBottom: 4 }}>{grade}</div>
                          <div style={{ fontFamily: "monospace", fontSize: "1.1rem", fontWeight: 900, color: "#fff" }}>{count}</div>
                          <div style={{ fontSize: "0.58rem", color: "var(--text-muted)", marginTop: 2 }}>{pct}%</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* ── Equity Curve ── */}
              {equityCurve.length > 1 && (
                <div className="glass-card" style={{ padding: "14px 16px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                    <div style={{ fontSize: "0.62rem", fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.1em" }}>
                      📈 Equity Curve
                    </div>
                    <div style={{ fontFamily: "monospace", fontSize: "0.75rem", color: returnColor, fontWeight: 700 }}>
                      ${initCap.toLocaleString()} → ${s.final_equity?.toFixed(0)}
                    </div>
                  </div>
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart data={equityCurve} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                      <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                      <YAxis tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} tickFormatter={v => `$${v >= 1000 ? (v / 1000).toFixed(1) + "k" : v}`} width={50} />
                      <Tooltip
                        contentStyle={{ background: "#0f172a", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, fontSize: 12 }}
                        formatter={(v: any) => [`$${Number(v).toFixed(2)}`, "Equity"]}
                      />
                      <ReferenceLine y={initCap} stroke="rgba(255,255,255,0.15)" strokeDasharray="4 4" label={{ value: "Start", fill: "#64748b", fontSize: 10 }} />
                      <Line type="monotone" dataKey="equity" stroke={returnPct >= 0 ? "#10b981" : "#ef4444"} strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* ── Setup Type Breakdown ── */}
              {results?.breakdown?.length > 0 && (
                <div className="glass-card" style={{ padding: "14px 16px" }}>
                  <div style={{ fontSize: "0.62rem", fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 12 }}>
                    Setup Type Breakdown
                  </div>
                  <div style={{ overflowX: "auto" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.75rem" }}>
                      <thead>
                        <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                          {["Setup Type", "Trades", "Wins", "Losses", "Win Rate", "PnL"].map(h => (
                            <th key={h} style={{ textAlign: "left", padding: "6px 10px", fontSize: "0.6rem", fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase" }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {results.breakdown.map((b: any, i: number) => (
                          <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                            <td style={{ padding: "8px 10px", fontWeight: 700, color: "#fff" }}>{b.setup_type}</td>
                            <td style={{ padding: "8px 10px", fontFamily: "monospace", color: "#94a3b8" }}>{b.total}</td>
                            <td style={{ padding: "8px 10px", fontFamily: "monospace", color: "#10b981" }}>{b.wins}</td>
                            <td style={{ padding: "8px 10px", fontFamily: "monospace", color: "#ef4444" }}>{b.losses}</td>
                            <td style={{ padding: "8px 10px" }}>
                              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                <div style={{ width: 50, height: 4, background: "rgba(255,255,255,0.08)", borderRadius: 2 }}>
                                  <div style={{ width: `${b.win_rate}%`, height: "100%", background: b.win_rate >= 50 ? "#10b981" : "#ef4444", borderRadius: 2 }} />
                                </div>
                                <span style={{ fontFamily: "monospace", color: b.win_rate >= 50 ? "#10b981" : "#ef4444", fontWeight: 700 }}>{b.win_rate}%</span>
                              </div>
                            </td>
                            <td style={{ padding: "8px 10px", fontFamily: "monospace", fontWeight: 700, color: b.pnl >= 0 ? "#10b981" : "#ef4444" }}>
                              {b.pnl >= 0 ? "+" : ""}${b.pnl.toFixed(2)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* ── Trade History ── */}
              <div className="glass-card" style={{ padding: "14px 16px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <div style={{ fontSize: "0.62rem", fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.1em" }}>
                    Trade History ({s.total_trades} trades)
                  </div>
                  <div style={{ display: "flex", gap: 4 }}>
                    {(["ALL", "WIN", "LOSS"] as const).map(f => (
                      <button key={f} onClick={() => setTradeFilter(f)}
                        style={{ fontSize: "0.6rem", fontWeight: 800, padding: "4px 10px", borderRadius: 6, cursor: "pointer", border: "1px solid rgba(255,255,255,0.1)", transition: "all 0.15s",
                          background: tradeFilter === f ? (f === "WIN" ? "rgba(16,185,129,0.2)" : f === "LOSS" ? "rgba(239,68,68,0.2)" : "rgba(59,130,246,0.2)") : "rgba(255,255,255,0.03)",
                          color: tradeFilter === f ? (f === "WIN" ? "#10b981" : f === "LOSS" ? "#ef4444" : "#60a5fa") : "var(--text-muted)" }}>
                        {f}
                      </button>
                    ))}
                  </div>
                </div>

                {filteredTrades.length === 0 ? (
                  <div style={{ textAlign: "center", color: "var(--text-muted)", fontSize: "0.8rem", padding: "32px 0" }}>
                    No {tradeFilter === "ALL" ? "" : tradeFilter.toLowerCase()} trades in this period.
                  </div>
                ) : (
                  <div style={{ overflowX: "auto" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.73rem" }}>
                      <thead>
                        <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                          {["Time", "Side", "Entry", "Grade", "Score", "R:R", "Setup", "Result", "Fees", "PnL"].map(h => (
                            <th key={h} style={{ textAlign: "left", padding: "6px 8px", fontSize: "0.58rem", fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", whiteSpace: "nowrap" }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {filteredTrades.map((t: any, i: number) => {
                          const gradeColors: Record<string, string> = { "A+": "#f59e0b", "A": "#10b981", "B": "#3b82f6", "C": "#94a3b8" };
                          const scoreMax = t.max_score || 36;
                          const scorePct = Math.round(((t.score || 0) / scoreMax) * 100);
                          return (
                            <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
                              <td style={{ padding: "7px 8px", color: "var(--text-muted)", fontSize: "0.68rem", whiteSpace: "nowrap" }}>
                                {new Date(t.entry_time).toLocaleDateString("id-ID", { day: "2-digit", month: "short" })}
                              </td>
                              <td style={{ padding: "7px 8px" }}>
                                <span style={{ fontSize: "0.62rem", fontWeight: 800, padding: "2px 7px", borderRadius: 4, background: t.direction === "BUY" ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.15)", color: t.direction === "BUY" ? "#10b981" : "#ef4444" }}>
                                  {t.direction === "BUY" ? "LONG" : "SHORT"}
                                </span>
                              </td>
                              <td style={{ padding: "7px 8px", fontFamily: "monospace", fontSize: "0.72rem", color: "#fff" }}>
                                {t.entry_price > 10 ? t.entry_price.toFixed(2) : t.entry_price.toFixed(5)}
                              </td>
                              <td style={{ padding: "7px 8px" }}>
                                <span style={{ fontSize: "0.62rem", fontWeight: 900, padding: "2px 6px", borderRadius: 4, background: `${gradeColors[t.signal_grade] || "#94a3b8"}18`, color: gradeColors[t.signal_grade] || "#94a3b8" }}>
                                  {t.signal_grade || "—"}
                                </span>
                              </td>
                              <td style={{ padding: "7px 8px" }}>
                                <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                                  <div style={{ width: 32, height: 3, background: "rgba(255,255,255,0.05)", borderRadius: 2 }}>
                                    <div style={{ width: `${scorePct}%`, height: "100%", background: "#3b82f6", borderRadius: 2 }} />
                                  </div>
                                  <span style={{ fontFamily: "monospace", fontSize: "0.68rem" }}>{t.score || 0}</span>
                                </div>
                              </td>
                              <td style={{ padding: "7px 8px", fontFamily: "monospace", color: "#a78bfa", fontSize: "0.72rem" }}>1:{t.risk_reward?.toFixed(1)}</td>
                              <td style={{ padding: "7px 8px", color: "var(--text-muted)", fontSize: "0.68rem", maxWidth: 100, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.setup_type || "—"}</td>
                              <td style={{ padding: "7px 8px" }}>
                                <span style={{ fontSize: "0.62rem", fontWeight: 800, padding: "2px 7px", borderRadius: 4, background: t.result === "WIN" ? "rgba(16,185,129,0.12)" : "rgba(239,68,68,0.12)", color: t.result === "WIN" ? "#10b981" : "#ef4444" }}>
                                  {t.result}
                                </span>
                              </td>
                              <td style={{ padding: "7px 8px", fontFamily: "monospace", fontSize: "0.68rem", color: "#f59e0b" }}>${(t.fees || 0).toFixed(2)}</td>
                              <td style={{ padding: "7px 8px", fontFamily: "monospace", fontWeight: 700, fontSize: "0.75rem", color: t.pnl >= 0 ? "#10b981" : "#ef4444" }}>
                                {t.pnl >= 0 ? "+" : ""}${t.pnl?.toFixed(2)}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="glass-card" style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 80, textAlign: "center", color: "var(--text-secondary)" }}>
              <div style={{ fontSize: "3rem", marginBottom: 16 }}>⏱️</div>
              <h3 style={{ fontWeight: 800, fontSize: "1.1rem", color: "#fff", marginBottom: 8 }}>Simulator Ready</h3>
              <p style={{ fontSize: "0.85rem", maxWidth: 380 }}>
                Configure parameters on the left and run the simulation. The engine will replay the full Confluence Engine (V4 · Phase 3) over historical OHLCV data and report Sharpe, Sortino, Calmar, and more.
              </p>
            </div>
          )}
        </div>
      </div>
    </MainLayout>
  );
}