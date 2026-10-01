"use client";

import { useState, useCallback } from "react";
import { API_URL } from "@/lib/utils";

interface ScoredOB {
  type: string;
  high: number;
  low: number;
  index: number;
  score: number;
  grade: string;
  grade_color: string;
  is_fresh: boolean;
  touch_count: number;
  has_internal_fvg: boolean;
  displacement_atr: number;
  is_tradeable: boolean;
  reason: string;
  breakdown: {
    displacement: number;
    volume: number;
    touch_penalty: number;
    internal_fvg: number;
    htf_confluence: number;
    freshness: number;
  };
}

interface OBStrengthData {
  symbol: string;
  timeframe: string;
  total_obs: number;
  a_plus_count: number;
  order_blocks: ScoredOB[];
  best_ob: ScoredOB | null;
}

const GRADE_COLORS: Record<string, string> = {
  "A+": "#f59e0b",
  "A":  "#10b981",
  "B":  "#3b82f6",
  "C":  "#94a3b8",
  "D":  "#ef4444",
};

function ScoreBar({ value, max = 30, color }: { value: number; max?: number; color: string }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{ flex: 1, height: 4, borderRadius: 99, background: "rgba(255,255,255,0.05)", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 99, transition: "width 0.6s" }} />
      </div>
      <span style={{ fontSize: "0.6rem", color, fontWeight: 700, minWidth: 20, textAlign: "right" }}>{value}</span>
    </div>
  );
}

export function OBStrengthPanel() {
  const [data, setData]       = useState<OBStrengthData | null>(null);
  const [loading, setLoading] = useState(false);
  const [sym, setSym]         = useState("BTCUSDT");
  const [tf, setTf]           = useState("1h");
  const [htf, setHtf]         = useState("4h");
  const [selected, setSelected] = useState<ScoredOB | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const res = await window.fetch(`${API_URL}/api/v1/pro/ob-strength`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: sym, timeframe: tf, htf }),
      });
      const json = await res.json();
      if (!json.error) {
        setData(json);
        setSelected(json.best_ob ?? null);
      }
    } catch { /* ignore */ } finally { setLoading(false); }
  }, [sym, tf, htf]);

  return (
    <div style={{ padding: 24, borderRadius: 16, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 4, height: 20, borderRadius: 99, background: "linear-gradient(180deg,#f59e0b,#3b82f6)" }} />
          <div>
            <div style={{ fontWeight: 800, fontSize: "0.95rem" }}>Order Block Strength Meter</div>
            <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>Displacement · Volume · Freshness · IFVG · HTF Confluence</div>
          </div>
        </div>

        <div style={{ display: "flex", gap: 8 }}>
          <input value={sym} onChange={e => setSym(e.target.value.toUpperCase())}
            style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: "6px 10px", color: "#fff", fontSize: "0.78rem", width: 110, fontFamily: "monospace" }} />
          <select value={tf} onChange={e => setTf(e.target.value)}
            style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: "6px 10px", color: "#fff", fontSize: "0.78rem" }}>
            {["15m","1h","4h","1d"].map(t => <option key={t}>{t}</option>)}
          </select>
          <select value={htf} onChange={e => setHtf(e.target.value)}
            style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: "6px 10px", color: "#fff", fontSize: "0.78rem" }}>
            {["4h","1d","1w"].map(t => <option key={t}>{t}</option>)}
          </select>
          <button onClick={fetch} disabled={loading} style={{
            padding: "6px 16px", borderRadius: 8, background: "rgba(245,158,11,0.15)",
            border: "1px solid rgba(245,158,11,0.3)", color: "#f59e0b", fontWeight: 800,
            fontSize: "0.75rem", cursor: "pointer",
          }}>
            {loading ? "⟳" : "Score OBs"}
          </button>
        </div>
      </div>

      {!data ? (
        <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-muted)", fontSize: "0.82rem" }}>
          <div style={{ fontSize: "2.5rem", marginBottom: 10, opacity: 0.4 }}>🧱</div>
          Select symbol and click Score OBs
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {/* OB List */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
              <span style={{ fontSize: "0.65rem", color: "var(--text-muted)", fontWeight: 700 }}>ORDER BLOCKS ({data.total_obs})</span>
              <span style={{ fontSize: "0.65rem", color: "#f59e0b", fontWeight: 700 }}>A+ Count: {data.a_plus_count}</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 380, overflowY: "auto" }}>
              {data.order_blocks.map((ob, i) => (
                <div key={i}
                  onClick={() => setSelected(ob)}
                  style={{
                    padding: "12px 14px", borderRadius: 10, cursor: "pointer",
                    background: selected === ob ? `${ob.grade_color}10` : "rgba(255,255,255,0.02)",
                    border: `1px solid ${selected === ob ? ob.grade_color + "40" : "rgba(255,255,255,0.06)"}`,
                    transition: "all 0.2s",
                    opacity: ob.is_tradeable ? 1 : 0.5,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ fontSize: "0.65rem", fontWeight: 700, color: ob.type === "BULLISH" ? "#10b981" : "#ef4444" }}>
                        {ob.type === "BULLISH" ? "▲" : "▼"} {ob.type}
                      </span>
                      {ob.is_fresh && <span style={{ fontSize: "0.55rem", color: "#10b981", background: "rgba(16,185,129,0.1)", padding: "1px 5px", borderRadius: 4, fontWeight: 700 }}>FRESH</span>}
                      {ob.has_internal_fvg && <span style={{ fontSize: "0.55rem", color: "#a78bfa", background: "rgba(167,139,250,0.1)", padding: "1px 5px", borderRadius: 4, fontWeight: 700 }}>IFVG</span>}
                    </div>
                    <span style={{
                      padding: "3px 8px", borderRadius: 6, fontSize: "0.65rem", fontWeight: 800,
                      background: `${ob.grade_color}15`, color: ob.grade_color,
                    }}>{ob.grade}</span>
                  </div>
                  <div style={{ fontSize: "0.7rem", color: "#fff", fontFamily: "monospace" }}>
                    {ob.low.toLocaleString("en", { maximumFractionDigits: 4 })} — {ob.high.toLocaleString("en", { maximumFractionDigits: 4 })}
                  </div>
                  <div style={{ marginTop: 6, height: 4, borderRadius: 99, background: "rgba(255,255,255,0.05)", overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${ob.score}%`, background: `linear-gradient(90deg, ${ob.grade_color}80, ${ob.grade_color})`, borderRadius: 99 }} />
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: 2 }}>
                    <span style={{ fontSize: "0.55rem", color: "var(--text-muted)" }}>{ob.touch_count} touches</span>
                    <span style={{ fontSize: "0.55rem", color: ob.grade_color, fontWeight: 700 }}>{ob.score}/100</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Detail Panel */}
          {selected && (
            <div style={{ padding: 16, borderRadius: 12, background: "rgba(255,255,255,0.02)", border: `1px solid ${selected.grade_color}30` }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                <div style={{ fontWeight: 800, fontSize: "0.9rem" }}>Score Breakdown</div>
                <div style={{
                  padding: "6px 14px", borderRadius: 8,
                  background: `${selected.grade_color}15`, color: selected.grade_color,
                  fontSize: "0.85rem", fontWeight: 900, border: `1px solid ${selected.grade_color}30`,
                }}>
                  {selected.grade} — {selected.score}/100
                </div>
              </div>

              {/* Breakdown bars */}
              <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 16 }}>
                {[
                  { label: "Displacement",   value: selected.breakdown.displacement,  max: 30, color: "#3b82f6" },
                  { label: "Volume",         value: selected.breakdown.volume,        max: 20, color: "#10b981" },
                  { label: "Internal FVG",   value: selected.breakdown.internal_fvg,  max: 25, color: "#a78bfa" },
                  { label: "HTF Confluence", value: selected.breakdown.htf_confluence,max: 15, color: "#f59e0b" },
                  { label: "Freshness",      value: selected.breakdown.freshness,     max: 10, color: "#06b6d4" },
                  { label: "Touch Penalty",  value: selected.breakdown.touch_penalty, max: 0,  color: "#ef4444" },
                ].map(b => (
                  <div key={b.label}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                      <span style={{ fontSize: "0.62rem", color: "var(--text-muted)" }}>{b.label}</span>
                    </div>
                    <ScoreBar value={b.value < 0 ? 0 : b.value} max={b.max || 45} color={b.color} />
                    {b.value < 0 && <div style={{ fontSize: "0.6rem", color: "#ef4444", marginTop: 1 }}>Penalty: {b.value} pts</div>}
                  </div>
                ))}
              </div>

              {/* Info tags */}
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 12 }}>
                {selected.is_fresh && <span style={{ fontSize: "0.62rem", color: "#10b981", background: "rgba(16,185,129,0.1)", padding: "3px 8px", borderRadius: 6, border: "1px solid rgba(16,185,129,0.2)" }}>✓ Fresh OB</span>}
                {selected.has_internal_fvg && <span style={{ fontSize: "0.62rem", color: "#a78bfa", background: "rgba(167,139,250,0.1)", padding: "3px 8px", borderRadius: 6, border: "1px solid rgba(167,139,250,0.2)" }}>★ Internal FVG</span>}
                {!selected.is_tradeable && <span style={{ fontSize: "0.62rem", color: "#ef4444", background: "rgba(239,68,68,0.1)", padding: "3px 8px", borderRadius: 6 }}>⚠️ Low quality</span>}
              </div>

              {selected.reason && (
                <div style={{ padding: "8px 12px", borderRadius: 8, background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.15)", fontSize: "0.7rem", color: "#f59e0b" }}>
                  ⚠️ {selected.reason}
                </div>
              )}

              <div style={{ marginTop: 12, fontSize: "0.65rem", color: "var(--text-muted)" }}>
                Displacement: <span style={{ color: "#3b82f6" }}>{selected.displacement_atr}x ATR</span>
                {" · "}Touches: <span style={{ color: selected.touch_count > 2 ? "#ef4444" : "#fff" }}>{selected.touch_count}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
