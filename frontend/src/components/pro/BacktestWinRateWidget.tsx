"use client";

import { useState, useEffect } from "react";
import { API_URL } from "@/lib/utils";

export function BacktestWinRateWidget({ symbol, timeframe }: { symbol: string; timeframe: string }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchBacktest = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/api/v1/backtest/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, timeframe, days: 30, initial_capital: 10000, risk_per_trade_pct: 1.0 })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (e: any) {
      setError(e.message || "Failed to run backtest");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Only fetch if symbol changes, don't auto fetch on mount unless triggered, but here we can just auto-fetch
    if (symbol) fetchBacktest();
  }, [symbol]);

  if (loading) {
    return <div style={{ padding: 16, borderRadius: 12, background: "rgba(255,255,255,0.02)", border: "1px dashed rgba(255,255,255,0.1)", color: "var(--text-muted)", fontSize: "0.75rem", display: "flex", gap: 8, alignItems: "center" }}>
      <span style={{ display: "inline-block", animation: "spin 1s linear infinite" }}>⟳</span> Running historical 30d backtest...
    </div>;
  }

  if (error) {
    return <div style={{ padding: 16, borderRadius: 12, background: "rgba(239,68,68,0.05)", border: "1px dashed rgba(239,68,68,0.2)", color: "#ef4444", fontSize: "0.75rem" }}>
      ⚠️ {error} <button onClick={fetchBacktest} style={{ background: "transparent", border: "1px solid #ef4444", color: "#ef4444", borderRadius: 4, padding: "2px 6px", cursor: "pointer", marginLeft: 8 }}>Retry</button>
    </div>;
  }

  if (!data || !data.summary) return null;

  const summary = data.summary;
  const isProfitable = (summary.net_profit_pct || 0) > 0;
  const color = isProfitable ? "#10b981" : "#ef4444";

  return (
    <div style={{ padding: 18, borderRadius: 14, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", marginBottom: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: "1.1rem" }}>🕰️</span>
          <div>
            <div style={{ fontWeight: 800, fontSize: "0.85rem", color: "#fff" }}>Historical Win Rate</div>
            <div style={{ fontSize: "0.6rem", color: "var(--text-muted)" }}>Last 30 Days (A+ & A setups)</div>
          </div>
        </div>
        <div style={{ padding: "4px 10px", borderRadius: 8, background: `${color}15`, border: `1px solid ${color}40`, color, fontSize: "0.85rem", fontWeight: 900 }}>
          {summary.win_rate_pct?.toFixed(1) || 0}%
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
        <div style={{ padding: 10, borderRadius: 8, background: "rgba(255,255,255,0.03)", textAlign: "center" }}>
          <div style={{ fontSize: "0.55rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 4 }}>Total Trades</div>
          <div style={{ fontSize: "0.85rem", fontWeight: 800, color: "#fff" }}>{summary.total_trades || 0}</div>
        </div>
        <div style={{ padding: 10, borderRadius: 8, background: "rgba(255,255,255,0.03)", textAlign: "center" }}>
          <div style={{ fontSize: "0.55rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 4 }}>Profit Factor</div>
          <div style={{ fontSize: "0.85rem", fontWeight: 800, color: (summary.profit_factor || 0) >= 1.5 ? "#10b981" : "#f59e0b" }}>{summary.profit_factor?.toFixed(2) || "0.00"}</div>
        </div>
        <div style={{ padding: 10, borderRadius: 8, background: "rgba(255,255,255,0.03)", textAlign: "center" }}>
          <div style={{ fontSize: "0.55rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 4 }}>Net Return</div>
          <div style={{ fontSize: "0.85rem", fontWeight: 800, color }}>{(summary.net_profit_pct || 0) > 0 ? "+" : ""}{summary.net_profit_pct?.toFixed(2) || "0.00"}%</div>
        </div>
      </div>
      
      {summary.total_trades < 5 && (
        <div style={{ marginTop: 10, fontSize: "0.6rem", color: "#f59e0b", textAlign: "center" }}>
          ⚠️ Sample size too small. Win rate may not be statistically significant.
        </div>
      )}
    </div>
  );
}
