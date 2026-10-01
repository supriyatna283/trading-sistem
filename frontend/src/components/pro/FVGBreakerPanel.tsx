"use client";

import { useState, useCallback } from "react";
import { API_URL } from "@/lib/utils";

/* ─── Types ───────────────────────────────────────────── */
interface FVG {
  id: number;
  type: "BULLISH" | "BEARISH";
  gap_high: number;
  gap_low: number;
  ce_level: number;
  size: number;
  size_atr_mult: number;
  bar_idx: number;
  status: "FRESH" | "PARTIAL" | "FILLED" | "INVERTED";
  is_inverted: boolean;
  fill_pct: number;
  is_institutional: boolean;
  strength: number;
}

interface BreakerBlock {
  id: number;
  type: "BULLISH_BREAKER" | "BEARISH_BREAKER";
  ob_high: number;
  ob_low: number;
  break_price: number;
  break_direction: "UPWARD" | "DOWNWARD";
  status: "ACTIVE" | "TESTED" | "USED";
  has_returned: boolean;
  midpoint: number;
  strength: number;
}

interface FVGResult {
  current_price: number;
  summary: {
    total_fvgs: number;
    fresh_fvgs: number;
    inverted_fvgs: number;
    total_breakers: number;
  };
  bullish_fvgs: FVG[];
  bearish_fvgs: FVG[];
  top_fvgs: FVG[];
  bullish_breakers: BreakerBlock[];
  bearish_breakers: BreakerBlock[];
  nearest: {
    bullish_fvg: FVG | null;
    bearish_fvg: FVG | null;
    breaker: BreakerBlock | null;
  };
  signals: {
    fvg_signal: string;
    breaker_signal: string;
    entry_bias: string;
    setup_quality: string;
    confluence_score: number;
    messages: string[];
  };
}

/* ─── Sub-components ──────────────────────────────────── */
function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span style={{ padding: "2px 8px", borderRadius: 5, fontSize: "0.6rem", fontWeight: 800, background: `${color}18`, color, border: `1px solid ${color}35`, whiteSpace: "nowrap" }}>
      {label}
    </span>
  );
}

function StrengthBar({ value, color }: { value: number; color: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{ flex: 1, height: 4, borderRadius: 99, background: "rgba(255,255,255,0.06)" }}>
        <div style={{ height: "100%", width: `${value}%`, borderRadius: 99, background: color, transition: "width 0.6s" }} />
      </div>
      <span style={{ fontSize: "0.6rem", fontFamily: "monospace", color: "var(--text-muted)", minWidth: 26 }}>{value}</span>
    </div>
  );
}

function QualityBadge({ grade }: { grade: string }) {
  const colors: Record<string, string> = {
    "A+": "#10b981", "A": "#34d399", "B": "#3b82f6", "C": "#f59e0b", "NONE": "#64748b"
  };
  return (
    <div style={{
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      width: 40, height: 40, borderRadius: 12, fontWeight: 900, fontSize: "1rem",
      background: `${colors[grade] ?? "#64748b"}18`,
      border: `2px solid ${colors[grade] ?? "#64748b"}40`,
      color: colors[grade] ?? "#64748b",
    }}>{grade}</div>
  );
}

function FVGRow({ fvg, price }: { fvg: FVG; price: number }) {
  const isBull = fvg.type === "BULLISH";
  const color  = isBull ? "#10b981" : "#ef4444";
  const statusColor: Record<string, string> = {
    FRESH: "#10b981", PARTIAL: "#f59e0b", FILLED: "#64748b", INVERTED: "#a78bfa"
  };
  const distPct = ((price - fvg.ce_level) / price * 100).toFixed(2);

  return (
    <div style={{
      padding: "12px 14px", borderRadius: 10, marginBottom: 6,
      background: `${color}08`, border: `1px solid ${color}20`,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
          <Badge label={isBull ? "BULLISH FVG" : "BEARISH FVG"} color={color} />
          <Badge label={fvg.status} color={statusColor[fvg.status]} />
          {fvg.is_inverted && <Badge label="IFVG" color="#a78bfa" />}
          {fvg.is_institutional && <Badge label="🐳 INSTITUTIONAL" color="#6366f1" />}
        </div>
        <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>
          CE dist: <span style={{ color, fontWeight: 700 }}>{distPct}%</span>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6, marginBottom: 8 }}>
        {[
          { label: "Gap High", value: fvg.gap_high.toLocaleString("en", { maximumFractionDigits: 2 }), color: "#ef4444" },
          { label: "CE Level", value: fvg.ce_level.toLocaleString("en", { maximumFractionDigits: 2 }), color: "#f59e0b" },
          { label: "Gap Low",  value: fvg.gap_low.toLocaleString("en",  { maximumFractionDigits: 2 }), color: "#10b981" },
          { label: "ATR Mult", value: `${fvg.size_atr_mult}x`, color: "var(--text-muted)" },
        ].map(({ label, value, color: c }) => (
          <div key={label} style={{ background: "rgba(255,255,255,0.02)", borderRadius: 7, padding: "6px 8px" }}>
            <div style={{ fontSize: "0.52rem", color: "var(--text-muted)", marginBottom: 2, textTransform: "uppercase" }}>{label}</div>
            <div style={{ fontSize: "0.72rem", fontFamily: "monospace", fontWeight: 700, color: c }}>{value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: "0.58rem", color: "var(--text-muted)", whiteSpace: "nowrap" }}>Strength</span>
        <div style={{ flex: 1 }}>
          <StrengthBar value={fvg.strength} color={color} />
        </div>
        {fvg.fill_pct > 0 && (
          <span style={{ fontSize: "0.6rem", color: "#f59e0b" }}>{fvg.fill_pct.toFixed(0)}% filled</span>
        )}
      </div>
    </div>
  );
}

function BreakerRow({ bb, price }: { bb: BreakerBlock; price: number }) {
  const isBull = bb.type === "BULLISH_BREAKER";
  const color  = isBull ? "#10b981" : "#ef4444";
  const distPct = ((price - bb.midpoint) / price * 100).toFixed(2);

  return (
    <div style={{
      padding: "12px 14px", borderRadius: 10, marginBottom: 6,
      background: `${color}08`, border: `1px solid ${color}25`,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <Badge label={isBull ? "🟢 BULLISH BREAKER" : "🔴 BEARISH BREAKER"} color={color} />
          <Badge label={bb.status} color={bb.status === "ACTIVE" ? "#f59e0b" : "#64748b"} />
          {bb.has_returned && <Badge label="TESTED ✓" color="#3b82f6" />}
        </div>
        <span style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>
          {Number(distPct) > 0 ? "+" : ""}{distPct}% from price
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6, marginBottom: 8 }}>
        {[
          { label: "Zone High",  value: bb.ob_high.toLocaleString("en", { maximumFractionDigits: 2 }) },
          { label: "Midpoint",   value: bb.midpoint.toLocaleString("en", { maximumFractionDigits: 2 }), color },
          { label: "Zone Low",   value: bb.ob_low.toLocaleString("en",  { maximumFractionDigits: 2 }) },
        ].map(({ label, value, color: c }) => (
          <div key={label} style={{ background: "rgba(255,255,255,0.02)", borderRadius: 7, padding: "6px 8px" }}>
            <div style={{ fontSize: "0.52rem", color: "var(--text-muted)", marginBottom: 2, textTransform: "uppercase" }}>{label}</div>
            <div style={{ fontSize: "0.72rem", fontFamily: "monospace", fontWeight: 700, color: c ?? "var(--text-secondary)" }}>{value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: "0.58rem", color: "var(--text-muted)", whiteSpace: "nowrap" }}>Strength</span>
        <div style={{ flex: 1 }}><StrengthBar value={bb.strength} color={color} /></div>
        <span style={{ fontSize: "0.6rem", color: "var(--text-muted)" }}>
          {bb.break_direction === "UPWARD" ? "↑ Broke up" : "↓ Broke down"}
        </span>
      </div>
    </div>
  );
}

/* ─── Main Component ─────────────────────────────────── */
export function FVGBreakerPanel() {
  const [sym, setSym] = useState("BTCUSDT");
  const [tf,  setTf]  = useState("1h");
  const [data, setData] = useState<FVGResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<"fvg" | "breaker">("fvg");
  const [filterType, setFilterType] = useState<"ALL" | "BULLISH" | "BEARISH">("ALL");

  const scan = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API_URL}/api/v1/pro/fvg-breaker`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: sym, timeframe: tf, limit: 150 }),
      });
      setData(await r.json());
    } catch {}
    finally { setLoading(false); }
  }, [sym, tf]);

  const biasColor: Record<string, string> = {
    BUY: "#10b981", SELL: "#ef4444", NEUTRAL: "#64748b"
  };
  const fvgSignalColor: Record<string, string> = {
    PRICE_IN_FVG: "#f59e0b", FVG_ABOVE: "#ef4444", FVG_BELOW: "#10b981", NEUTRAL: "#64748b"
  };

  const fvgsToShow = data ? [
    ...(filterType !== "BEARISH" ? data.bullish_fvgs.filter(f => f.status !== "FILLED") : []),
    ...(filterType !== "BULLISH" ? data.bearish_fvgs.filter(f => f.status !== "FILLED") : []),
  ].sort((a, b) => b.strength - a.strength) : [];

  const breakersToShow = data ? [
    ...(filterType !== "BEARISH" ? data.bullish_breakers : []),
    ...(filterType !== "BULLISH" ? data.bearish_breakers : []),
  ].sort((a, b) => b.strength - a.strength) : [];

  return (
    <div>
      {/* Toolbar */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
        <input value={sym} onChange={e => setSym(e.target.value.toUpperCase())}
          style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: "8px 12px", color: "#fff", fontSize: "0.8rem", width: 120, fontFamily: "monospace", fontWeight: 700 }} />
        <select value={tf} onChange={e => setTf(e.target.value)}
          style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: "8px 12px", color: "#fff", fontSize: "0.8rem" }}>
          {["5m","15m","1h","4h","1d"].map(t => <option key={t}>{t}</option>)}
        </select>
        <button onClick={scan} disabled={loading} style={{ padding: "8px 20px", borderRadius: 8, background: "rgba(99,102,241,0.15)", border: "1px solid rgba(99,102,241,0.35)", color: "#6366f1", fontWeight: 800, fontSize: "0.78rem", cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}>
          {loading ? <><span style={{ animation: "spin 1s linear infinite", display: "inline-block" }}>⟳</span> Scanning...</> : "🔍 Scan FVG + Breakers"}
        </button>

        {/* Type filter */}
        <div style={{ display: "flex", gap: 4, marginLeft: "auto" }}>
          {(["ALL", "BULLISH", "BEARISH"] as const).map(f => (
            <button key={f} onClick={() => setFilterType(f)} style={{
              padding: "6px 12px", borderRadius: 7, fontSize: "0.7rem", fontWeight: 700, cursor: "pointer",
              background: filterType === f ? (f === "BULLISH" ? "rgba(16,185,129,0.15)" : f === "BEARISH" ? "rgba(239,68,68,0.15)" : "rgba(99,102,241,0.15)") : "rgba(255,255,255,0.03)",
              border: `1px solid ${filterType === f ? (f === "BULLISH" ? "rgba(16,185,129,0.4)" : f === "BEARISH" ? "rgba(239,68,68,0.4)" : "rgba(99,102,241,0.4)") : "rgba(255,255,255,0.06)"}`,
              color: filterType === f ? (f === "BULLISH" ? "#10b981" : f === "BEARISH" ? "#ef4444" : "#6366f1") : "var(--text-muted)",
            }}>{f}</button>
          ))}
        </div>
      </div>

      {!data ? (
        <div style={{ textAlign: "center", padding: "80px 0", color: "var(--text-muted)" }}>
          <div style={{ fontSize: "3.5rem", marginBottom: 16, opacity: 0.2 }}>⬜</div>
          <div style={{ fontSize: "0.9rem", fontWeight: 700, marginBottom: 8 }}>Fair Value Gap + Breaker Block Scanner</div>
          <div style={{ fontSize: "0.75rem", opacity: 0.6 }}>Deteksi imbalance harga (FVG) dan failed order block (Breaker) secara otomatis</div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

          {/* Summary Row */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10 }}>
            <div style={{ padding: "14px 16px", borderRadius: 12, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", textAlign: "center" }}>
              <div style={{ fontSize: "0.55rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 6 }}>Total FVGs</div>
              <div style={{ fontSize: "1.4rem", fontWeight: 900, color: "#6366f1" }}>{data.summary.total_fvgs}</div>
              <div style={{ fontSize: "0.6rem", color: "var(--text-muted)" }}>{data.summary.fresh_fvgs} fresh</div>
            </div>
            <div style={{ padding: "14px 16px", borderRadius: 12, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", textAlign: "center" }}>
              <div style={{ fontSize: "0.55rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 6 }}>Inverted FVG</div>
              <div style={{ fontSize: "1.4rem", fontWeight: 900, color: "#a78bfa" }}>{data.summary.inverted_fvgs}</div>
              <div style={{ fontSize: "0.6rem", color: "#a78bfa" }}>IFVG active</div>
            </div>
            <div style={{ padding: "14px 16px", borderRadius: 12, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", textAlign: "center" }}>
              <div style={{ fontSize: "0.55rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 6 }}>Breakers</div>
              <div style={{ fontSize: "1.4rem", fontWeight: 900, color: "#f59e0b" }}>{data.summary.total_breakers}</div>
              <div style={{ fontSize: "0.6rem", color: "var(--text-muted)" }}>active blocks</div>
            </div>
            <div style={{ padding: "14px 16px", borderRadius: 12, background: `${biasColor[data.signals.entry_bias]}12`, border: `1px solid ${biasColor[data.signals.entry_bias]}30`, textAlign: "center" }}>
              <div style={{ fontSize: "0.55rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 6 }}>Entry Bias</div>
              <div style={{ fontSize: "1rem", fontWeight: 900, color: biasColor[data.signals.entry_bias] }}>{data.signals.entry_bias}</div>
              <div style={{ fontSize: "0.6rem", color: "var(--text-muted)" }}>{data.signals.fvg_signal.replace(/_/g, " ")}</div>
            </div>
            <div style={{ padding: "14px 16px", borderRadius: 12, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
              <div style={{ fontSize: "0.55rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Setup Grade</div>
              <QualityBadge grade={data.signals.setup_quality} />
            </div>
          </div>

          {/* Signals */}
          {data.signals.messages.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              {data.signals.messages.map((m, i) => (
                <div key={i} style={{ fontSize: "0.75rem", padding: "8px 14px", background: "rgba(255,255,255,0.02)", borderRadius: 8, border: "1px solid rgba(255,255,255,0.05)" }}>{m}</div>
              ))}
            </div>
          )}

          {/* Nearest quick-view */}
          {(data.nearest.bullish_fvg || data.nearest.bearish_fvg || data.nearest.breaker) && (
            <div style={{ padding: "14px 16px", borderRadius: 12, background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.2)" }}>
              <div style={{ fontWeight: 800, fontSize: "0.78rem", color: "#6366f1", marginBottom: 10 }}>⭐ Nearest Key Levels to Price</div>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                {data.nearest.bullish_fvg && (
                  <div style={{ padding: "8px 12px", borderRadius: 8, background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.2)" }}>
                    <div style={{ fontSize: "0.6rem", color: "#10b981", fontWeight: 700, marginBottom: 3 }}>🟢 Nearest Bullish FVG</div>
                    <div style={{ fontFamily: "monospace", fontSize: "0.75rem" }}>CE: {data.nearest.bullish_fvg.ce_level.toLocaleString("en", { maximumFractionDigits: 2 })}</div>
                    <div style={{ fontSize: "0.6rem", color: "var(--text-muted)" }}>{data.nearest.bullish_fvg.gap_low.toLocaleString("en", {maximumFractionDigits:2})} – {data.nearest.bullish_fvg.gap_high.toLocaleString("en", {maximumFractionDigits:2})}</div>
                  </div>
                )}
                {data.nearest.bearish_fvg && (
                  <div style={{ padding: "8px 12px", borderRadius: 8, background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)" }}>
                    <div style={{ fontSize: "0.6rem", color: "#ef4444", fontWeight: 700, marginBottom: 3 }}>🔴 Nearest Bearish FVG</div>
                    <div style={{ fontFamily: "monospace", fontSize: "0.75rem" }}>CE: {data.nearest.bearish_fvg.ce_level.toLocaleString("en", { maximumFractionDigits: 2 })}</div>
                    <div style={{ fontSize: "0.6rem", color: "var(--text-muted)" }}>{data.nearest.bearish_fvg.gap_low.toLocaleString("en", {maximumFractionDigits:2})} – {data.nearest.bearish_fvg.gap_high.toLocaleString("en", {maximumFractionDigits:2})}</div>
                  </div>
                )}
                {data.nearest.breaker && (
                  <div style={{ padding: "8px 12px", borderRadius: 8, background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.2)" }}>
                    <div style={{ fontSize: "0.6rem", color: "#f59e0b", fontWeight: 700, marginBottom: 3 }}>🧱 Nearest Breaker</div>
                    <div style={{ fontFamily: "monospace", fontSize: "0.75rem" }}>{data.nearest.breaker.midpoint.toLocaleString("en", { maximumFractionDigits: 2 })}</div>
                    <div style={{ fontSize: "0.6rem", color: "var(--text-muted)" }}>{data.nearest.breaker.type.replace("_", " ")}</div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Tab switcher: FVG / Breakers */}
          <div style={{ display: "flex", gap: 4, padding: 5, borderRadius: 10, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)", width: "fit-content" }}>
            {([["fvg", "⬜ Fair Value Gaps", "#6366f1"], ["breaker", "🧱 Breaker Blocks", "#f59e0b"]] as const).map(([v, label, c]) => (
              <button key={v} onClick={() => setView(v as "fvg" | "breaker")} style={{
                padding: "7px 16px", borderRadius: 7, fontWeight: 700, fontSize: "0.78rem", cursor: "pointer",
                background: view === v ? `${c}15` : "transparent",
                border: `1px solid ${view === v ? `${c}40` : "transparent"}`,
                color: view === v ? c : "var(--text-muted)",
              }}>{label} <span style={{ fontSize: "0.65rem", opacity: 0.7 }}>({v === "fvg" ? fvgsToShow.length : breakersToShow.length})</span></button>
            ))}
          </div>

          {/* Lists */}
          {view === "fvg" && (
            <div>
              {fvgsToShow.length === 0 ? (
                <div style={{ textAlign: "center", padding: "30px 0", color: "var(--text-muted)", fontSize: "0.8rem" }}>No active FVGs found</div>
              ) : fvgsToShow.map(f => (
                <FVGRow key={`${f.type}-${f.id}`} fvg={f} price={data.current_price} />
              ))}
            </div>
          )}

          {view === "breaker" && (
            <div>
              {breakersToShow.length === 0 ? (
                <div style={{ textAlign: "center", padding: "30px 0", color: "var(--text-muted)", fontSize: "0.8rem" }}>No breaker blocks detected</div>
              ) : breakersToShow.map(b => (
                <BreakerRow key={`${b.type}-${b.id}`} bb={b} price={data.current_price} />
              ))}
            </div>
          )}

        </div>
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
