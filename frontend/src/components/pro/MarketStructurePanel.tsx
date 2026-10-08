"use client";

import { useState, useEffect, useCallback } from "react";
import { API_URL } from "@/lib/utils";

interface MarketStructureData {
  symbol: string;
  timeframe: string;
  bias: "BULLISH" | "BEARISH" | "SIDEWAYS";
  swing_points: Array<{ index: number; price: number; type: "HIGH" | "LOW"; time: string | null }>;
  structure_labels: Array<{ index: number; label: "HH" | "HL" | "LH" | "LL"; is_break: boolean; break_type: "BOS" | "CHOCH" | null }>;
}

export function MarketStructurePanel({ symbol, timeframe }: { symbol: string; timeframe: string }) {
  const [data, setData] = useState<MarketStructureData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/api/v1/pro/market-structure`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, timeframe, lookback: 200, swing_lookback: 5 }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return (
      <div style={{ padding: 20, borderRadius: 16, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
        <div className="skeleton" style={{ height: 20, width: 150, marginBottom: 12 }} />
        <div className="skeleton" style={{ height: 60, width: "100%" }} />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{ padding: 20, borderRadius: 16, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
        <div style={{ color: "#ef4444", fontSize: "0.8rem" }}>Failed to load market structure: {error}</div>
      </div>
    );
  }

  const biasColor = data.bias === "BULLISH" ? "#10b981" : data.bias === "BEARISH" ? "#ef4444" : "#f59e0b";
  const recentBreaks = data.structure_labels.filter(l => l.is_break).reverse().slice(0, 3);
  const latestSwings = [...data.swing_points].reverse().slice(0, 4);

  return (
    <div style={{ padding: 20, borderRadius: 16, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: "1.2rem" }}>📈</span>
            <span style={{ fontWeight: 800, fontSize: "0.9rem" }}>Market Structure</span>
          </div>
          <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", marginTop: 2 }}>
            Detects Swing Points, BOS, and CHoCH on {symbol} {timeframe}
          </div>
        </div>
        
        <div style={{ padding: "6px 12px", borderRadius: 8, background: `${biasColor}15`, border: `1px solid ${biasColor}40`, color: biasColor, fontSize: "0.75rem", fontWeight: 800, display: "flex", alignItems: "center", gap: 6 }}>
          <div style={{ width: 6, height: 6, borderRadius: "50%", background: biasColor, boxShadow: `0 0 6px ${biasColor}` }} className="animate-pulse-dot" />
          {data.bias} BIAS
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Recent Swings */}
        <div style={{ background: "rgba(255,255,255,0.02)", borderRadius: 12, padding: 12, border: "1px solid rgba(255,255,255,0.05)" }}>
          <div style={{ fontSize: "0.65rem", fontWeight: 700, color: "var(--text-muted)", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>Recent Swing Points</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {latestSwings.map((s, i) => {
              const label = data.structure_labels.find(l => l.index === s.index)?.label || s.type;
              const isHigh = s.type === "HIGH";
              return (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 10px", borderRadius: 6, background: "rgba(255,255,255,0.03)" }}>
                  <span style={{ fontSize: "0.7rem", fontWeight: 800, color: isHigh ? "#10b981" : "#ef4444" }}>
                    {label}
                  </span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.7rem", color: "#e2e8f0" }}>
                    {s.price.toLocaleString("en", { maximumFractionDigits: 5 })}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Structure Breaks */}
        <div style={{ background: "rgba(255,255,255,0.02)", borderRadius: 12, padding: 12, border: "1px solid rgba(255,255,255,0.05)" }}>
          <div style={{ fontSize: "0.65rem", fontWeight: 700, color: "var(--text-muted)", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>Recent Structure Breaks</div>
          {recentBreaks.length === 0 ? (
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", padding: "10px 0", textAlign: "center" }}>No recent breaks detected</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {recentBreaks.map((b, i) => {
                const isChoch = b.break_type === "CHOCH";
                const color = isChoch ? "#a78bfa" : "#3b82f6";
                return (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 10px", borderRadius: 6, background: `${color}10`, border: `1px solid ${color}30` }}>
                    <span style={{ padding: "2px 6px", borderRadius: 4, background: color, color: "#fff", fontSize: "0.55rem", fontWeight: 900 }}>
                      {b.break_type}
                    </span>
                    <span style={{ fontSize: "0.65rem", color: "#e2e8f0" }}>
                      Broken {b.label}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <div style={{ marginTop: 12, padding: "8px 12px", borderRadius: 8, background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.2)", fontSize: "0.65rem", color: "#a78bfa", lineHeight: 1.5 }}>
        💡 <strong>Rule:</strong> CHoCH (Change of Character) signals a trend reversal. BOS (Break of Structure) confirms trend continuation. Always trade in the direction of the latest BOS unless a valid CHoCH occurs.
      </div>
    </div>
  );
}
