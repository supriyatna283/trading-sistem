"use client";

/**
 * ICT Confluence Dashboard
 * ========================
 * Shows ALL ICT signals for a symbol in one unified view:
 * FVG + Breaker + OB + Liquidity Sweep + PD Zone status + Trade Plan
 */

import { useState, useEffect, useCallback } from "react";
import { API_URL } from "@/lib/utils";

/** Adaptive precision: more decimals for low-priced coins */
const fmtPrice = (v?: number | null) => {
  if (v === undefined || v === null || isNaN(v)) return "-";
  const a = Math.abs(v);
  const d = a >= 1000 ? 2 : a >= 1 ? 4 : a >= 0.01 ? 5 : 8;
  return v.toLocaleString("en", { maximumFractionDigits: d });
};

interface ConfluenceProps {
  symbol: string;
  timeframe: string;
  htfTimeframe: string;
  autoRefresh?: boolean;
  refreshInterval?: number; // seconds
  onSetWAAlert?: (data: any) => void;
}

interface ConfluenceState {
  loading: boolean;
  fvg: any;
  ob: any;
  sweep: any;
  pd: any;
  lastUpdated: string | null;
  error: string | null;
}

const GRADE_COLOR: Record<string, string> = {
  "A+": "#10b981", "A": "#34d399", "B": "#3b82f6",
  "C": "#f59e0b", "D": "#f97316", "WAIT": "#64748b",
};

const BIAS_COLOR: Record<string, string> = {
  STRONG_BUY: "#10b981", BUY: "#34d399",
  STRONG_SELL: "#ef4444", SELL: "#f87171",
  NEUTRAL: "#64748b",
};

function Pill({ label, color, size = "sm" }: { label: string; color: string; size?: "xs" | "sm" | "lg" }) {
  const sizes = { xs: { p: "1px 5px", fs: "0.52rem" }, sm: { p: "2px 8px", fs: "0.62rem" }, lg: { p: "4px 12px", fs: "0.75rem" } };
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

const ZONE_COLOR: Record<string, string> = {
  PREMIUM: "#ef4444", EQUILIBRIUM: "#f59e0b", DISCOUNT: "#10b981", UNKNOWN: "#64748b",
};
const ZONE_LABEL: Record<string, string> = {
  PREMIUM: "🔴 PREMIUM — Sell Zone", EQUILIBRIUM: "🟡 EQUILIBRIUM — Wait", DISCOUNT: "🟢 DISCOUNT — Buy Zone", UNKNOWN: "⏳ Analyzing...",
};

export function ICTConfluenceDashboard({ symbol, timeframe, htfTimeframe, autoRefresh = true, refreshInterval = 30, onSetWAAlert }: ConfluenceProps) {
  const [state, setState] = useState<ConfluenceState>({ loading: false, fvg: null, ob: null, sweep: null, pd: null, lastUpdated: null, error: null });
  const [countdown, setCountdown] = useState(refreshInterval);

  const fetchAll = useCallback(async () => {
    setState(s => ({ ...s, loading: true, error: null }));
    try {
      const [fvgRes, obRes, sweepRes, pdRes] = await Promise.allSettled([
        fetch(`${API_URL}/api/v1/pro/fvg-breaker`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ symbol, timeframe, limit: 100 }),
        }).then(r => r.json()),
        fetch(`${API_URL}/api/v1/pro/ob-strength`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ symbol, timeframe, htf: htfTimeframe }),
        }).then(r => r.json()),
        fetch(`${API_URL}/api/v1/pro/liquidity-sweep`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ symbol, timeframe }),
        }).then(r => r.json()),
        fetch(`${API_URL}/api/v1/pro/pd-zones`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ symbol, timeframe, htf: htfTimeframe }),
        }).then(r => r.json()),
      ]);

      setState({
        loading: false,
        fvg:   fvgRes.status   === "fulfilled" ? fvgRes.value   : null,
        ob:    obRes.status    === "fulfilled" ? obRes.value    : null,
        sweep: sweepRes.status === "fulfilled" ? sweepRes.value : null,
        pd:    pdRes.status    === "fulfilled" ? pdRes.value?.pd_zone ?? pdRes.value : null,
        lastUpdated: new Date().toLocaleTimeString("id-ID"),
        error: null,
      });
      setCountdown(refreshInterval);
    } catch (e: any) {
      setState(s => ({ ...s, loading: false, error: e.message }));
    }
  }, [symbol, timeframe, htfTimeframe, refreshInterval]);

  // Auto-fetch on symbol/TF change
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

  const fvg = state.fvg;
  const ob = state.ob;
  const sweep = state.sweep;
  const pd = state.pd;

  // Compute overall confluence score (4 dimensions: FVG, OB, Sweep, PD Zone)
  const computeConfluence = () => {
    let score = 0;
    let signals: string[] = [];
    if (fvg?.ict_setup?.total >= 2) { score += 25; signals.push("FVG+Breaker"); }
    if (ob?.best_ob?.grade === "A+" || ob?.best_ob?.grade === "A") { score += 25; signals.push("OB A+"); }
    if (sweep?.latest_sweep?.is_confirmed) { score += 20; signals.push("Sweep Confirmed"); }
    if (sweep?.bias_from_sweep) { score += 10; signals.push("Sweep Bias"); }
    if (pd?.trade_allowed) { score += 15; signals.push(`${pd.zone} Zone`); }
    if (pd?.is_in_ote) { score += 5; signals.push("In OTE"); }
    return { score: Math.min(100, score), signals };
  };

  const { score: confluenceScore, signals: activeSignals } = computeConfluence();
  const confluenceGrade = confluenceScore >= 80 ? "A+" : confluenceScore >= 65 ? "A" : confluenceScore >= 50 ? "B" : confluenceScore >= 35 ? "C" : "D";

  // Build trade plan from available data
  const buildTradePlan = () => {
    const bias = fvg?.signals?.entry_bias;
    if (!bias || bias === "NEUTRAL") return null;
    let entry = null;
    if (bias.includes("BUY")) {
      entry = fvg?.nearest?.bullish_fvg?.entry_zone;
    } else if (bias.includes("SELL")) {
      entry = fvg?.nearest?.bearish_fvg?.entry_zone;
    }
    return { entry, bias, fvgSignal: fvg?.signals?.fvg_signal, breakerSignal: fvg?.signals?.breaker_signal };
  };
  const plan = buildTradePlan();

  const freshFVGs = (fvg?.bullish_fvgs || []).filter((f: any) => f.status === "FRESH").length
    + (fvg?.bearish_fvgs || []).filter((f: any) => f.status === "FRESH").length;
  const activeOBs = ob?.order_blocks?.filter((o: any) => o.is_fresh && o.is_tradeable).length || 0;
  const confirmedSweeps = sweep?.confirmed_count || 0;

  return (
    <div>
      {/* ── Header ── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div>
            <div style={{ fontWeight: 900, fontSize: "0.95rem" }}>🧠 ICT Confluence</div>
            <div style={{ fontSize: "0.6rem", color: "var(--text-muted)" }}>
              {symbol} · {timeframe} · {state.lastUpdated ? `Updated ${state.lastUpdated}` : "Loading..."}
            </div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {autoRefresh && (
            <div style={{ fontSize: "0.6rem", color: "var(--text-muted)", padding: "4px 8px", borderRadius: 6, background: "rgba(255,255,255,0.04)", border: "1px solid var(--border)" }}>
              🔄 {countdown}s
            </div>
          )}
          <button onClick={fetchAll} disabled={state.loading} style={{ padding: "6px 14px", borderRadius: 8, background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.3)", color: "#6366f1", fontSize: "0.7rem", fontWeight: 800, cursor: "pointer" }}>
            {state.loading ? "⟳ Analyzing..." : "⚡ Analyze"}
          </button>
        </div>
      </div>

      {/* ── Confluence Score Card ── */}
      <div style={{ padding: "16px 20px", borderRadius: 14, background: `${GRADE_COLOR[confluenceGrade]}08`, border: `1px solid ${GRADE_COLOR[confluenceGrade]}30`, marginBottom: 16, display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
        {/* Score Ring */}
        <div style={{ position: "relative", width: 90, height: 90, flexShrink: 0 }}>
          <svg width={90} height={90} viewBox="0 0 90 90">
            <circle cx={45} cy={45} r={32} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={7} />
            <circle cx={45} cy={45} r={32} fill="none" stroke={GRADE_COLOR[confluenceGrade]} strokeWidth={7}
              strokeDasharray={`${(confluenceScore / 100) * (2 * Math.PI * 32)} ${2 * Math.PI * 32}`}
              strokeLinecap="round" transform="rotate(-90 45 45)"
              style={{ transition: "stroke-dasharray .8s ease", filter: `drop-shadow(0 0 6px ${GRADE_COLOR[confluenceGrade]}60)` }} />
          </svg>
          <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 1 }}>
            <div style={{ fontSize: "1.6rem", fontWeight: 900, color: GRADE_COLOR[confluenceGrade], lineHeight: 1, letterSpacing: "-0.05em", textShadow: `0 0 12px ${GRADE_COLOR[confluenceGrade]}80` }}>
              {confluenceGrade}
            </div>
            <div style={{ fontSize: "0.5rem", color: "rgba(255,255,255,0.45)", fontWeight: 700 }}>{confluenceScore}/100</div>
          </div>
        </div>

        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 900, fontSize: "0.9rem", marginBottom: 8 }}>
            Overall ICT Confluence — {symbol}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
            {activeSignals.map(s => <Pill key={s} label={s} color="#10b981" size="xs" />)}
            {activeSignals.length === 0 && <span style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>Belum ada sinyal terkonfirmasi</span>}
          </div>
          <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
            {[
              { label: "Fresh FVGs",    val: freshFVGs,       color: "#6366f1" },
              { label: "Tradeable OBs", val: activeOBs,       color: "#f59e0b" },
              { label: "Sweeps",        val: confirmedSweeps, color: "#ef4444" },
              { label: "PD Zone",       val: pd?.zone || "—", color: pd?.trade_allowed ? "#10b981" : "#64748b", isStr: true },
            ].map(item => (
              <div key={item.label} style={{ textAlign: "center", minWidth: 48 }}>
                <div style={{ fontSize: (item as any).isStr ? "0.72rem" : "1.1rem", fontWeight: 900, color: item.color }}>{item.val}</div>
                <div style={{ fontSize: "0.52rem", color: "var(--text-muted)" }}>{item.label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* WA Alert button — show always after analysis */}
        {onSetWAAlert && confluenceScore > 0 && (
          <button
            onClick={() => onSetWAAlert({ symbol, score: confluenceScore, grade: confluenceGrade, signals: activeSignals })}
            style={{
              padding: "10px 16px", borderRadius: 10, cursor: "pointer", whiteSpace: "nowrap",
              background: confluenceScore >= 50 ? "rgba(16,185,129,0.15)" : "rgba(100,116,139,0.15)",
              border: `1px solid ${confluenceScore >= 50 ? "rgba(16,185,129,0.4)" : "rgba(100,116,139,0.3)"}`,
              color: confluenceScore >= 50 ? "#10b981" : "#94a3b8",
              fontSize: "0.72rem", fontWeight: 800,
            }}
          >
            📱 {confluenceScore >= 50 ? "Set WA Alert" : "WA (Low Score)"}
          </button>
        )}
      </div>

      {/* ── Signal Grid ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 14, marginBottom: 14 }}>

        {/* FVG Section */}
        <Section title="Fair Value Gaps" icon="⬜" color="#6366f1">
          {!fvg ? (
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>Click Analyze to load FVG data</div>
          ) : (
            <>
              <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
                <Pill label={fvg.signals?.entry_bias || "—"} color={BIAS_COLOR[fvg.signals?.entry_bias] || "#64748b"} />
                <Pill label={`Score ${fvg.signals?.confluence_score || 0}/100`} color={GRADE_COLOR[fvg.ict_setup?.grade] || "#64748b"} size="xs" />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 10 }}>
                {[
                  { label: "Fresh FVG", val: fvg.summary?.fresh_fvgs, color: "#10b981" },
                  { label: "Inverted", val: fvg.summary?.inverted_fvgs, color: "#a78bfa" },
                  { label: "Institutional", val: fvg.summary?.institutional_fvgs, color: "#6366f1" },
                ].map(i => (
                  <div key={i.label} style={{ padding: "8px", borderRadius: 8, background: "rgba(255,255,255,0.03)", textAlign: "center" }}>
                    <div style={{ fontSize: "1rem", fontWeight: 900, color: i.color }}>{i.val ?? 0}</div>
                    <div style={{ fontSize: "0.52rem", color: "var(--text-muted)" }}>{i.label}</div>
                  </div>
                ))}
              </div>
              {/* Nearest FVG */}
              {fvg.nearest?.bullish_fvg && (
                <div style={{ padding: "8px 10px", borderRadius: 8, background: "rgba(16,185,129,0.06)", border: "1px solid rgba(16,185,129,0.2)", marginBottom: 6, fontSize: "0.65rem" }}>
                  <div style={{ fontWeight: 700, color: "#10b981", marginBottom: 4 }}>📍 Nearest Bull FVG</div>
                  <div style={{ display: "flex", gap: 10, color: "var(--text-muted)" }}>
                    <span>Zone: <strong style={{ color: "#fff" }}>{fvg.nearest.bullish_fvg.gap_low?.toLocaleString("en", { maximumFractionDigits: 2 })} – {fvg.nearest.bullish_fvg.gap_high?.toLocaleString("en", { maximumFractionDigits: 2 })}</strong></span>
                    <span>CE: <strong style={{ color: "#f59e0b" }}>{fvg.nearest.bullish_fvg.ce_level?.toLocaleString("en", { maximumFractionDigits: 2 })}</strong></span>
                  </div>
                </div>
              )}
              {fvg.nearest?.bearish_fvg && (
                <div style={{ padding: "8px 10px", borderRadius: 8, background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.2)", fontSize: "0.65rem" }}>
                  <div style={{ fontWeight: 700, color: "#ef4444", marginBottom: 4 }}>📍 Nearest Bear FVG</div>
                  <div style={{ display: "flex", gap: 10, color: "var(--text-muted)" }}>
                    <span>Zone: <strong style={{ color: "#fff" }}>{fvg.nearest.bearish_fvg.gap_low?.toLocaleString("en", { maximumFractionDigits: 2 })} – {fvg.nearest.bearish_fvg.gap_high?.toLocaleString("en", { maximumFractionDigits: 2 })}</strong></span>
                    <span>CE: <strong style={{ color: "#f59e0b" }}>{fvg.nearest.bearish_fvg.ce_level?.toLocaleString("en", { maximumFractionDigits: 2 })}</strong></span>
                  </div>
                </div>
              )}
            </>
          )}
        </Section>

        {/* OB Section */}
        <Section title="Order Blocks" icon="🧱" color="#f59e0b">
          {!ob ? (
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>Click Analyze to load OB data</div>
          ) : (
            <>
              <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
                <Pill label={`${ob.a_plus_count} A+ OB`} color="#f59e0b" />
                <Pill label={`${ob.total_obs} total`} color="#64748b" size="xs" />
              </div>
              {ob.best_ob ? (
                <div style={{ padding: "10px 12px", borderRadius: 10, background: `${GRADE_COLOR[ob.best_ob.grade] || "#64748b"}08`, border: `1px solid ${GRADE_COLOR[ob.best_ob.grade] || "#64748b"}25` }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                    <Pill label={`Best OB: ${ob.best_ob.type}`} color={ob.best_ob.type === "BULLISH" ? "#10b981" : "#ef4444"} />
                    <Pill label={ob.best_ob.grade} color={GRADE_COLOR[ob.best_ob.grade]} size="lg" />
                  </div>
                  <div style={{ display: "flex", gap: 12, fontSize: "0.65rem", color: "var(--text-muted)", marginBottom: 6 }}>
                    <span>Zone: <strong style={{ color: "#fff" }}>{ob.best_ob.low?.toLocaleString("en", { maximumFractionDigits: 2 })} – {ob.best_ob.high?.toLocaleString("en", { maximumFractionDigits: 2 })}</strong></span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <MiniBar v={ob.best_ob.score} color={GRADE_COLOR[ob.best_ob.grade] || "#64748b"} />
                    <span style={{ fontSize: "0.6rem", color: "var(--text-muted)", whiteSpace: "nowrap" }}>{ob.best_ob.score}/30</span>
                  </div>
                </div>
              ) : (
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>No tradeable OBs found</div>
              )}
            </>
          )}
        </Section>

        {/* Sweep Section */}
        <Section title="Liquidity Sweep" icon="🌊" color="#ef4444">
          {!sweep ? (
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>Click Analyze to load sweep data</div>
          ) : (
            <>
              <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
                {sweep.bias_from_sweep && <Pill label={sweep.bias_from_sweep} color={BIAS_COLOR[sweep.bias_from_sweep] || "#64748b"} />}
                <Pill label={`Score ${sweep.score}`} color={sweep.score >= 70 ? "#10b981" : sweep.score >= 40 ? "#f59e0b" : "#ef4444"} size="xs" />
              </div>
              {sweep.latest_sweep ? (
                <div style={{ padding: "10px 12px", borderRadius: 10, background: sweep.latest_sweep.is_confirmed ? "rgba(16,185,129,0.06)" : "rgba(239,68,68,0.05)", border: `1px solid ${sweep.latest_sweep.is_confirmed ? "rgba(16,185,129,0.2)" : "rgba(239,68,68,0.15)"}` }}>
                  <div style={{ display: "flex", gap: 6, marginBottom: 8, flexWrap: "wrap" }}>
                    <Pill label={sweep.latest_sweep.sweep_type} color="#ef4444" size="xs" />
                    <Pill label={sweep.latest_sweep.signal_grade} color={sweep.latest_sweep.is_confirmed ? "#10b981" : "#64748b"} size="xs" />
                    {sweep.latest_sweep.has_displacement && <Pill label="Displaced" color="#6366f1" size="xs" />}
                  </div>
                  <div style={{ fontSize: "0.63rem", color: "var(--text-muted)" }}>
                    Entry zone: <strong style={{ color: "#fff" }}>{fmtPrice(Math.min(sweep.latest_sweep.entry_zone_low, sweep.latest_sweep.entry_zone_high))} – {fmtPrice(Math.max(sweep.latest_sweep.entry_zone_low, sweep.latest_sweep.entry_zone_high))}</strong>
                  </div>
                </div>
              ) : (
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>No recent sweeps detected</div>
              )}
              <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                {(sweep.pools || []).slice(0, 4).map((p: any, i: number) => (
                  <div key={i} style={{ padding: "4px 8px", borderRadius: 6, background: p.swept ? "rgba(239,68,68,0.1)" : "rgba(255,255,255,0.04)", border: `1px solid ${p.swept ? "rgba(239,68,68,0.25)" : "rgba(255,255,255,0.07)"}`, fontSize: "0.58rem" }}>
                    <div style={{ color: "var(--text-muted)" }}>{p.type}</div>
                    <div style={{ fontWeight: 700, fontFamily: "monospace" }}>{p.price?.toLocaleString("en", { maximumFractionDigits: 2 })}</div>
                    {p.swept && <div style={{ color: "#ef4444", fontSize: "0.52rem" }}>SWEPT</div>}
                  </div>
                ))}
              </div>
            </>
          )}
        </Section>

        {/* PD Zone Section */}
        <Section title="P/D Zone + OTE" icon="📈" color="#3b82f6">
          {!pd ? (
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>Click Analyze to load PD Zone data</div>
          ) : (
            <>
              {/* Zone Status */}
              <div style={{ padding: "12px 14px", borderRadius: 10, background: `${ZONE_COLOR[pd.zone] || "#64748b"}10`, border: `1px solid ${ZONE_COLOR[pd.zone] || "#64748b"}30`, marginBottom: 10 }}>
                <div style={{ fontWeight: 900, fontSize: "0.85rem", color: ZONE_COLOR[pd.zone] || "#64748b", marginBottom: 6 }}>
                  {ZONE_LABEL[pd.zone] || pd.zone}
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <Pill label={pd.signal || "—"} color={BIAS_COLOR[pd.signal] || "#64748b"} size="xs" />
                  {pd.is_in_ote && <Pill label="✨ In OTE Zone" color="#a78bfa" size="xs" />}
                  {pd.trade_allowed ? <Pill label="✅ Trade Allowed" color="#10b981" size="xs" /> : <Pill label="⛔ Wait" color="#ef4444" size="xs" />}
                </div>
              </div>

              {/* OTE & Levels */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 8 }}>
                {[
                  { label: "OTE Low",   val: pd.levels?.ote_low,             color: "#10b981" },
                  { label: "OTE High",  val: pd.levels?.ote_high,            color: "#10b981" },
                  { label: "Eq. Level", val: pd.levels?.equilibrium,         color: "#f59e0b" },
                  { label: "Zone %",    val: pd.zone_pct ? `${pd.zone_pct.toFixed(1)}%` : "—", color: "#3b82f6", raw: true },
                ].map(item => (
                  <div key={item.label} style={{ padding: "7px 10px", borderRadius: 8, background: "rgba(255,255,255,0.03)", textAlign: "center" }}>
                    <div style={{ fontSize: "0.48rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 2 }}>{item.label}</div>
                    <div style={{ fontSize: "0.68rem", fontWeight: 800, fontFamily: "monospace", color: item.color }}>
                      {(item as any).raw ? item.val : (item.val as number)?.toLocaleString("en", { maximumFractionDigits: 2 }) || "—"}
                    </div>
                  </div>
                ))}
              </div>

              {/* OTE distance */}
              {pd.distance_to_ote_pct != null && !pd.is_in_ote && (
                <div style={{ padding: "6px 10px", borderRadius: 7, background: "rgba(167,139,250,0.06)", border: "1px solid rgba(167,139,250,0.2)", fontSize: "0.62rem", color: "#a78bfa" }}>
                  ★ OTE distance: <strong>{pd.distance_to_ote_pct.toFixed(2)}%</strong> away
                </div>
              )}
            </>
          )}
        </Section>
      </div>

      {/* ── Trade Plan ── */}
      {plan && (
        <div style={{ padding: "16px 20px", borderRadius: 14, background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.2)", marginBottom: 14 }}>
          <div style={{ fontWeight: 800, fontSize: "0.85rem", marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
            <span>📋 Auto Trade Plan</span>
            <Pill label={plan.bias} color={BIAS_COLOR[plan.bias] || "#64748b"} />
          </div>
          {!plan.entry ? (
             <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", padding: "10px", background: "rgba(255,255,255,0.03)", borderRadius: 8, border: "1px dashed rgba(255,255,255,0.1)" }}>
               ⚠️ Tidak ada area {plan.bias.includes("BUY") ? "Bullish" : "Bearish"} FVG/Breaker yang ditemukan untuk entry.
             </div>
          ) : (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: 8 }}>
                {[
                  { label: "ENTRY", val: plan.entry.entry, color: "#6366f1" },
                  { label: "STOP LOSS", val: plan.entry.stop_loss, color: "#ef4444" },
                  { label: "TP1", val: plan.entry.tp1, color: "#10b981" },
                  { label: "TP2", val: plan.entry.tp2, color: "#10b981" },
                  { label: "TP3", val: plan.entry.tp3, color: "#a78bfa" },
                ].map(item => (
                  <div key={item.label} style={{ padding: "10px 12px", borderRadius: 10, background: `${item.color}08`, border: `1px solid ${item.color}20`, textAlign: "center" }}>
                    <div style={{ fontSize: "0.5rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 4 }}>{item.label}</div>
                    <div style={{ fontSize: "0.72rem", fontWeight: 900, fontFamily: "monospace", color: item.color }}>
                      {item.val?.toLocaleString("en", { maximumFractionDigits: 2 }) || "—"}
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 10, display: "flex", gap: 12, fontSize: "0.65rem", color: "var(--text-muted)" }}>
                <span>R:R TP1 <strong style={{ color: "#f59e0b" }}>1:{plan.entry.rr_tp1}</strong></span>
                <span>R:R TP2 <strong style={{ color: "#10b981" }}>1:{plan.entry.rr_tp2}</strong></span>
                <span>Risk <strong style={{ color: "#ef4444" }}>{plan.entry.risk_pct?.toFixed(3)}%</strong></span>
              </div>
              {onSetWAAlert && (
                <button
                  onClick={() => onSetWAAlert({ symbol, score: confluenceScore, grade: confluenceGrade, entry: plan.entry, bias: plan.bias })}
                  style={{ marginTop: 12, padding: "8px 16px", borderRadius: 8, background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.25)", color: "#10b981", fontSize: "0.72rem", fontWeight: 800, cursor: "pointer" }}
                >
                  📱 Kirim ke WhatsApp
                </button>
              )}
            </>
          )}
        </div>
      )}

      {/* Signals list */}
      {fvg?.signals?.messages?.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {fvg.signals.messages.map((m: string, i: number) => (
            <div key={i} style={{ padding: "6px 12px", borderRadius: 6, background: "rgba(16,185,129,0.06)", border: "1px solid rgba(16,185,129,0.15)", fontSize: "0.65rem", color: "#10b981" }}>
              ✅ {m}
            </div>
          ))}
          {fvg.signals.warnings.map((w: string, i: number) => (
            <div key={`w${i}`} style={{ padding: "6px 12px", borderRadius: 6, background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.15)", fontSize: "0.65rem", color: "#f59e0b" }}>
              ⚠️ {w}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}