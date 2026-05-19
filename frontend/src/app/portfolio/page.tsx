"use client";

import MainLayout from "@/components/layout/MainLayout";
import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

export default function PortfolioPage() {
  const [balance, setBalance] = useState<any>(null);
  const [positions, setPositions] = useState<any[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [tradingStatus, setTradingStatus] = useState<any>(null);
  const [config, setConfig] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [closingSymbol, setClosingSymbol] = useState<string | null>(null);
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [balRes, posRes, histRes, statsRes, statusRes, cfgRes] = await Promise.all([
        api.getPortfolioBalance().catch(() => ({})),
        api.getPortfolioPositions().catch(() => ({ positions: [] })),
        api.getPortfolioHistory(30).catch(() => ({ trades: [] })),
        api.getPortfolioStats(30).catch(() => ({ stats: {} })),
        api.getTradingStatus().catch(() => ({})),
        api.getTradingConfig().catch(() => ({ config: {} })),
      ]);
      setBalance(balRes);
      setPositions(posRes.positions || []);
      setHistory(histRes.trades || []);
      setStats(statsRes.stats || {});
      setTradingStatus(statusRes);
      setConfig(cfgRes.config || {});
    } catch (e) {
      console.error("Portfolio fetch error:", e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Auto-refresh every 10 seconds
  useEffect(() => {
    const timer = setInterval(fetchData, 10000);
    return () => clearInterval(timer);
  }, [fetchData]);

  const handleClose = async (symbol: string) => {
    if (!confirm(`Close position ${symbol}?`)) return;
    setClosingSymbol(symbol);
    try {
      const res = await api.closePosition(symbol);
      if (res.result?.success) {
        setMessage({ text: `✅ ${res.result.message}`, type: "success" });
        fetchData();
      } else {
        setMessage({ text: `❌ ${res.result?.message || "Failed"}`, type: "error" });
      }
    } catch (e: any) {
      setMessage({ text: `❌ ${e.message}`, type: "error" });
    } finally {
      setClosingSymbol(null);
      setTimeout(() => setMessage(null), 5000);
    }
  };

  const handleToggleAutoTrade = async () => {
    try {
      const newConfig = { ...config, enabled: !config.enabled };
      await api.updateTradingConfig(newConfig);
      setConfig(newConfig);
      setMessage({ text: newConfig.enabled ? "🤖 Auto-trading ENABLED" : "⏸ Auto-trading DISABLED", type: "success" });
      setTimeout(() => setMessage(null), 3000);
    } catch (e) {
      setMessage({ text: "Failed to update config", type: "error" });
    }
  };

  const handleToggleDryRun = async () => {
    try {
      const newConfig = { ...config, dry_run: !config.dry_run };
      await api.updateTradingConfig(newConfig);
      setConfig(newConfig);
      setMessage({ text: newConfig.dry_run ? "🧪 Dry-run mode ON" : "⚡ LIVE trading mode", type: "success" });
      setTimeout(() => setMessage(null), 3000);
    } catch (e) {
      setMessage({ text: "Failed to update config", type: "error" });
    }
  };

  const totalPnl = positions.reduce((s: number, p: any) => s + (p.unrealized_pnl || 0), 0);

  return (
    <MainLayout>
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h1 style={{ fontSize: "1.5rem", fontWeight: 800, margin: 0, letterSpacing: "-0.03em" }}>Portfolio & Trading</h1>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "4px 0 0" }}>
              Real-time positions, PnL tracking & auto-trading control
            </p>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {/* Connection Status */}
            <span style={{
              padding: "6px 12px", borderRadius: 20, fontSize: "0.75rem", fontWeight: 700,
              background: tradingStatus?.connected ? "rgba(34,197,94,0.12)" : "rgba(239,68,68,0.12)",
              border: `1px solid ${tradingStatus?.connected ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`,
              color: tradingStatus?.connected ? "#22c55e" : "#ef4444",
            }}>
              {tradingStatus?.connected ? "🟢 Binance Connected" : "🔴 Not Connected"}
            </span>
            {/* Auto-Trade Toggle */}
            <button onClick={handleToggleAutoTrade} style={{
              padding: "6px 14px", borderRadius: 20, fontSize: "0.78rem", fontWeight: 700, cursor: "pointer",
              background: config?.enabled ? "rgba(34,197,94,0.15)" : "rgba(255,255,255,0.03)",
              border: `1px solid ${config?.enabled ? "rgba(34,197,94,0.4)" : "var(--border)"}`,
              color: config?.enabled ? "#22c55e" : "var(--text-secondary)",
              transition: "all 0.2s",
            }}>
              {config?.enabled ? "🤖 Auto-Trade ON" : "⏸ Auto-Trade OFF"}
            </button>
            {/* Dry-Run Toggle */}
            <button onClick={handleToggleDryRun} style={{
              padding: "6px 14px", borderRadius: 20, fontSize: "0.78rem", fontWeight: 700, cursor: "pointer",
              background: config?.dry_run ? "rgba(245,158,11,0.15)" : "rgba(239,68,68,0.15)",
              border: `1px solid ${config?.dry_run ? "rgba(245,158,11,0.4)" : "rgba(239,68,68,0.4)"}`,
              color: config?.dry_run ? "#f59e0b" : "#ef4444",
              transition: "all 0.2s",
            }}>
              {config?.dry_run ? "🧪 Dry-Run" : "⚡ LIVE"}
            </button>
          </div>
        </div>

        {/* Message Banner */}
        {message && (
          <div style={{
            padding: "10px 16px", borderRadius: 10, fontSize: "0.85rem", fontWeight: 600,
            background: message.type === "success" ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)",
            border: `1px solid ${message.type === "success" ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`,
            color: message.type === "success" ? "#22c55e" : "#ef4444",
          }}>
            {message.text}
          </div>
        )}

        {/* ── Stats Cards ── */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
          {[
            { label: "Total Balance", value: `$${(balance?.total_balance ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2 })}`, color: "var(--accent-blue)" },
            { label: "Available", value: `$${(balance?.available_balance ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2 })}`, color: "#a78bfa" },
            { label: "Unrealized PnL", value: `${totalPnl >= 0 ? "+" : ""}$${totalPnl.toFixed(2)}`, color: totalPnl >= 0 ? "#22c55e" : "#ef4444" },
            { label: "Open Positions", value: positions.length.toString(), color: "#f59e0b" },
            { label: "Win Rate", value: `${(stats?.win_rate ?? 0).toFixed(1)}%`, color: "#22c55e" },
            { label: "Today PnL", value: `${(stats?.today_pnl ?? 0) >= 0 ? "+" : ""}$${(stats?.today_pnl ?? 0).toFixed(2)}`, color: (stats?.today_pnl ?? 0) >= 0 ? "#22c55e" : "#ef4444" },
          ].map(card => (
            <div key={card.label} className="glass-card" style={{ padding: "16px 20px" }}>
              <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6 }}>{card.label}</div>
              <div style={{ fontSize: "1.4rem", fontWeight: 800, color: card.color, fontFamily: "'JetBrains Mono', monospace" }}>{isLoading ? "..." : card.value}</div>
            </div>
          ))}
        </div>

        {/* ── Open Positions ── */}
        <div className="glass-card" style={{ padding: 20 }}>
          <div style={{ fontSize: "0.9rem", fontWeight: 700, marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>📊 Open Positions</span>
            <span className="badge badge-score">{positions.length} open</span>
          </div>
          {positions.length === 0 ? (
            <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "30px 0", fontSize: "0.85rem" }}>
              No open positions {!tradingStatus?.connected && "— Connect Binance API to start"}
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    {["Symbol", "Side", "Size", "Entry", "Mark Price", "PnL", "PnL %", "Leverage", "Margin", "Action"].map(h => (
                      <th key={h} style={{ padding: "8px 10px", textAlign: "left", color: "var(--text-muted)", fontWeight: 600, fontSize: "0.72rem", textTransform: "uppercase" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {positions.map((p: any, i: number) => (
                    <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
                      <td style={{ padding: "10px", fontWeight: 700 }}>{p.symbol}</td>
                      <td><span className={`badge ${p.side === "LONG" ? "badge-buy" : "badge-sell"}`}>{p.side}</span></td>
                      <td style={{ fontFamily: "'JetBrains Mono', monospace" }}>{p.size}</td>
                      <td style={{ fontFamily: "'JetBrains Mono', monospace" }}>{formatPrice(p.entry_price)}</td>
                      <td style={{ fontFamily: "'JetBrains Mono', monospace" }}>{formatPrice(p.mark_price)}</td>
                      <td style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: p.unrealized_pnl >= 0 ? "#22c55e" : "#ef4444" }}>
                        {p.unrealized_pnl >= 0 ? "+" : ""}{p.unrealized_pnl?.toFixed(4)}
                      </td>
                      <td style={{ fontWeight: 700, color: p.unrealized_pnl_pct >= 0 ? "#22c55e" : "#ef4444" }}>
                        {p.unrealized_pnl_pct >= 0 ? "+" : ""}{p.unrealized_pnl_pct?.toFixed(2)}%
                      </td>
                      <td>{p.leverage}x</td>
                      <td style={{ fontFamily: "'JetBrains Mono', monospace" }}>${p.margin?.toFixed(2)}</td>
                      <td>
                        <button
                          onClick={() => handleClose(p.symbol)}
                          disabled={closingSymbol === p.symbol}
                          style={{
                            padding: "4px 10px", borderRadius: 6, fontSize: "0.72rem", fontWeight: 700,
                            background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)",
                            color: "#ef4444", cursor: "pointer", transition: "all 0.15s",
                          }}
                        >
                          {closingSymbol === p.symbol ? "..." : "Close"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ── Trading Config ── */}
        <div className="glass-card" style={{ padding: 20 }}>
          <div style={{ fontSize: "0.9rem", fontWeight: 700, marginBottom: 16 }}>⚙️ Auto-Trade Settings</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
            {[
              { label: "Risk per Trade", value: `${config?.risk_per_trade ?? 1}%` },
              { label: "Max Positions", value: config?.max_positions ?? 3 },
              { label: "Max Daily Loss", value: `${config?.max_daily_loss ?? 3}%` },
              { label: "Default Leverage", value: `${config?.default_leverage ?? 5}x` },
            ].map(item => (
              <div key={item.label} style={{
                padding: "12px 16px", borderRadius: 10,
                background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)",
              }}>
                <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", fontWeight: 600, marginBottom: 4, textTransform: "uppercase" }}>{item.label}</div>
                <div style={{ fontSize: "1.1rem", fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>{item.value}</div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Trade History ── */}
        <div className="glass-card" style={{ padding: 20 }}>
          <div style={{ fontSize: "0.9rem", fontWeight: 700, marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>📜 Trade History (30 days)</span>
            <div style={{ display: "flex", gap: 12, fontSize: "0.75rem" }}>
              <span style={{ color: "#22c55e", fontWeight: 700 }}>W: {stats?.win_count ?? 0}</span>
              <span style={{ color: "#ef4444", fontWeight: 700 }}>L: {stats?.loss_count ?? 0}</span>
              <span style={{ color: "var(--text-secondary)", fontWeight: 700 }}>Total: {stats?.total_trades ?? 0}</span>
            </div>
          </div>
          {history.length === 0 ? (
            <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "20px 0", fontSize: "0.85rem" }}>
              No trade history yet
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.78rem" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    {["Symbol", "Side", "Realized PnL", "Date"].map(h => (
                      <th key={h} style={{ padding: "8px 10px", textAlign: "left", color: "var(--text-muted)", fontWeight: 600, fontSize: "0.7rem", textTransform: "uppercase" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {history.slice(0, 20).map((t: any, i: number) => (
                    <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
                      <td style={{ padding: "8px 10px", fontWeight: 700 }}>{t.symbol}</td>
                      <td><span className={`badge ${t.realized_pnl >= 0 ? "badge-buy" : "badge-sell"}`}>{t.side}</span></td>
                      <td style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: t.realized_pnl >= 0 ? "#22c55e" : "#ef4444" }}>
                        {t.realized_pnl >= 0 ? "+" : ""}${t.realized_pnl?.toFixed(4)}
                      </td>
                      <td style={{ color: "var(--text-secondary)" }}>{t.closed_at ? new Date(t.closed_at).toLocaleDateString() : "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ── Performance ── */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div className="glass-card" style={{ padding: 20 }}>
            <div style={{ fontSize: "0.85rem", fontWeight: 700, marginBottom: 12 }}>📈 Performance</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {[
                { label: "Total Realized PnL", value: `$${(stats?.total_realized_pnl ?? 0).toFixed(2)}`, color: (stats?.total_realized_pnl ?? 0) >= 0 ? "#22c55e" : "#ef4444" },
                { label: "Max Drawdown", value: `${(stats?.max_drawdown_pct ?? 0).toFixed(2)}%`, color: "#ef4444" },
                { label: "Margin Used", value: `$${(stats?.total_margin_used ?? 0).toFixed(2)}`, color: "#f59e0b" },
              ].map(item => (
                <div key={item.label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
                  <span style={{ color: "var(--text-secondary)", fontSize: "0.78rem" }}>{item.label}</span>
                  <span style={{ fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", color: item.color, fontSize: "0.85rem" }}>{item.value}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="glass-card" style={{ padding: 20 }}>
            <div style={{ fontSize: "0.85rem", fontWeight: 700, marginBottom: 12 }}>🎯 Win/Loss</div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 20, padding: "20px 0" }}>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: "2rem", fontWeight: 800, color: "#22c55e" }}>{stats?.win_count ?? 0}</div>
                <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 600 }}>WINS</div>
              </div>
              <div style={{ width: 2, height: 50, background: "var(--border)" }} />
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: "2rem", fontWeight: 800, color: "#ef4444" }}>{stats?.loss_count ?? 0}</div>
                <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 600 }}>LOSSES</div>
              </div>
              <div style={{ width: 2, height: 50, background: "var(--border)" }} />
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: "2rem", fontWeight: 800, color: "var(--accent-blue)" }}>{(stats?.win_rate ?? 0).toFixed(0)}%</div>
                <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 600 }}>WIN RATE</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}

function formatPrice(val: number) {
  if (!val && val !== 0) return "-";
  return val > 10
    ? val.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : val.toFixed(6);
}
