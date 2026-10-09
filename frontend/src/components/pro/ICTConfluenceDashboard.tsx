"use client";

/**
 * ICT Confluence Dashboard — v2
 * ==============================
 * Refactored to use single /full-analysis endpoint (Bug #1).
 * Scoring now synced to backend 16-scale normalized to % (Bug #2).
 * WA Alert includes full entry/SL/TP (Bug #10).
 * Auto Trade Plan panel added (Feature #4).
 */

import { useState, useEffect, useCallback } from "react";
import { API_URL } from "@/lib/utils";
import { BacktestWinRateWidget } from "./BacktestWinRateWidget";

/** Adaptive precision for price display */
const fmtPrice = (v?: number | null) => {
  if (v === undefined || v === null || isNaN(v)) return "—";
  const a = Math.abs(v);
  const d = a >= 1000 ? 2 : a >= 1 ? 4 : a >= 0.01 ? 5 : 8;
  return v.toLocaleString("en", { maximumFractionDigits: d });
};

const fmtPct = (v?: number | null) =>
  v != null && !isNaN(v) ? `${v.toFixed(2)}%` : "—";

interface ConfluenceProps {
  symbol: string;
  timeframe: string;
  htfTimeframe: string;
  autoRefresh?: boolean;
  refreshInterval?: number;
  onSetWAAlert?: (data: any) => void;
  onLoadPosCalc?: (data: any) => void;
}

// ── Unified response shape from /full-analysis ──────────────────────────
interface FullAnalysisData {
  symbol: string;
  timeframe: string;
  htf: string;
  current_price: number;
  pd_zone: {
    zone: string;
    zone_pct: number;
    zone_color: string;
    signal: string;
    htf_bias: string;
    trade_allowed: boolean;
    is_in_ote: boolean;
    distance_to_ote_pct: number;
    levels: Record<string, number>;
    score: number;
  };
  liquidity_sweep: {
    latest_sweep: any;
    bias_from_sweep: string | null;
    confirmed_count: number;
    total_pools: number;
    pools: any[];
    score: number;
  };
  ob_strength: {
    total_obs: number;
    a_plus_count: number;
    best_ob: any;
    top_obs: any[];
    score: number;
  };
  killzone: {
    current_session: string;
    is_killzone_active: boolean;
    is_high_volume_kz: boolean;
    time_to_next: string;
    trade_advice: string;
    score: number;
  };
  fvg: {
    summary: any;
    nearest: { bullish_fvg: any; bearish_fvg: any; breaker: any };
    ict_setup: { total: number; grade: string; description: string };
    signals: { fvg_signal: string; breaker_signal: string; entry_bias: string; confluence_score: number; messages: string[]; warnings: string[] };
    bullish_fvgs: any[];
    bearish_fvgs: any[];
  };
  trade_plan: {
    bias: string;
    entry: number;
    stop_loss: number;
    tp1: number;
    tp2: number;
    tp3: number;
    rr_tp1: number;
    rr_tp2: number;
    risk_pct: number;
    quality: string;
    pd_zone: string;
    killzone: string;
    is_killzone: boolean;
    in_ote: boolean;
    confidence: number;
    exit_strategy?: {
      tp1_action: string;
      tp2_action: string;
      tp3_action: string;
    };
  } | null;
  confluence: {
    total_score: number;
    max_score: number;
    score_pct: number;
    grade: string;
    bias: string;
    signal: string;
    macro_restricted: boolean;
    macro_message: string;
    breakdown: { pd_zone: number; sweep: number; ob: number; killzone: number };
    smt?: { is_divergent: boolean; type: string; description: string };
    volume_profile?: { poc_price: number; vah_price: number; val_price: number };
  };
}

// ── Color maps ────────────────────────────────────────────────────────────
const GRADE_COLOR: Record<string, string> = {
  "A+": "#10b981", A: "#34d399", B: "#3b82f6",
  C: "#f59e0b", D: "#f97316", WEAK: "#64748b", WAIT: "#64748b",
};
const BIAS_COLOR: Record<string, string> = {
  STRONG_BUY: "#10b981", BUY: "#34d399",
  STRONG_SELL: "#ef4444", SELL: "#f87171",
  NEUTRAL: "#64748b",
};
const ZONE_COLOR: Record<string, string> = {
  PREMIUM: "#ef4444", EQUILIBRIUM: "#f59e0b", DISCOUNT: "#10b981", UNKNOWN: "#64748b",
};

// ── Small reusable components ────────────────────────────────────────────
function Pill({ label, color, size = "sm" }: { label: string; color: string; size?: "xs" | "sm" | "lg" }) {
  const sizes = { xs: { p: "1px 5px", fs: "0.52rem" }, sm: { p: "2px 8px", fs: "0.62rem" }, lg: { p: "5px 14px", fs: "0.75rem" } };
  const s = sizes[size];
  return (
    <span style={{ padding: s.p, borderRadius: 5, fontSize: s.fs, fontWeight: 800, background: `${color}20`, color, border: `1px solid ${color}40`, whiteSpace: "nowrap" }}>
      {label}
    </span>
  );
}

function MiniBar({ v, max = 100, color = "#3b82f6" }: { v: number; max?: number; color?: string }) {
  return (
    <div style={{ height: 4, borderRadius: 99, background: "rgba(255,255,255,0.05)", overflow: "hidden", flex: 1 }}>
      <div style={{ height: "100%", width: `${Math.min(100, (v / max) * 100)}%`, background: color, borderRadius: 99, transition: "width .6s" }} />
    </div>
  );
}

function Section({ title, icon, color, children }: { title: string; icon: string; color: string; children: React.ReactNode }) {
  return (
    <div style={{ borderRadius: 14, background: `${color}05`, border: `1px solid ${color}20`, overflow: "hidden" }}>
      <div style={{ padding: "10px 16px", background: `${color}10`, borderBottom: `1px solid ${color}20`, display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: "1rem" }}>{icon}</span>
        <span style={{ fontWeight: 800, fontSize: "0.8rem", color }}>{title}</span>
      </div>
      <div style={{ padding: "14px 16px" }}>{children}</div>
    </div>
  );
}

// ── Score breakdown bar ───────────────────────────────────────────────────
function ScoreBreakdown({ breakdown, maxPer }: { breakdown: Record<string, number>; maxPer: Record<string, number> }) {
  const labels: Record<string, string> = { pd_zone: "P/D Zone", sweep: "Sweep", ob: "OB", killzone: "Killzone" };
  const colors: Record<string, string> = { pd_zone: "#6366f1", sweep: "#ef4444", ob: "#f59e0b", killzone: "#10b981" };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {Object.entries(breakdown).map(([k, v]) => {
        const max = maxPer[k] || 4;
        const pct = Math.min(100, (v / max) * 100);
        const clr = colors[k] || "#64748b";
        return (
          <div key={k} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: "0.58rem", color: "var(--text-muted)", width: 60, flexShrink: 0 }}>{labels[k] || k}</span>
            <div style={{ flex: 1, height: 5, borderRadius: 99, background: "rgba(255,255,255,0.05)", overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${pct}%`, background: clr, borderRadius: 99, transition: "width .6s" }} />
            </div>
            <span style={{ fontSize: "0.58rem", color: clr, fontWeight: 800, width: 28, textAlign: "right", flexShrink: 0 }}>{v}/{max}</span>
          </div>
        );
      })}
    </div>
  );
}

// ── Trade Plan Card (Feature #4) ─────────────────────────────────────────
function TradePlanCard({ plan, symbol, onWA, onLoadPosCalc }: { plan: NonNullable<FullAnalysisData["trade_plan"]>; symbol: string; onWA?: () => void; onLoadPosCalc?: () => void }) {
  const isBuy = plan.bias.includes("BUY");
  const accentColor = isBuy ? "#10b981" : "#ef4444";
  const qualityColors: Record<string, string> = { IDEAL: "#10b981", GOOD: "#3b82f6", VALID: "#f59e0b" };
  const qColor = qualityColors[plan.quality] || "#64748b";

  return (
    <div style={{
      borderRadius: 16, overflow: "hidden",
      border: `1px solid ${accentColor}35`,
      background: `${accentColor}06`,
      boxShadow: `0 4px 24px ${accentColor}10`,
    }}>
      {/* Header */}
      <div style={{ padding: "12px 18px", background: `${accentColor}12`, borderBottom: `1px solid ${accentColor}20`, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: "1.1rem" }}>{isBuy ? "📋" : "📋"}</span>
          <div>
            <div style={{ fontWeight: 900, fontSize: "0.9rem", color: accentColor }}>Auto Trade Plan</div>
            <div style={{ fontSize: "0.58rem", color: "var(--text-muted)", marginTop: 1 }}>
              {symbol} · {plan.pd_zone} Zone · {plan.killzone?.replace(/_/g, " ")}
              {plan.in_ote && " · ✨ In OTE"}
              {plan.is_killzone && " · 🔥 Killzone Active"}
            </div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <Pill label={plan.bias} color={BIAS_COLOR[plan.bias] || accentColor} />
          <Pill label={plan.quality || "VALID"} color={qColor} size="xs" />
          <Pill label={`${plan.confidence}% conf.`} color={plan.confidence >= 60 ? "#10b981" : plan.confidence >= 40 ? "#f59e0b" : "#ef4444"} size="xs" />
        </div>
      </div>

      {/* Entry / SL / TP Grid */}
      <div style={{ padding: "16px 18px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr 1fr", gap: 8, marginBottom: 14 }}>
          {[
            { label: "ENTRY",     val: plan.entry,     color: "#6366f1", icon: "🎯" },
            { label: "STOP LOSS", val: plan.stop_loss,  color: "#ef4444", icon: "🛑" },
            { label: "TP1",       val: plan.tp1,        color: "#10b981", icon: "✅" },
            { label: "TP2",       val: plan.tp2,        color: "#10b981", icon: "✅" },
            { label: "TP3",       val: plan.tp3,        color: "#a78bfa", icon: "🏆" },
          ].map(item => (
            <div key={item.label} style={{ padding: "10px 12px", borderRadius: 10, background: `${item.color}08`, border: `1px solid ${item.color}25`, textAlign: "center" }}>
              <div style={{ fontSize: "0.5rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 3, letterSpacing: "0.06em" }}>{item.icon} {item.label}</div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.7rem", fontWeight: 900, color: item.color }}>
                {fmtPrice(item.val)}
              </div>
            </div>
          ))}
        </div>

        {/* R:R + Risk row */}
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 14 }}>
          {[
            { label: "R:R TP1", val: plan.rr_tp1 ? `1:${plan.rr_tp1}` : "—", color: "#f59e0b" },
            { label: "R:R TP2", val: plan.rr_tp2 ? `1:${plan.rr_tp2}` : "—", color: "#10b981" },
            { label: "Risk %",  val: fmtPct(plan.risk_pct),                  color: "#ef4444" },
          ].map(f => (
            <div key={f.label} style={{ flex: 1, padding: "8px 12px", borderRadius: 8, background: "rgba(255,255,255,0.03)", border: "1px solid var(--border)", textAlign: "center", minWidth: 70 }}>
              <div style={{ fontSize: "0.5rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 3 }}>{f.label}</div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.78rem", fontWeight: 800, color: f.color }}>{f.val}</div>
            </div>
          ))}
        </div>

        {/* Exit Strategy Framework */}
        {plan.exit_strategy && (
          <div style={{ marginBottom: 14, padding: "10px 14px", borderRadius: 10, background: "rgba(255,255,255,0.02)", border: "1px dashed rgba(255,255,255,0.1)" }}>
            <div style={{ fontSize: "0.6rem", textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 6, fontWeight: 800 }}>📉 Exit Strategy Framework</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <Pill label="TP1" color="#10b981" size="xs" />
                <span style={{ fontSize: "0.65rem", color: "#e2e8f0" }}>{plan.exit_strategy.tp1_action}</span>
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <Pill label="TP2" color="#3b82f6" size="xs" />
                <span style={{ fontSize: "0.65rem", color: "#e2e8f0" }}>{plan.exit_strategy.tp2_action}</span>
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <Pill label="TP3" color="#a78bfa" size="xs" />
                <span style={{ fontSize: "0.65rem", color: "#e2e8f0" }}>{plan.exit_strategy.tp3_action}</span>
              </div>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div style={{ display: "flex", gap: 10 }}>
          {onLoadPosCalc && (
            <button onClick={onLoadPosCalc} style={{
              flex: 1, padding: "10px", borderRadius: 10, cursor: "pointer",
              background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.3)",
              color: "#818cf8", fontSize: "0.78rem", fontWeight: 800, letterSpacing: "0.03em",
              display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              transition: "all 0.2s",
            }}
              onMouseEnter={e => (e.currentTarget.style.background = "rgba(99,102,241,0.2)")}
              onMouseLeave={e => (e.currentTarget.style.background = "rgba(99,102,241,0.1)")}
            >
              🔢 Load Position Calc
            </button>
          )}
          
          {/* WA Button */}
          {onWA && (
            <button onClick={onWA} style={{
              flex: 1, padding: "10px", borderRadius: 10, cursor: "pointer",
              background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.3)",
              color: "#10b981", fontSize: "0.78rem", fontWeight: 800, letterSpacing: "0.03em",
              display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              transition: "all 0.2s",
            }}
              onMouseEnter={e => (e.currentTarget.style.background = "rgba(16,185,129,0.2)")}
              onMouseLeave={e => (e.currentTarget.style.background = "rgba(16,185,129,0.1)")}
            >
              📱 Kirim ke WA
            </button>
          )}
        </div>
      </div>
    </div>
  );
}


// ── Main component ────────────────────────────────────────────────────────
export function ICTConfluenceDashboard({
  symbol, timeframe, htfTimeframe,
  autoRefresh = true, refreshInterval = 30,
  onSetWAAlert, onLoadPosCalc,
}: ConfluenceProps) {
  const [data, setData] = useState<FullAnalysisData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(refreshInterval);

  // Bug #1 fix: single /full-analysis call instead of 4 parallel calls
  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/v1/pro/full-analysis`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, timeframe, htf: htfTimeframe }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const json: FullAnalysisData = await res.json();
      setData(json);
      setLastUpdated(new Date().toLocaleTimeString("id-ID"));
      setCountdown(refreshInterval);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe, htfTimeframe, refreshInterval]);

  useEffect(() => { fetchAll(); }, [symbol, timeframe, htfTimeframe]);

  // Auto-refresh countdown
  useEffect(() => {
    if (!autoRefresh) return;
    const iv = setInterval(() => {
      setCountdown(c => {
        if (c <= 1) { fetchAll(); return refreshInterval; }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(iv);
  }, [autoRefresh, refreshInterval, fetchAll]);

  // Bug #10 fix: WA Alert now includes full trade plan
  const handleWAAlert = useCallback(() => {
    if (!onSetWAAlert || !data) return;
    const plan = data.trade_plan;
    onSetWAAlert({
      symbol: data.symbol,
      score: data.confluence.score_pct,
      grade: data.confluence.grade,
      signals: [data.confluence.signal, data.confluence.bias],
      bias: data.confluence.bias,
      // Include full entry plan so page.tsx WA formatter has the data
      entry: plan ? {
        entry: plan.entry,
        stop_loss: plan.stop_loss,
        tp1: plan.tp1,
        tp2: plan.tp2,
        tp3: plan.tp3,
        rr_tp1: plan.rr_tp1,
        rr_tp2: plan.rr_tp2,
        risk_pct: plan.risk_pct,
      } : undefined,
    });
  }, [onSetWAAlert, data]);

  // Bug #2 fix: use backend score_pct (already normalized from 16-scale to 0–100%)
  const score = data?.confluence.score_pct ?? 0;
  const grade = data?.confluence.grade ?? "WAIT";
  const gradeColor = GRADE_COLOR[grade] || "#64748b";

  const freshFVGs = data
    ? (data.fvg.bullish_fvgs?.filter((f: any) => f.status === "FRESH").length || 0)
      + (data.fvg.bearish_fvgs?.filter((f: any) => f.status === "FRESH").length || 0)
    : 0;

  return (
    <div>
      {/* ── Header ── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <div>
          <div style={{ fontWeight: 900, fontSize: "0.95rem" }}>🧠 ICT Confluence Dashboard</div>
          <div style={{ fontSize: "0.6rem", color: "var(--text-muted)" }}>
            {symbol} · {timeframe}/{htfTimeframe} · {lastUpdated ? `Updated ${lastUpdated}` : "Loading..."}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {autoRefresh && (
            <div style={{ fontSize: "0.6rem", color: "var(--text-muted)", padding: "4px 8px", borderRadius: 6, background: "rgba(255,255,255,0.04)", border: "1px solid var(--border)" }}>
              🔄 {countdown}s
            </div>
          )}
          <button onClick={fetchAll} disabled={loading} style={{ padding: "6px 14px", borderRadius: 8, background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.3)", color: "#6366f1", fontSize: "0.7rem", fontWeight: 800, cursor: loading ? "not-allowed" : "pointer" }}>
            {loading ? "⟳ Analyzing..." : "⚡ Analyze"}
          </button>
        </div>
      </div>

      {/* ── Error Banner ── */}
      {error && (
        <div style={{ padding: "10px 16px", borderRadius: 10, background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)", color: "#ef4444", fontSize: "0.72rem", marginBottom: 14 }}>
          ⚠️ {error}
        </div>
      )}

      {/* ── Macro News Alert (Sprint D) ── */}
      {data?.confluence.macro_restricted && (
        <div style={{ padding: "12px 18px", borderRadius: 12, background: "rgba(239,68,68,0.15)", border: "1px solid rgba(239,68,68,0.4)", color: "#fca5a5", fontSize: "0.8rem", marginBottom: 16, display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: "1.5rem" }}>🚨</span>
          <div>
            <div style={{ fontWeight: 900, color: "#ef4444", marginBottom: 4 }}>MACRO NEWS WARNING</div>
            <div style={{ fontSize: "0.7rem", color: "#fecaca" }}>{data.confluence.macro_message} (Trade Plan Disabled)</div>
          </div>
        </div>
      )}

      {/* ── SMT Divergence Alert (Sprint D) ── */}
      {data?.confluence.smt?.is_divergent && (
        <div style={{ padding: "12px 18px", borderRadius: 12, background: data.confluence.smt.type === "BULLISH" ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.15)", border: `1px solid ${data.confluence.smt.type === "BULLISH" ? "rgba(16,185,129,0.4)" : "rgba(239,68,68,0.4)"}`, color: data.confluence.smt.type === "BULLISH" ? "#6ee7b7" : "#fca5a5", fontSize: "0.8rem", marginBottom: 16, display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: "1.5rem" }}>👀</span>
          <div>
            <div style={{ fontWeight: 900, color: data.confluence.smt.type === "BULLISH" ? "#10b981" : "#ef4444", marginBottom: 4 }}>{data.confluence.smt.type} SMT DIVERGENCE DETECTED</div>
            <div style={{ fontSize: "0.7rem", color: data.confluence.smt.type === "BULLISH" ? "#a7f3d0" : "#fecaca" }}>{data.confluence.smt.description}</div>
          </div>
        </div>
      )}

      {/* ── Confluence Score Card (Bug #2 fixed: uses backend score_pct) ── */}
      {data && (
        <div style={{ padding: "16px 20px", borderRadius: 14, background: `${gradeColor}08`, border: `1px solid ${gradeColor}30`, marginBottom: 16, display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
          {/* Score Ring */}
          <div style={{ position: "relative", width: 90, height: 90, flexShrink: 0 }}>
            <svg width={90} height={90} viewBox="0 0 90 90">
              <circle cx={45} cy={45} r={32} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={7} />
              <circle cx={45} cy={45} r={32} fill="none" stroke={gradeColor} strokeWidth={7}
                strokeDasharray={`${(score / 100) * (2 * Math.PI * 32)} ${2 * Math.PI * 32}`}
                strokeLinecap="round" transform="rotate(-90 45 45)"
                style={{ transition: "stroke-dasharray .8s ease", filter: `drop-shadow(0 0 6px ${gradeColor}60)` }} />
            </svg>
            <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 1 }}>
              <div style={{ fontSize: "1.6rem", fontWeight: 900, color: gradeColor, lineHeight: 1, letterSpacing: "-0.05em", textShadow: `0 0 12px ${gradeColor}80` }}>
                {grade}
              </div>
              <div style={{ fontSize: "0.5rem", color: "rgba(255,255,255,0.45)", fontWeight: 700 }}>{score.toFixed(0)}%</div>
            </div>
          </div>

          <div style={{ flex: 1, minWidth: 180 }}>
            <div style={{ fontWeight: 900, fontSize: "0.9rem", marginBottom: 6 }}>
              {data.confluence.signal} — {symbol}
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 10 }}>
              <Pill label={data.confluence.bias} color={BIAS_COLOR[data.confluence.bias] || "#64748b"} size="xs" />
              <Pill label={data.pd_zone.zone} color={ZONE_COLOR[data.pd_zone.zone] || "#64748b"} size="xs" />
              {data.pd_zone.is_in_ote && <Pill label="✨ In OTE" color="#a78bfa" size="xs" />}
              {data.killzone.is_killzone_active && <Pill label="🔥 Killzone Active" color="#f59e0b" size="xs" />}
            </div>
            {/* Score breakdown bars */}
            <ScoreBreakdown
              breakdown={data.confluence.breakdown}
              maxPer={{ pd_zone: 4, sweep: 5, ob: 5, killzone: 3 }}
            />
          </div>

          {/* Stats */}
          <div style={{ display: "flex", gap: 14 }}>
            {[
              { label: "Fresh FVGs",  val: freshFVGs,                        color: "#6366f1" },
              { label: "A+ OBs",      val: data.ob_strength.a_plus_count,    color: "#f59e0b" },
              { label: "Sweeps",      val: data.liquidity_sweep.confirmed_count, color: "#ef4444" },
            ].map(item => (
              <div key={item.label} style={{ textAlign: "center", minWidth: 44 }}>
                <div style={{ fontSize: "1.2rem", fontWeight: 900, color: item.color, lineHeight: 1 }}>{item.val}</div>
                <div style={{ fontSize: "0.5rem", color: "var(--text-muted)", marginTop: 2 }}>{item.label}</div>
              </div>
            ))}
          </div>

          {/* WA Alert button (Bug #10 fix: sends full entry data) */}
          {onSetWAAlert && (
            <button
              onClick={handleWAAlert}
              style={{
                padding: "10px 16px", borderRadius: 10, cursor: "pointer", whiteSpace: "nowrap",
                background: score >= 50 ? "rgba(16,185,129,0.15)" : "rgba(100,116,139,0.15)",
                border: `1px solid ${score >= 50 ? "rgba(16,185,129,0.4)" : "rgba(100,116,139,0.3)"}`,
                color: score >= 50 ? "#10b981" : "#94a3b8",
                fontSize: "0.72rem", fontWeight: 800,
              }}
            >
              📱 {score >= 50 ? "Set WA Alert" : "WA (Low Score)"}
            </button>
          )}
        </div>
      )}

      {/* ── Loading skeleton ── */}
      {loading && !data && (
        <div style={{ padding: "60px 0", textAlign: "center" }}>
          <div style={{ width: 40, height: 40, border: "3px solid rgba(99,102,241,0.2)", borderTopColor: "#6366f1", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto" }} />
          <div style={{ marginTop: 14, fontSize: "0.82rem", color: "#6366f1", fontWeight: 700 }}>Analyzing all ICT signals...</div>
        </div>
      )}

      {/* ── Signal Grid ── */}
      {data && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14, marginBottom: 14 }}>

            {/* FVG Section */}
            <Section title="Fair Value Gaps" icon="⬜" color="#6366f1">
              <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
                <Pill label={data.fvg.signals.entry_bias || "—"} color={BIAS_COLOR[data.fvg.signals.entry_bias] || "#64748b"} />
                <Pill label={`Score ${data.fvg.ict_setup?.total || 0}/100`} color={GRADE_COLOR[data.fvg.ict_setup?.grade] || "#64748b"} size="xs" />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 10 }}>
                {[
                  { label: "Fresh FVG",     val: data.fvg.summary?.fresh_fvgs,       color: "#10b981" },
                  { label: "Inverted",      val: data.fvg.summary?.inverted_fvgs,    color: "#a78bfa" },
                  { label: "Institutional", val: data.fvg.summary?.institutional_fvgs, color: "#6366f1" },
                ].map(i => (
                  <div key={i.label} style={{ padding: "8px", borderRadius: 8, background: "rgba(255,255,255,0.03)", textAlign: "center" }}>
                    <div style={{ fontSize: "1rem", fontWeight: 900, color: i.color }}>{i.val ?? 0}</div>
                    <div style={{ fontSize: "0.52rem", color: "var(--text-muted)" }}>{i.label}</div>
                  </div>
                ))}
              </div>
              {data.fvg.nearest?.bullish_fvg && (
                <div style={{ padding: "8px 10px", borderRadius: 8, background: "rgba(16,185,129,0.06)", border: "1px solid rgba(16,185,129,0.2)", marginBottom: 6, fontSize: "0.65rem" }}>
                  <div style={{ fontWeight: 700, color: "#10b981", marginBottom: 4 }}>📍 Nearest Bull FVG</div>
                  <div style={{ display: "flex", gap: 10, color: "var(--text-muted)", flexWrap: "wrap" }}>
                    <span>Zone: <strong style={{ color: "#fff" }}>{fmtPrice(data.fvg.nearest.bullish_fvg.gap_low)} – {fmtPrice(data.fvg.nearest.bullish_fvg.gap_high)}</strong></span>
                    <span>CE: <strong style={{ color: "#f59e0b" }}>{fmtPrice(data.fvg.nearest.bullish_fvg.ce_level)}</strong></span>
                  </div>
                </div>
              )}
              {data.fvg.nearest?.bearish_fvg && (
                <div style={{ padding: "8px 10px", borderRadius: 8, background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.2)", fontSize: "0.65rem" }}>
                  <div style={{ fontWeight: 700, color: "#ef4444", marginBottom: 4 }}>📍 Nearest Bear FVG</div>
                  <div style={{ display: "flex", gap: 10, color: "var(--text-muted)", flexWrap: "wrap" }}>
                    <span>Zone: <strong style={{ color: "#fff" }}>{fmtPrice(data.fvg.nearest.bearish_fvg.gap_low)} – {fmtPrice(data.fvg.nearest.bearish_fvg.gap_high)}</strong></span>
                    <span>CE: <strong style={{ color: "#f59e0b" }}>{fmtPrice(data.fvg.nearest.bearish_fvg.ce_level)}</strong></span>
                  </div>
                </div>
              )}
              {/* ── FRVP Indicator (Sprint D) ── */}
              {data.confluence.volume_profile && (
                <div style={{ marginTop: 10, padding: "8px 10px", borderRadius: 8, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", fontSize: "0.65rem" }}>
                  <div style={{ fontWeight: 700, color: "#6366f1", marginBottom: 4 }}>📊 Fixed Range Volume Profile</div>
                  <div style={{ display: "flex", gap: 10, color: "var(--text-muted)", flexWrap: "wrap", justifyContent: "space-between" }}>
                    <span>VAL: <strong style={{ color: "#fff" }}>{fmtPrice(data.confluence.volume_profile.val_price)}</strong></span>
                    <span>POC: <strong style={{ color: "#f59e0b" }}>{fmtPrice(data.confluence.volume_profile.poc_price)}</strong></span>
                    <span>VAH: <strong style={{ color: "#fff" }}>{fmtPrice(data.confluence.volume_profile.vah_price)}</strong></span>
                  </div>
                </div>
              )}
            </Section>

            {/* OB Section */}
            <Section title="Order Blocks" icon="🧱" color="#f59e0b">
              <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
                <Pill label={`${data.ob_strength.a_plus_count} A+ OB`} color="#f59e0b" />
                <Pill label={`${data.ob_strength.total_obs} total`} color="#64748b" size="xs" />
              </div>
              {data.ob_strength.best_ob ? (
                <div style={{ padding: "10px 12px", borderRadius: 10, background: `${GRADE_COLOR[data.ob_strength.best_ob.grade] || "#64748b"}08`, border: `1px solid ${GRADE_COLOR[data.ob_strength.best_ob.grade] || "#64748b"}25` }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                    <Pill label={`Best: ${data.ob_strength.best_ob.type}`} color={data.ob_strength.best_ob.type === "BULLISH" ? "#10b981" : "#ef4444"} />
                    <Pill label={data.ob_strength.best_ob.grade} color={GRADE_COLOR[data.ob_strength.best_ob.grade]} size="lg" />
                  </div>
                  <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", marginBottom: 6 }}>
                    Zone: <strong style={{ color: "#fff" }}>{fmtPrice(data.ob_strength.best_ob.low)} – {fmtPrice(data.ob_strength.best_ob.high)}</strong>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <MiniBar v={data.ob_strength.best_ob.score} color={GRADE_COLOR[data.ob_strength.best_ob.grade] || "#64748b"} />
                    <span style={{ fontSize: "0.6rem", color: "var(--text-muted)", whiteSpace: "nowrap" }}>{data.ob_strength.best_ob.score}/30</span>
                  </div>
                </div>
              ) : (
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>No tradeable OBs found</div>
              )}
            </Section>

            {/* Sweep Section */}
            <Section title="Liquidity Sweep" icon="🌊" color="#ef4444">
              <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
                {data.liquidity_sweep.bias_from_sweep && <Pill label={data.liquidity_sweep.bias_from_sweep} color={BIAS_COLOR[data.liquidity_sweep.bias_from_sweep] || "#64748b"} />}
                <Pill label={`${data.liquidity_sweep.confirmed_count} confirmed`} color={data.liquidity_sweep.confirmed_count > 0 ? "#10b981" : "#64748b"} size="xs" />
                <Pill label={`Score ${data.liquidity_sweep.score}`} color={data.liquidity_sweep.score >= 3 ? "#10b981" : "#64748b"} size="xs" />
              </div>
              {data.liquidity_sweep.latest_sweep ? (
                <div style={{ padding: "10px 12px", borderRadius: 10, background: data.liquidity_sweep.latest_sweep.is_confirmed ? "rgba(16,185,129,0.06)" : "rgba(239,68,68,0.05)", border: `1px solid ${data.liquidity_sweep.latest_sweep.is_confirmed ? "rgba(16,185,129,0.2)" : "rgba(239,68,68,0.15)"}` }}>
                  <div style={{ display: "flex", gap: 6, marginBottom: 8, flexWrap: "wrap" }}>
                    <Pill label={data.liquidity_sweep.latest_sweep.sweep_type} color="#ef4444" size="xs" />
                    <Pill label={data.liquidity_sweep.latest_sweep.signal_grade} color={data.liquidity_sweep.latest_sweep.is_confirmed ? "#10b981" : "#64748b"} size="xs" />
                    {data.liquidity_sweep.latest_sweep.has_displacement && <Pill label="Displaced" color="#6366f1" size="xs" />}
                  </div>
                  <div style={{ fontSize: "0.63rem", color: "var(--text-muted)" }}>
                    Entry: <strong style={{ color: "#fff" }}>
                      {fmtPrice(Math.min(data.liquidity_sweep.latest_sweep.entry_zone_low, data.liquidity_sweep.latest_sweep.entry_zone_high))} – {fmtPrice(Math.max(data.liquidity_sweep.latest_sweep.entry_zone_low, data.liquidity_sweep.latest_sweep.entry_zone_high))}
                    </strong>
                  </div>
                </div>
              ) : (
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>No recent sweeps detected</div>
              )}
              <div style={{ display: "flex", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
                {(data.liquidity_sweep.pools || []).slice(0, 4).map((p: any, i: number) => (
                  <div key={i} style={{ padding: "4px 8px", borderRadius: 6, background: p.swept ? "rgba(239,68,68,0.1)" : "rgba(255,255,255,0.04)", border: `1px solid ${p.swept ? "rgba(239,68,68,0.25)" : "rgba(255,255,255,0.07)"}`, fontSize: "0.58rem" }}>
                    <div style={{ color: "var(--text-muted)" }}>{p.type}</div>
                    <div style={{ fontWeight: 700, fontFamily: "monospace" }}>{fmtPrice(p.price)}</div>
                    {p.swept && <div style={{ color: "#ef4444", fontSize: "0.52rem" }}>SWEPT</div>}
                  </div>
                ))}
              </div>
            </Section>

            {/* PD Zone Section */}
            <Section title="P/D Zone + OTE" icon="📈" color="#3b82f6">
              <div style={{ padding: "12px 14px", borderRadius: 10, background: `${ZONE_COLOR[data.pd_zone.zone] || "#64748b"}10`, border: `1px solid ${ZONE_COLOR[data.pd_zone.zone] || "#64748b"}30`, marginBottom: 10 }}>
                <div style={{ fontWeight: 900, fontSize: "0.85rem", color: ZONE_COLOR[data.pd_zone.zone] || "#64748b", marginBottom: 6 }}>
                  {data.pd_zone.zone === "PREMIUM" ? "🔴 PREMIUM — Sell Zone" :
                   data.pd_zone.zone === "DISCOUNT" ? "🟢 DISCOUNT — Buy Zone" :
                   data.pd_zone.zone === "EQUILIBRIUM" ? "🟡 EQUILIBRIUM — Wait" : "⏳ Analyzing..."}
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <Pill label={data.pd_zone.signal || "—"} color={BIAS_COLOR[data.pd_zone.signal] || "#64748b"} size="xs" />
                  {data.pd_zone.is_in_ote && <Pill label="✨ In OTE Zone" color="#a78bfa" size="xs" />}
                  {data.pd_zone.trade_allowed ? <Pill label="✅ Trade OK" color="#10b981" size="xs" /> : <Pill label="⛔ Wait" color="#ef4444" size="xs" />}
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 8 }}>
                {[
                  { label: "OTE Low",   val: data.pd_zone.levels?.ote_low,    color: "#10b981" },
                  { label: "OTE High",  val: data.pd_zone.levels?.ote_high,   color: "#10b981" },
                  { label: "Eq. Level", val: data.pd_zone.levels?.equilibrium, color: "#f59e0b" },
                  { label: "Zone %",    val: `${data.pd_zone.zone_pct?.toFixed(1)}%`, color: "#3b82f6", raw: true },
                ].map(item => (
                  <div key={item.label} style={{ padding: "7px 10px", borderRadius: 8, background: "rgba(255,255,255,0.03)", textAlign: "center" }}>
                    <div style={{ fontSize: "0.48rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 2 }}>{item.label}</div>
                    <div style={{ fontSize: "0.68rem", fontWeight: 800, fontFamily: "monospace", color: item.color }}>
                      {(item as any).raw ? item.val : fmtPrice(item.val as number)}
                    </div>
                  </div>
                ))}
              </div>
              {data.pd_zone.distance_to_ote_pct != null && !data.pd_zone.is_in_ote && (
                <div style={{ padding: "6px 10px", borderRadius: 7, background: "rgba(167,139,250,0.06)", border: "1px solid rgba(167,139,250,0.2)", fontSize: "0.62rem", color: "#a78bfa" }}>
                  ★ OTE distance: <strong>{data.pd_zone.distance_to_ote_pct.toFixed(2)}%</strong> away
                </div>
              )}
            </Section>
          </div>

          {/* ── Auto Trade Plan (Feature #4) ── */}
          {data.trade_plan ? (
            <div style={{ marginBottom: 14 }}>
              <BacktestWinRateWidget symbol={symbol} timeframe={timeframe} />
              <TradePlanCard
                plan={data.trade_plan}
                symbol={symbol}
                onWA={onSetWAAlert ? handleWAAlert : undefined}
                onLoadPosCalc={onLoadPosCalc ? () => onLoadPosCalc(data.trade_plan) : undefined}
              />
            </div>
          ) : (
            <div style={{ padding: "16px 20px", borderRadius: 14, background: "rgba(255,255,255,0.02)", border: "1px dashed rgba(255,255,255,0.1)", marginBottom: 14, textAlign: "center", fontSize: "0.72rem", color: "var(--text-muted)" }}>
              ⚠️ Tidak ada FVG/Breaker yang tersedia untuk generate trade plan. Tunggu setup yang lebih jelas.
            </div>
          )}

          {/* ── Signal messages ── */}
          {data.fvg?.signals?.messages?.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {data.fvg.signals.messages.map((m: string, i: number) => (
                <div key={i} style={{ padding: "6px 12px", borderRadius: 6, background: "rgba(16,185,129,0.06)", border: "1px solid rgba(16,185,129,0.15)", fontSize: "0.65rem", color: "#10b981" }}>
                  ✅ {m}
                </div>
              ))}
              {data.fvg.signals.warnings?.map((w: string, i: number) => (
                <div key={`w${i}`} style={{ padding: "6px 12px", borderRadius: 6, background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.15)", fontSize: "0.65rem", color: "#f59e0b" }}>
                  ⚠️ {w}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}