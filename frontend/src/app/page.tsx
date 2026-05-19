"use client";

import MainLayout from "@/components/layout/MainLayout";
import Link from "next/link";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";

const EXCHANGES = [
  { key: "bybit", label: "Bybit", color: "#f7931a" },
  { key: "okx", label: "OKX", color: "#00b4ff" },
  { key: "binance", label: "Binance", color: "#f0b90b" },
];

const TIER_CONFIG: Record<string, { color: string; bg: string; label: string; icon: string }> = {
  "A+":       { color: "#f59e0b", bg: "rgba(245,158,11,0.15)",  label: "A+ SETUP",    icon: "💎" },
  "VALID":    { color: "#10b981", bg: "rgba(16,185,129,0.12)",  label: "VALID",      icon: "✅" },
  "WEAK":     { color: "#60a5fa", bg: "rgba(96,165,250,0.12)",  label: "WATCHLIST",  icon: "◉" },
  "NO_TRADE": { color: "#94a3b8", bg: "rgba(148,163,184,0.08)", label: "NO TRADE",   icon: "✕" },
};

function TierBadge({ tier }: { tier: string }) {
  const cfg = TIER_CONFIG[tier] || TIER_CONFIG.NO_TRADE;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "4px 10px", borderRadius: 8, fontSize: "0.65rem",
      fontWeight: 900, letterSpacing: "0.05em",
      color: cfg.color, background: cfg.bg,
      border: `1px solid ${cfg.color}40`,
      boxShadow: tier === "A+" ? `0 0 12px ${cfg.color}30` : "none",
    }}>
      {cfg.icon} {cfg.label}
    </span>
  );
}

function StatCard({ label, value, sub, color, icon, barPct = 60 }: any) {
  return (
    <div className="glass-card" style={{ padding: 22, position: "relative", overflow: "hidden", border: "1px solid var(--border)" }}>
      <div style={{
        position: "absolute", top: -20, right: -20, width: 90, height: 90,
        borderRadius: "50%", background: color, opacity: 0.08, filter: "blur(28px)", pointerEvents: "none"
      }} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 14 }}>
        <span style={{ fontSize: "0.68rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.1em" }}>
          {label}
        </span>
        <span style={{ fontSize: "1.4rem", lineHeight: 1 }}>{icon}</span>
      </div>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "1.75rem", fontWeight: 800, color, letterSpacing: "-0.02em", lineHeight: 1 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: 6 }}>{sub}</div>}
      <div className="stat-bar" style={{ marginTop: 14, height: 4 }}>
        <div className="stat-bar-fill" style={{ width: `${barPct}%`, background: `linear-gradient(90deg, ${color}cc, ${color})`, borderRadius: 2 }} />
      </div>
    </div>
  );
}

function ScoreBar({ score, max = 100 }: { score: number; max?: number }) {
  const pct = Math.min(100, (score / max) * 100);
  const color = score >= 80 ? "#f59e0b" : score >= 65 ? "#10b981" : score >= 50 ? "#3b82f6" : "#ef4444";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <div style={{ flex: 1, height: 6, borderRadius: 99, background: "rgba(255,255,255,0.05)", overflow: "hidden", border: "1px solid rgba(255,255,255,0.03)" }}>
        <div style={{ 
          height: "100%", width: `${pct}%`, 
          background: `linear-gradient(90deg, ${color}99, ${color})`, 
          borderRadius: 99, transition: "width 0.8s cubic-bezier(0.34, 1.56, 0.64, 1)",
          boxShadow: score >= 80 ? `0 0 10px ${color}40` : "none"
        }} />
      </div>
      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.75rem", color, fontWeight: 800, minWidth: 42 }}>
        {score} <span style={{ fontSize: "0.6rem", opacity: 0.5 }}>/100</span>
      </span>
    </div>
  );
}

function LayerBreakdown({ breakdown }: { breakdown: Record<string, number> }) {
  if (!breakdown) return null;
  const layers = [
    { k: "STR", max: 20, color: "#3b82f6" },
    { k: "PA",  max: 20, color: "#10b981" },
    { k: "SMC", max: 20, color: "#a855f7" },
    { k: "VOL", max: 20, color: "#f59e0b" },
    { k: "TIM", max: 10, color: "#ec4899" },
    { k: "RR",  max: 10, color: "#06b6d4" },
  ];
  
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 4, marginTop: 8 }}>
      {layers.map(l => {
        const score = breakdown[l.k] || 0;
        const pct = (score / l.max) * 100;
        return (
          <div key={l.k} title={`${l.k}: ${score}/${l.max}`}>
            <div style={{ height: 3, background: "rgba(255,255,255,0.05)", borderRadius: 2, overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${pct}%`, background: l.color, borderRadius: 2 }} />
            </div>
            <div style={{ fontSize: "0.5rem", fontWeight: 700, color: "var(--text-muted)", marginTop: 2, textAlign: "center" }}>{l.k}</div>
          </div>
        );
      })}
    </div>
  );
}

export default function DashboardPage() {
  const [scannerData, setScannerData] = useState<any[]>([]);
  const [activeSetups, setActiveSetups] = useState<any[]>([]);
  const [stats, setStats] = useState({ winRate: 0, pf: 0, rr: 0, active: 0 });
  const [livePrices, setLivePrices] = useState<Record<string, { price: number; change: number }>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [scanLoading, setScanLoading] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [scanRes, setupsRes, analyticsRes] = await Promise.all([
          api.getScanner().catch(() => ({ results: [] })),
          api.getSetups("ACTIVE").catch(() => ({ setups: [] })),
          api.getAnalytics().catch(() => ({ analytics: null })),
        ]);
        setScannerData(Array.isArray(scanRes?.results) ? scanRes.results : []);
        const setupsArr = Array.isArray(setupsRes?.setups) ? setupsRes.setups : [];
        setActiveSetups(setupsArr);
        const analytics = analyticsRes?.analytics || null;
        if (analytics) {
          setStats({ winRate: analytics.win_rate ?? 0, pf: analytics.profit_factor ?? 0, rr: analytics.avg_r_multiple ?? 0, active: setupsArr.length });
        } else {
          setStats(p => ({ ...p, active: setupsArr.length }));
        }
      } catch {} finally { setIsLoading(false); }
    };
    fetchData();
  }, []);

  // Live price WS
  useEffect(() => {
    if (!scannerData.length) return;
    const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    const u = new URL(API_URL);
    const ws = new WebSocket(`${u.protocol === "https:" ? "wss:" : "ws:"}//${u.host}/ws/tickers?symbols=${scannerData.map((s: any) => s.symbol).join(",")}`);
    ws.onmessage = (e) => {
      const res = JSON.parse(e.data);
      if (res.data?.[0]) {
        const d = res.data[0];
        const sym = (d.instId || "").replace("-", "");
        if (sym && d.last) {
          const open24h = parseFloat(d.open24h || d.last);
          const last = parseFloat(d.last);
          setLivePrices(prev => ({ ...prev, [sym]: { price: last, change: open24h > 0 ? ((last - open24h) / open24h) * 100 : 0 } }));
        }
      }
    };
    return () => ws.close();
  }, [scannerData]);

  const runManualScan = async () => {
    setScanLoading(true);
    try {
      await api.runScanner();
      const res = await api.getScanner();
      setScannerData(Array.isArray(res?.results) ? res.results : []);
    } catch {} finally { setScanLoading(false); }
  };

  const statCards = [
    { label: "Win Rate", value: `${stats.winRate.toFixed(1)}%`, sub: "All closed trades", color: "#10b981", icon: "🎯", barPct: stats.winRate },
    { label: "Profit Factor", value: stats.pf.toFixed(2), sub: "Gross P / Gross L", color: "#3b82f6", icon: "📈", barPct: Math.min(100, stats.pf * 20) },
    { label: "Avg R:R", value: `1:${stats.rr.toFixed(2)}`, sub: "Average risk multiple", color: "#a855f7", icon: "⚖️", barPct: Math.min(100, stats.rr * 20) },
    { label: "Active Setups", value: stats.active, sub: "Open positions", color: "#ef4444", icon: "🔥", barPct: Math.min(100, stats.active * 10) },
  ];

  return (
    <MainLayout>
      {/* ── Header ── */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 32 }}>
        <div>
          <h1 style={{ fontFamily: "'Outfit',sans-serif", fontSize: "1.8rem", fontWeight: 900, letterSpacing: "-0.04em", margin: 0,
            background: "linear-gradient(135deg, #fff 30%, #94a3b8)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            Trading Intelligence Platform
          </h1>
          <p style={{ color: "var(--text-muted)", fontSize: "0.82rem", margin: "8px 0 0", display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ color: "var(--accent-blue)", fontWeight: 700 }}>6-Layer Scoring</span>
            <span style={{ opacity: 0.3 }}>•</span>
            <span>A+ Execution Gate</span>
            <span style={{ opacity: 0.3 }}>•</span>
            <span>Institutional SMC V3</span>
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          {EXCHANGES.map(ex => (
            <div key={ex.key} style={{ display: "flex", alignItems: "center", gap: 6, background: "rgba(255,255,255,0.03)", padding: "6px 12px", borderRadius: 10, border: "1px solid rgba(255,255,255,0.05)" }}>
              <div className="animate-pulse-dot" style={{ width: 6, height: 6, borderRadius: "50%", background: ex.color, boxShadow: `0 0 8px ${ex.color}60` }} />
              <span style={{ fontSize: "0.72rem", color: "var(--text-secondary)", fontWeight: 700, letterSpacing: "0.02em" }}>{ex.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Stats ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 20, marginBottom: 32 }}>
        {statCards.map(s => <StatCard key={s.label} {...s} />)}
      </div>

      {/* ── Active Setups ── */}
      <div className="glass-card" style={{ padding: 24, marginBottom: 28, border: "1px solid var(--border)" }}>
        <div className="flex-between" style={{ marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 4, height: 20, borderRadius: 99, background: "linear-gradient(180deg,#f59e0b,#3b82f6)" }} />
            <span style={{ fontWeight: 800, fontSize: "1rem", letterSpacing: "-0.01em" }}>High Conviction Setups</span>
          </div>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <span className="badge badge-score" style={{ background: "rgba(59,130,246,0.1)", color: "var(--accent-blue)", fontWeight: 800 }}>{activeSetups.length} ACTIVE</span>
            <Link href="/setups" style={{ fontSize: "0.75rem", color: "var(--accent-blue)", textDecoration: "none", fontWeight: 700, opacity: 0.8 }}>View All Signals →</Link>
          </div>
        </div>

        {activeSetups.length === 0 ? (
          <div style={{ padding: "48px 0", textAlign: "center", color: "var(--text-muted)", fontSize: "0.85rem",
            border: "1px dashed rgba(255,255,255,0.1)", borderRadius: 16, background: "rgba(255,255,255,0.01)" }}>
            <div style={{ fontSize: "2.5rem", marginBottom: 12, opacity: 0.5 }}>📡</div>
            No active signals detected. Running scanner...
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(340px,1fr))", gap: 18 }}>
            {activeSetups.slice(0, 6).map((setup: any, idx: number) => (
              <div key={setup.id || idx} style={{
                background: "rgba(255,255,255,0.015)", border: "1px solid var(--border)", borderRadius: 16, padding: 18,
                transition: "all 0.3s ease", cursor: "pointer",
              }}
              onMouseOver={(e) => e.currentTarget.style.border = "1px solid rgba(59,130,246,0.3)"}
              onMouseOut={(e) => e.currentTarget.style.border = "1px solid var(--border)"}
              >
                {/* Header: Symbol + Direction + Grade */}
                <div className="flex-between" style={{ marginBottom: 14 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span className="text-mono" style={{ fontWeight: 900, fontSize: "1.05rem", color: "#fff" }}>{setup.symbol}</span>
                    <span className={`badge badge-${setup.direction === "BUY" ? "buy" : "sell"}`} style={{ fontWeight: 800 }}>{setup.direction}</span>
                    <TierBadge tier={setup.signal_grade || "NO_TRADE"} />
                  </div>
                  <span style={{ fontSize: "0.65rem", color: "var(--text-muted)", fontWeight: 600 }}>{setup.timeframe}</span>
                </div>
                {/* Score bar */}
                <div style={{ marginBottom: 14 }}>
                  <ScoreBar score={setup.signal_score ?? 0} max={100} />
                  <LayerBreakdown breakdown={setup.score_breakdown} />
                </div>
                {/* Levels */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 10 }}>
                  {[
                    { l: "Entry Zone", v: `${setup.entry_low} – ${setup.entry_high}`, c: "var(--text-primary)" },
                    { l: "Stop Loss", v: setup.stop_loss, c: "var(--accent-red)" },
                    { l: "Target 1", v: setup.take_profit_1, c: "var(--accent-green)" },
                    { l: "R:R", v: `1:${(setup.risk_reward ?? 0).toFixed(1)}`, c: "var(--accent-blue)" },
                  ].map(f => (
                    <div key={f.l} style={{ background: "var(--bg-secondary)", borderRadius: 8, padding: "7px 10px" }}>
                      <div style={{ fontSize: "0.58rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 2 }}>{f.l}</div>
                      <div className="text-mono" style={{ fontSize: "0.76rem", fontWeight: 700, color: f.c }}>{f.v}</div>
                    </div>
                  ))}
                </div>
                {/* Exchange tags */}
                <div style={{ display: "flex", gap: 5 }}>
                  {EXCHANGES.map(ex => (
                    <span key={ex.key} className={`ex-tag ex-tag-${ex.key}`}>{ex.label}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Scanner Table V7 ── */}
      <div className="glass-card" style={{ padding: 24, border: "1px solid var(--border)" }}>
        <div className="flex-between" style={{ marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 4, height: 20, borderRadius: 99, background: "linear-gradient(180deg,#10b981,#3b82f6)" }} />
            <span style={{ fontWeight: 800, fontSize: "1rem" }}>Alpha Scanner</span>
            <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 600 }}>0-100 Layer Score</span>
          </div>
          <button className="btn-primary" style={{ padding: "8px 20px", fontSize: "0.78rem", display: "flex", alignItems: "center", gap: 8, fontWeight: 700 }}
            onClick={runManualScan} disabled={scanLoading || isLoading}>
            {scanLoading ? <><span className="animate-spin" style={{ display: "inline-block" }}>⟳</span> Analyzing…</> : "⟳ Scan All Markets"}
          </button>
        </div>

        <table className="data-table">
          <thead>
            <tr>
              <th>Pair</th>
              <th>Live Price</th>
              <th>24h Δ</th>
              <th>Trend</th>
              <th>Signal</th>
              <th style={{ textAlign: "center" }}>Layer Breakdown</th>
              <th>Score</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i}>{Array.from({ length: 7 }).map((_, j) => (
                  <td key={j}><div className="skeleton" style={{ height: 16, width: j === 0 ? 80 : 60 }} /></td>
                ))}</tr>
              ))
            ) : scannerData.length === 0 ? (
              <tr><td colSpan={7} style={{ textAlign: "center", padding: 48, color: "var(--text-muted)" }}>
                No scan data available. Click &apos;Scan All Markets&apos; to begin analysis.
              </td></tr>
            ) : (
              scannerData.map((row: any) => {
                const live = livePrices[row.symbol];
                const price = live?.price || 0;
                const change = live?.change || 0;
                const trendColor = row.trend === "BULLISH" ? "var(--accent-green)" : row.trend === "BEARISH" ? "var(--accent-red)" : "var(--accent-yellow)";

                return (
                  <tr key={row.symbol} style={{ opacity: row.hard_rejected ? 0.45 : 1, transition: "opacity 0.3s" }}>
                    {/* Pair */}
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <div style={{ width: 32, height: 32, borderRadius: 10,
                          background: "linear-gradient(135deg,rgba(59,130,246,0.2),rgba(168,85,247,0.2))",
                          display: "flex", alignItems: "center", justifyContent: "center",
                          fontSize: "0.7rem", fontWeight: 900, color: "#fff", border: "1px solid rgba(255,255,255,0.05)" }}>
                          {row.symbol.replace("USDT", "").slice(0, 3)}
                        </div>
                        <div>
                          <div style={{ fontWeight: 800, fontSize: "0.85rem" }}>{row.symbol}</div>
                          <div style={{ fontSize: "0.6rem", color: "var(--text-muted)", fontWeight: 600 }}>SWAP/USDT</div>
                        </div>
                      </div>
                    </td>
                    {/* Price */}
                    <td style={{ fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", fontSize: "0.85rem" }}>
                      {price > 0
                        ? (price > 10 ? price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : price.toFixed(5))
                        : <span className="skeleton" style={{ height: 14, width: 60, display: "inline-block" }} />}
                    </td>
                    {/* 24h */}
                    <td>
                      <span style={{
                        color: change > 0 ? "#10b981" : change < 0 ? "#ef4444" : "var(--text-muted)",
                        fontWeight: 800, background: change > 0 ? "rgba(16,185,129,0.1)" : change < 0 ? "rgba(239,68,68,0.1)" : "transparent",
                        padding: "3px 8px", borderRadius: 6, fontSize: "0.75rem", fontFamily: "'JetBrains Mono', monospace"
                      }}>
                        {change > 0 ? "+" : ""}{change.toFixed(2)}%
                      </span>
                    </td>
                    {/* Trend */}
                    <td>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: "0.75rem", fontWeight: 800, color: trendColor }}>
                        <span style={{ width: 6, height: 6, borderRadius: "50%", background: trendColor, display: "inline-block", boxShadow: `0 0 6px ${trendColor}60` }} />
                        {row.trend || "NEUTRAL"}
                      </span>
                    </td>
                    {/* Signal Tier */}
                    <td>
                      <TierBadge tier={row.signal_grade || "NO_TRADE"} />
                      {row.hard_rejected && row.rejection_reasons?.[0] && (
                        <div style={{ fontSize: "0.58rem", color: "#ef4444", marginTop: 4, fontWeight: 700, opacity: 0.8 }} className="truncate">
                          ⚠️ {row.rejection_reasons[0]}
                        </div>
                      )}
                    </td>
                    {/* Layer breakdown */}
                    <td style={{ minWidth: 160 }}>
                      <LayerBreakdown breakdown={row.score_breakdown} />
                    </td>
                    {/* Total Score */}
                    <td style={{ minWidth: 110 }}>
                      <ScoreBar score={row.signal_score ?? 0} max={100} />
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </MainLayout>
  );
}
