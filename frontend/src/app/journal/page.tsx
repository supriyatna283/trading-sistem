"use client";

import MainLayout from "@/components/layout/MainLayout";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";

export default function JournalPage() {
  const [entries, setEntries] = useState<any[]>([]);
  const [analytics, setAnalytics] = useState<any>({
    total_trades: 0,
    win_rate: 0.0,
    profit_factor: 0.0,
    avg_r_multiple: 0.0,
    total_pnl: 0.0,
    wins: 0,
    losses: 0,
    breakeven: 0
  });
  const [loading, setLoading] = useState(true);
  const [isAdding, setIsAdding] = useState(false);
  
  // Form state
  const [formData, setFormData] = useState({
    symbol: "BTCUSDT",
    direction: "BUY",
    entry_price: "",
    exit_price: "",
    stop_loss: "",
    take_profit: "",
    position_size: "1",
    pnl: "",
    result: "WIN",
    notes: ""
  });

  const fetchData = async () => {
    try {
      setLoading(true);
      const [entriesRes, analyticsRes] = await Promise.all([
        api.getJournal(),
        api.getAnalytics()
      ]);
      setEntries(entriesRes?.entries || []);
      
      const a = analyticsRes?.analytics;
      if (a) {
        setAnalytics({
          total_trades: a.total_trades || 0,
          win_rate: a.win_rate || 0,
          profit_factor: a.profit_factor || 0,
          avg_r_multiple: a.avg_r_multiple || 0,
          total_pnl: a.total_pnl || 0,
          wins: a.wins || 0,
          losses: a.losses || 0,
          breakeven: (a.total_trades || 0) - (a.wins || 0) - (a.losses || 0)
        });
      }
    } catch (err) {
      console.error("Failed to load journal", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  return (
    <MainLayout>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: "1.5rem", fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>Trading Journal</h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "4px 0 0" }}>Track and analyze your trading performance automatically from Setups</p>
      </div>

      {/* Analytics Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 14, marginBottom: 24 }}>
        {[
          { label: "Win Rate", value: `${(analytics.win_rate * 100).toFixed(1)}%`, color: "var(--accent-green)", glow: "glow-green" },
          { label: "Profit Factor", value: (analytics.profit_factor).toFixed(2), color: "var(--accent-blue)", glow: "glow-blue" },
          { label: "Avg R Multiple", value: `${(analytics.avg_r_multiple).toFixed(2)}R`, color: "var(--accent-purple)", glow: "glow-purple" },
          { label: "Total Trades", value: analytics.total_trades.toString(), color: "var(--accent-cyan)", glow: "glow-blue" },
          { label: "W/L/BE", value: `${analytics.wins}/${analytics.losses}/${Math.max(0, analytics.total_trades - analytics.wins - analytics.losses)}`, color: "var(--text-primary)", glow: "" },
        ].map((s) => (
          <div key={s.label} className={`glass-card ${s.glow}`} style={{ padding: 16, textAlign: "center" }}>
            <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase" }}>{s.label}</div>
            <div style={{ fontSize: "1.3rem", fontWeight: 800, fontFamily: "'JetBrains Mono', monospace", color: s.color, marginTop: 6 }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Journal Table */}
      <div className="glass-card" style={{ padding: 0, overflow: "hidden" }}>
        {loading ? (
             <div className="p-12 flex justify-center"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div></div>
        ) : entries.length === 0 ? (
            <div className="p-12 text-center text-muted-foreground italic">No journal entries found in database. Add a manual trade or let the auto-scheduler create one.</div>
        ) : (
            <table className="data-table">
            <thead>
                <tr>
                <th>Date</th>
                <th>Pair</th>
                <th>Side</th>
                <th>Grade</th>
                <th>Score</th>
                <th>Entry</th>
                <th>Exit</th>
                <th>PnL</th>
                <th>Result</th>
                <th>Notes</th>
                </tr>
            </thead>
            <tbody>
                {entries.map((j: any) => (
                <tr key={j.id}>
                    <td style={{ color: "var(--text-secondary)", fontFamily: "Inter, sans-serif", fontSize: "0.75rem" }}>
                        {new Date(j.created_at).toLocaleDateString()}
                    </td>
                    <td style={{ fontWeight: 800, color: "var(--text-primary)" }}>{j.symbol}</td>
                    <td><span className={`badge ${j.direction === "BUY" ? "badge-buy" : "badge-sell"}`}>{j.direction === "BUY" ? "LONG" : "SHORT"}</span></td>
                    <td>
                      <span style={{ 
                        fontSize: "0.65rem", fontWeight: 800, padding: "2px 6px", borderRadius: 4,
                        color: j.signal_grade === "A+" ? "#f59e0b" : "#10b981",
                        background: j.signal_grade === "A+" ? "rgba(245,158,11,0.1)" : "rgba(16,185,129,0.1)",
                        border: "1px solid currentColor"
                      }}>
                        {j.signal_grade || "N/A"}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <div style={{ width: 30, height: 4, background: "rgba(255,255,255,0.05)", borderRadius: 2 }}>
                          <div style={{ width: `${j.signal_score || 0}%`, height: "100%", background: "#3b82f6", borderRadius: 2 }} />
                        </div>
                        <span style={{ fontFamily: "monospace", fontSize: "0.75rem" }}>{j.signal_score || 0}</span>
                      </div>
                    </td>
                    <td style={{ fontFamily: "monospace" }}>{j.entry_price}</td>
                    <td style={{ fontFamily: "monospace" }}>{j.exit_price || '-'}</td>
                    <td style={{ color: j.pnl >= 0 ? "var(--accent-green)" : "var(--accent-red)", fontWeight: 800, fontFamily: "monospace" }}>
                    {j.pnl > 0 ? "+" : ""}{j.pnl || '0'}
                    </td>
                    <td>
                    <span className={`badge ${j.result === "WIN" ? "badge-bullish" : j.result === "LOSS" ? "badge-bearish" : "badge-sideways"}`}>
                        {j.result || 'OPEN'}
                    </span>
                    </td>
                    <td style={{ color: "var(--text-muted)", fontFamily: "Inter, sans-serif", fontSize: "0.75rem", maxWidth: 120 }} className="truncate">
                    {j.notes || "-"}
                    </td>
                </tr>
                ))}
            </tbody>
            </table>
        )}
      </div>
    </MainLayout>
  );
}

