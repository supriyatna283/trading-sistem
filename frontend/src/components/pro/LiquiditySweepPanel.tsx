"use client";

import { useState, useCallback, useEffect } from "react";
import { API_URL } from "@/lib/utils";

interface SweepPool {
  price: number;
  type: string;
  strength: number;
  swept: boolean;
}

interface SweepEvent {
  pool_price: number;
  pool_type: string;
  pool_strength: number;
  sweep_type: string;
  direction_after: string;
  has_displacement: boolean;
  displacement_strength: number;
  is_confirmed: boolean;
  quality_score: number;
  signal_grade: string;
  entry_zone_low: number;
  entry_zone_high: number;
  invalidation: number;
  sweep_time: string | null;
}

interface SweepData {
  symbol: string;
  timeframe: string;
  pools: SweepPool[];
  sweeps: SweepEvent[];
  latest_sweep: SweepEvent | null;
  bias_from_sweep: string | null;
  score: number;
  confirmed_count: number;
}

const GRADE_COLORS: Record<string, string> = {
  "A+":   "#f59e0b",
  "VALID": "#10b981",
  "WEAK":  "#64748b",
};

interface LiquiditySweepPanelProps {
  symbol?: string;
  timeframe?: string;
  autoLoad?: boolean;
}

export function LiquiditySweepPanel({
  symbol = "BTCUSDT",
  timeframe = "1h",
  autoLoad = false,
}: LiquiditySweepPanelProps) {
  const [data, setData]     = useState<SweepData | null>(null);
  const [loading, setLoading] = useState(false);
  const [sym, setSym]       = useState(symbol);
  const [tf, setTf]         = useState(timeframe);

  const fetch = useCallback(async (s?: string, t?: string) => {
    setLoading(true);
    try {
      const res = await window.fetch(`${API_URL}/api/v1/pro/liquidity-sweep`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: (s || sym).toUpperCase(), timeframe: t || tf, lookback: 100 }),
      });
      const json = await res.json();
      if (!json.error) setData(json);
    } catch { /* ignore */ } finally { setLoading(false); }
  }, [sym, tf]);

  // Sync props → local state + auto-fetch when props change
  useEffect(() => {
    setSym(symbol);
    setTf(timeframe);
    if (autoLoad) fetch(symbol, timeframe);
  }, [symbol, timeframe, autoLoad]);

  useEffect(() => { if (autoLoad) fetch(); }, []);  // initial load


  const latest = data?.latest_sweep;
  const biasColor = data?.bias_from_sweep === "BUY" ? "#10b981" : data?.bias_from_sweep === "SELL" ? "#ef4444" : "#64748b";

  return (
    <div style={{ padding: 24, borderRadius: 16, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 4, height: 20, borderRadius: 99, background: "linear-gradient(180deg,#ef4444,#f59e0b)" }} />
          <div>
            <div style={{ fontWeight: 800, fontSize: "0.95rem" }}>Liquidity Sweep Detector</div>
            <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>Equal Highs/Lows → Sweep → Displacement → Entry</div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            value={sym} onChange={e => setSym(e.target.value.toUpperCase())}
            style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: "6px 10px", color: "#fff", fontSize: "0.78rem", width: 110, fontFamily: "monospace" }}
            placeholder="BTCUSDT"
          />
          <select value={tf} onChange={e => setTf(e.target.value)}
            style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: "6px 10px", color: "#fff", fontSize: "0.78rem" }}>
            {["5m","15m","1h","4h","1d"].map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <button onClick={() => fetch()} disabled={loading} style={{
            padding: "6px 16px", borderRadius: 8, background: "rgba(239,68,68,0.15)",
            border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444", fontWeight: 800,
            fontSize: "0.75rem", cursor: "pointer",
          }}>
            {loading ? "⟳" : "Scan"}
          </button>
        </div>
      </div>

      {!data ? (
        <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-muted)", fontSize: "0.82rem" }}>
          <div style={{ fontSize: "2.5rem", marginBottom: 10, opacity: 0.4 }}>🎯</div>
          Select a symbol and click Scan to detect liquidity sweeps
        </div>
      ) : (
        <div>
          {/* Summary row */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 20 }}>
            {[
              { label: "Liquidity Pools", value: data.pools.length, color: "#f59e0b" },
              { label: "Sweeps Found",    value: data.sweeps.length, color: "#ef4444" },
              { label: "Confirmed",       value: data.confirmed_count, color: "#10b981" },
              { label: "Confluence Score",value: `${data.score}/5`, color: "#3b82f6" },
            ].map(s => (
              <div key={s.label} style={{ padding: "12px", borderRadius: 10, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", textAlign: "center" }}>
                <div style={{ fontSize: "0.55rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4 }}>{s.label}</div>
                <div style={{ fontSize: "1.2rem", fontWeight: 800, color: s.color, fontFamily: "'JetBrains Mono', monospace" }}>{s.value}</div>
              </div>
            ))}
          </div>

          {/* Bias from sweep */}
          {data.bias_from_sweep && (
            <div style={{
              padding: "12px 16px", borderRadius: 10, marginBottom: 16,
              background: `${biasColor}10`, border: `1px solid ${biasColor}30`,
              display: "flex", alignItems: "center", justifyContent: "space-between",
            }}>
              <div>
                <div style={{ fontSize: "0.6rem", color: "var(--text-muted)", marginBottom: 2 }}>DIRECTIONAL BIAS FROM SWEEP</div>
                <div style={{ fontSize: "1rem", fontWeight: 800, color: biasColor }}>
                  {data.bias_from_sweep === "BUY" ? "▲ BULLISH" : "▼ BEARISH"} — Market Maker direction
                </div>
              </div>
              <div style={{
                padding: "6px 14px", borderRadius: 8, background: `${biasColor}15`,
                fontSize: "0.75rem", fontWeight: 800, color: biasColor,
                border: `1px solid ${biasColor}30`,
              }}>
                LOOK {data.bias_from_sweep}
              </div>
            </div>
          )}

          {/* Latest sweep detail */}
          {latest && (
            <div style={{
              padding: 16, borderRadius: 12, marginBottom: 16,
              background: "rgba(255,255,255,0.02)", border: `1px solid ${GRADE_COLORS[latest.signal_grade] ?? "#64748b"}30`,
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <div style={{ fontWeight: 800, fontSize: "0.85rem" }}>Most Recent Sweep</div>
                <div style={{ display: "flex", gap: 6 }}>
                  <span style={{
                    padding: "4px 10px", borderRadius: 6, fontSize: "0.65rem", fontWeight: 800,
                    background: `${GRADE_COLORS[latest.signal_grade] ?? "#64748b"}20`,
                    color: GRADE_COLORS[latest.signal_grade] ?? "#64748b",
                    border: `1px solid ${GRADE_COLORS[latest.signal_grade] ?? "#64748b"}40`,
                  }}>
                    {latest.signal_grade}
                  </span>
                  {latest.is_confirmed && (
                    <span style={{ padding: "4px 10px", borderRadius: 6, fontSize: "0.65rem", fontWeight: 800, background: "rgba(16,185,129,0.15)", color: "#10b981", border: "1px solid rgba(16,185,129,0.3)" }}>
                      ✓ CONFIRMED
                    </span>
                  )}
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
                {[
                  { label: "Type",          value: latest.sweep_type.replace(/_/g, " ") },
                  { label: "Pool Price",    value: latest.pool_price.toLocaleString("en", { maximumFractionDigits: 4 }) },
                  { label: "Pool Strength", value: `${latest.pool_strength} touches` },
                  { label: "Entry Zone Low",  value: Math.min(latest.entry_zone_low, latest.entry_zone_high).toLocaleString("en", { maximumFractionDigits: latest.pool_price < 1 ? 6 : 4 }) },
                  { label: "Entry Zone High", value: Math.max(latest.entry_zone_low, latest.entry_zone_high).toLocaleString("en", { maximumFractionDigits: latest.pool_price < 1 ? 6 : 4 }) },
                  { label: "Invalidation",  value: latest.invalidation.toLocaleString("en", { maximumFractionDigits: 4 }) },
                  { label: "Displacement",  value: latest.has_displacement ? `${latest.displacement_strength}x ATR ✓` : "Not confirmed" },
                  { label: "Quality Score", value: `${latest.quality_score}/100` },
                  { label: "Direction",     value: latest.direction_after },
                ].map(f => (
                  <div key={f.label} style={{ background: "var(--bg-secondary)", borderRadius: 8, padding: "8px 10px" }}>
                    <div style={{ fontSize: "0.55rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 2 }}>{f.label}</div>
                    <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "#fff", fontFamily: "monospace" }}>{f.value}</div>
                  </div>
                ))}
              </div>

              {/* Score bar */}
              <div style={{ marginTop: 12 }}>
                <div style={{ fontSize: "0.6rem", color: "var(--text-muted)", marginBottom: 4 }}>Quality Score</div>
                <div style={{ height: 6, borderRadius: 99, background: "rgba(255,255,255,0.05)", overflow: "hidden" }}>
                  <div style={{
                    height: "100%", borderRadius: 99, transition: "width 0.8s",
                    width: `${latest.quality_score}%`,
                    background: `linear-gradient(90deg, ${GRADE_COLORS[latest.signal_grade] ?? "#64748b"}80, ${GRADE_COLORS[latest.signal_grade] ?? "#64748b"})`,
                  }} />
                </div>
              </div>
            </div>
          )}

          {/* Pools list */}
          {data.pools.length > 0 && (
            <div>
              <div style={{ fontSize: "0.65rem", fontWeight: 700, color: "var(--text-muted)", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.1em" }}>
                Liquidity Pools ({data.pools.length})
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {data.pools.slice(0, 6).map((pool, i) => (
                  <div key={i} style={{
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                    padding: "8px 12px", borderRadius: 8,
                    background: pool.swept ? "rgba(239,68,68,0.05)" : "rgba(255,255,255,0.02)",
                    border: `1px solid ${pool.swept ? "rgba(239,68,68,0.2)" : "rgba(255,255,255,0.05)"}`,
                    opacity: pool.swept ? 0.6 : 1,
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: "0.7rem", color: pool.type === "EQUAL_HIGH" ? "#ef4444" : "#10b981", fontWeight: 700 }}>
                        {pool.type === "EQUAL_HIGH" ? "▲ EQH" : "▼ EQL"}
                      </span>
                      <span style={{ fontSize: "0.75rem", fontFamily: "monospace", color: "#fff" }}>
                        {pool.price.toLocaleString("en", { maximumFractionDigits: 4 })}
                      </span>
                    </div>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <span style={{ fontSize: "0.62rem", color: "var(--text-muted)" }}>{pool.strength} touches</span>
                      {pool.swept && <span style={{ fontSize: "0.62rem", color: "#ef4444", fontWeight: 700 }}>SWEPT</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
