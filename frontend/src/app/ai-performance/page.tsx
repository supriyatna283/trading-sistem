"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/utils";
import MainLayout from "@/components/layout/MainLayout";

interface PerformanceStats {
  total_signals: number;
  active_signals: number;
  completed_signals: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_pnl_pct: number;
  avg_pnl_per_trade: number;
}

interface SignalHistory {
  created_at: string;
  symbol: string;
  timeframe: string;
  grade: string;
  direction: string;
  status: string;
  pnl_pct: number;
}

interface EquityPoint {
  time: string;
  equity: number;
  pnl: number;
  symbol: string;
}

export default function AIPerformancePage() {
  const [stats, setStats] = useState<PerformanceStats | null>(null);
  const [history, setHistory] = useState<SignalHistory[]>([]);
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [timeWindow, setTimeWindow] = useState("30d");

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      try {
        const [stRes, hiRes, eqRes] = await Promise.all([
          fetch(`${API_URL}/api/v1/ai/performance?time_window=${timeWindow}`),
          fetch(`${API_URL}/api/v1/ai/performance/history?limit=50`),
          fetch(`${API_URL}/api/v1/ai/performance/equity?time_window=${timeWindow}`),
        ]);
        
        if (stRes.ok) setStats(await stRes.json());
        if (hiRes.ok) {
            const histData = await hiRes.json();
            setHistory(histData.items || []);
        }
        if (eqRes.ok) setEquity(await eqRes.json());
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [timeWindow]);

  return (
    <MainLayout>
      <div style={{ padding: "24px", maxWidth: 1200, margin: "0 auto", color: "var(--text-main)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
          <h1 style={{ fontSize: "1.8rem", fontWeight: 700, margin: 0 }}>AI Analyst Performance</h1>
          
          <div style={{ display: "flex", gap: 8 }}>
            {["7d", "30d", "90d", "all"].map(w => (
              <button 
                key={w}
                onClick={() => setTimeWindow(w)}
                style={{
                  background: timeWindow === w ? "var(--accent)" : "var(--bg-card)",
                  color: timeWindow === w ? "#fff" : "var(--text-muted)",
                  border: "none", padding: "6px 12px", borderRadius: 4, cursor: "pointer",
                  fontSize: "0.85rem", fontWeight: 600
                }}
              >
                {w.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div style={{ textAlign: "center", padding: 60, color: "var(--text-muted)" }}>Loading performance data...</div>
        ) : (
          <>
            {/* STATS CARDS */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16, marginBottom: 24 }}>
              <div className="glass-card" style={{ padding: 20 }}>
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>Win Rate</div>
                <div style={{ fontSize: "2rem", fontWeight: 800, color: (stats?.win_rate || 0) >= 50 ? "#4ade80" : "#f87171" }}>
                  {stats?.win_rate}%
                </div>
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 4 }}>
                  {stats?.wins}W / {stats?.losses}L
                </div>
              </div>
              <div className="glass-card" style={{ padding: 20 }}>
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>Total PnL</div>
                <div style={{ fontSize: "2rem", fontWeight: 800, color: (stats?.total_pnl_pct || 0) >= 0 ? "#4ade80" : "#f87171" }}>
                  {(stats?.total_pnl_pct || 0) >= 0 ? "+" : ""}{stats?.total_pnl_pct}%
                </div>
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 4 }}>
                  Avg {stats?.avg_pnl_per_trade}% / trade
                </div>
              </div>
              <div className="glass-card" style={{ padding: 20 }}>
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>Total Signals</div>
                <div style={{ fontSize: "2rem", fontWeight: 800, color: "#93c5fd" }}>
                  {stats?.total_signals}
                </div>
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 4 }}>
                  {stats?.active_signals} Active · {stats?.completed_signals} Completed
                </div>
              </div>
            </div>

            {/* HISTORY TABLE */}
            <div className="glass-card" style={{ padding: 20, overflowX: "auto" }}>
              <h2 style={{ fontSize: "1.2rem", marginTop: 0, marginBottom: 16 }}>Recent Signals</h2>
              {history.length === 0 ? (
                <div style={{ padding: 40, textAlign: "center", color: "var(--text-muted)" }}>No signals generated yet.</div>
              ) : (
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border-color)", color: "var(--text-muted)", fontSize: "0.85rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                      <th style={{ padding: "12px 8px" }}>Date</th>
                      <th style={{ padding: "12px 8px" }}>Symbol</th>
                      <th style={{ padding: "12px 8px" }}>Grade</th>
                      <th style={{ padding: "12px 8px" }}>Direction</th>
                      <th style={{ padding: "12px 8px" }}>Status</th>
                      <th style={{ padding: "12px 8px", textAlign: "right" }}>PnL %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((s, i) => (
                      <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", fontSize: "0.95rem" }}>
                        <td style={{ padding: "12px 8px", color: "var(--text-muted)" }}>{new Date(s.created_at).toLocaleDateString()} {new Date(s.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</td>
                        <td style={{ padding: "12px 8px", fontWeight: 600 }}>{s.symbol} <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{s.timeframe}</span></td>
                        <td style={{ padding: "12px 8px" }}>
                          <span style={{ 
                            background: s.grade === 'A+' || s.grade === 'A' ? "rgba(59,130,246,0.15)" : "rgba(255,255,255,0.1)", 
                            color: s.grade === 'A+' || s.grade === 'A' ? "#93c5fd" : "var(--text-muted)",
                            padding: "2px 6px", borderRadius: 4, fontSize: "0.8rem", fontWeight: 700 
                          }}>{s.grade}</span>
                        </td>
                        <td style={{ padding: "12px 8px" }}>
                          <span style={{ color: s.direction === "BUY" ? "#4ade80" : "#f87171", fontWeight: 600 }}>
                            {s.direction}
                          </span>
                        </td>
                        <td style={{ padding: "12px 8px" }}>
                          <span style={{ 
                            color: s.status.includes("WIN") ? "#4ade80" : s.status === "LOSS" ? "#f87171" : s.status === "ACTIVE" ? "#fbbf24" : "var(--text-muted)" 
                          }}>
                            {s.status.replace("_", " ")}
                          </span>
                        </td>
                        <td style={{ padding: "12px 8px", textAlign: "right", fontWeight: 600, color: s.pnl_pct > 0 ? "#4ade80" : s.pnl_pct < 0 ? "#f87171" : "var(--text-muted)" }}>
                          {s.pnl_pct != null ? `${s.pnl_pct > 0 ? "+" : ""}${s.pnl_pct.toFixed(2)}%` : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </>
        )}
      </div>
    </MainLayout>
  );
}
