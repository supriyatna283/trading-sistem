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

    // Dynamic lookback period based on timeframe to ensure statistical significance
    let days = 30;
    if (timeframe === "1m" || timeframe === "5m") days = 15;
    else if (timeframe === "15m" || timeframe === "30m") days = 30;
    else if (timeframe === "1h") days = 90;
    else if (timeframe === "4h") days = 180;
    else if (timeframe === "1d" || timeframe === "1w") days = 365;

    try {
      const res = await fetch(`${API_URL}/api/v1/backtest/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, timeframe, days, initial_capital: 10000, risk_per_trade_pct: 1.0 })
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
    if (symbol) fetchBacktest();
  }, [symbol, timeframe]);

  if (loading) {
    return <div style={{ padding: 16, borderRadius: 12, background: "rgba(255,255,255,0.02)", border: "1px dashed rgba(255,255,255,0.1)", color: "var(--text-muted)", fontSize: "0.75rem", display: "flex", gap: 8, alignItems: "center" }}>
      <span style={{ display: "inline-block", animation: "spin 1s linear infinite" }}>⟳</span> Running fast historical backtest...
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
            <div style={{ fontSize: "0.6rem", color: "var(--text-muted)" }}>Dynamic Lookback ({data.summary.total_trades || 0} setups)</div>
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

      {(data.tp_rates || summary.tp_rates) && (data.tp_rates || summary.tp_rates).n > 0 && (
        <div style={{ marginTop: 10, padding: "8px 10px", borderRadius: 8, background: "rgba(255,255,255,0.03)", fontSize: "0.6rem", color: "var(--text-muted)" }}>
          <div style={{ fontWeight: 700, marginBottom: 4, letterSpacing: "0.05em", textTransform: "uppercase" }}>🎯 TP Hit Rate (sebelum SL)</div>
          <div style={{ display: "flex", gap: 12 }}>
            <span>TP1 <strong style={{ color: "#10b981" }}>{(data.tp_rates || summary.tp_rates).tp1_hit_rate}%</strong></span>
            <span>TP2 <strong style={{ color: "#60a5fa" }}>{(data.tp_rates || summary.tp_rates).tp2_hit_rate}%</strong></span>
            <span>TP3 <strong style={{ color: "#a78bfa" }}>{(data.tp_rates || summary.tp_rates).tp3_hit_rate}%</strong></span>
          </div>
        </div>
      )}

      {(data.grade_breakdown || summary.grade_breakdown) && (data.grade_breakdown || summary.grade_breakdown).length > 0 && (
        <div style={{ marginTop: 10, padding: "8px 10px", borderRadius: 8, background: "rgba(255,255,255,0.03)", fontSize: "0.6rem", color: "var(--text-muted)" }}>
          <div style={{ fontWeight: 700, marginBottom: 4, letterSpacing: "0.05em", textTransform: "uppercase" }}>🏅 Win Rate per Grade</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            {(data.grade_breakdown || summary.grade_breakdown).map((g: any) => (
              <div key={g.grade} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 22, fontWeight: 800, color: g.grade === "A+" ? "#f59e0b" : g.grade === "A" ? "#10b981" : g.grade === "B" ? "#3b82f6" : "#ef4444" }}>{g.grade}</span>
                <div style={{ flex: 1, height: 5, borderRadius: 2, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
                  <div style={{ width: `${Math.min(100, g.win_rate)}%`, height: "100%", background: g.win_rate >= 60 ? "#10b981" : g.win_rate >= 45 ? "#f59e0b" : "#ef4444" }} />
                </div>
                <span style={{ fontWeight: 800, color: "#fff" }}>{g.win_rate}%</span>
                <span style={{ color: "var(--text-muted)" }}>({g.total})</span>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {summary.total_trades < 5 && (
        <div style={{ marginTop: 10, fontSize: "0.6rem", color: "#f59e0b", textAlign: "center" }}>
          ⚠️ Sample size too small. Win rate may not be statistically significant.
        </div>
      )}
    </div>
  );
}
