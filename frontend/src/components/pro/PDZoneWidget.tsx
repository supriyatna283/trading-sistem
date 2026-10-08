"use client";

import { useState, useCallback, useEffect } from "react";
import { API_URL } from "@/lib/utils";

interface PDZoneData {
  zone: string;
  zone_pct: number;
  zone_color: string;
  signal: string;
  htf_bias: string;
  trade_allowed: boolean;
  is_in_ote: boolean;
  distance_to_ote_pct: number;
  levels: {
    range_high: number;
    range_low: number;
    equilibrium: number;
    premium_threshold: number;
    discount_threshold: number;
    ote_low: number;
    ote_high: number;
  };
  score: number;
}

const ZONE_LABELS: Record<string, { label: string; emoji: string }> = {
  PREMIUM:            { label: "PREMIUM — Sell Zone",    emoji: "🔴" },
  EQUILIBRIUM:        { label: "EQUILIBRIUM — Wait",     emoji: "🟡" },
  DISCOUNT:           { label: "DISCOUNT — Buy Zone",    emoji: "🟢" },
  UNKNOWN:            { label: "ANALYZING...",           emoji: "⏳" },
};

const SIGNAL_COLORS: Record<string, string> = {
  STRONG_BUY:        "#10b981",
  BUY:               "#34d399",
  NEUTRAL:           "#64748b",
  SELL:              "#f87171",
  STRONG_SELL:       "#ef4444",
  CAUTION_PREMIUM:   "#f59e0b",
  CAUTION_DISCOUNT:  "#f59e0b",
};

interface PDZoneWidgetProps {
  symbol?: string;
  currentPrice?: number;
  htf?: string;
  timeframe?: string;
}

export function PDZoneWidget({
  symbol = "BTCUSDT",
  currentPrice,
  htf = "1d",
  timeframe = "1h",
}: PDZoneWidgetProps) {
  const [data, setData]       = useState<PDZoneData | null>(null);
  const [loading, setLoading] = useState(false);

  const fetch = useCallback(async (sym: string) => {
    setLoading(true);
    try {
      const res = await window.fetch(`${API_URL}/api/v1/pro/pd-zones`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: sym, timeframe, htf }),
      });
      const json = await res.json();
      if (json.pd_zone) setData(json.pd_zone);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }, [timeframe, htf]);

  // Auto-fetch when symbol/timeframe changes
  useEffect(() => {
    if (symbol) fetch(symbol);
  }, [symbol, timeframe, htf, fetch]);

  if (loading) return (
    <div style={{ padding: 20, borderRadius: 16, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height: 14, marginBottom: 8, width: i % 2 === 0 ? "60%" : "80%" }} />
      ))}
    </div>
  );

  if (!data) return (
    <div style={{ padding: 20, borderRadius: 16, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", textAlign: "center", color: "var(--text-muted)", fontSize: "0.8rem" }}>
      <div style={{ fontSize: "1.5rem", marginBottom: 8 }}>📊</div>
      Click Analyze to load PD Zones
    </div>
  );

  const zoneInfo    = ZONE_LABELS[data.zone] ?? ZONE_LABELS.UNKNOWN;
  const signalColor = SIGNAL_COLORS[data.signal] ?? "#64748b";
  const levels      = data.levels;

  // PD Zone visualization: vertical bar
  const pricePct = Math.min(100, Math.max(0, data.zone_pct));

  return (
    <div style={{
      padding: 20, borderRadius: 16,
      background: "rgba(255,255,255,0.02)",
      border: `1px solid ${data.zone_color}30`,
      boxShadow: data.trade_allowed ? `0 0 20px ${data.zone_color}10` : "none",
    }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: "0.62rem", fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: 4 }}>
            P/D Array — {htf.toUpperCase()} Range
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: "1.1rem" }}>{zoneInfo.emoji}</span>
            <span style={{ fontWeight: 800, fontSize: "0.9rem", color: data.zone_color }}>
              {zoneInfo.label}
            </span>
          </div>
        </div>
        <div style={{
          padding: "6px 12px", borderRadius: 8, fontWeight: 800, fontSize: "0.7rem",
          background: `${signalColor}15`, color: signalColor,
          border: `1px solid ${signalColor}30`,
        }}>
          {data.signal.replace(/_/g, " ")}
        </div>
      </div>

      {/* Zone Position Visualizer */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ position: "relative", height: 140, borderRadius: 10, overflow: "hidden", border: "1px solid rgba(255,255,255,0.05)" }}>
          {/* Premium zone (top 38%) */}
          <div style={{
            position: "absolute", top: 0, left: 0, right: 0,
            height: "38%",
            background: "linear-gradient(180deg, rgba(239,68,68,0.15) 0%, rgba(239,68,68,0.05) 100%)",
            borderBottom: "1px dashed rgba(239,68,68,0.3)",
          }}>
            <span style={{ fontSize: "0.6rem", color: "#ef4444", padding: "4px 8px", fontWeight: 700, opacity: 0.8 }}>PREMIUM</span>
          </div>

          {/* Equilibrium band (middle 24%) */}
          <div style={{
            position: "absolute", top: "38%", left: 0, right: 0, height: "24%",
            background: "rgba(245,158,11,0.06)",
            borderBottom: "1px dashed rgba(245,158,11,0.3)",
          }}>
            <span style={{ fontSize: "0.6rem", color: "#f59e0b", padding: "4px 8px", fontWeight: 700, opacity: 0.7 }}>EQ</span>
          </div>

          {/* Discount zone (bottom 38%) */}
          <div style={{
            position: "absolute", bottom: 0, left: 0, right: 0, height: "38%",
            background: "linear-gradient(0deg, rgba(16,185,129,0.15) 0%, rgba(16,185,129,0.03) 100%)",
          }}>
            <span style={{ fontSize: "0.6rem", color: "#10b981", padding: "4px 8px", fontWeight: 700, opacity: 0.8, position: "absolute", bottom: 4, left: 0 }}>DISCOUNT</span>
          </div>

          {/* OTE Zone highlight */}
          {levels && (
            <div style={{
              position: "absolute",
              top: `${Math.min(90, 100 - ((levels.ote_high - levels.range_low) / (levels.range_high - levels.range_low)) * 100)}%`,
              bottom: `${Math.min(90, ((levels.ote_low - levels.range_low) / (levels.range_high - levels.range_low)) * 100)}%`,
              left: 0, right: 0,
              background: "rgba(139,92,246,0.15)",
              borderTop: "1px solid rgba(139,92,246,0.5)",
              borderBottom: "1px solid rgba(139,92,246,0.5)",
            }}>
              {data.is_in_ote && (
                <span style={{ fontSize: "0.55rem", color: "#a78bfa", padding: "2px 6px", fontWeight: 800 }}>★ OTE</span>
              )}
            </div>
          )}

          {/* Current price indicator */}
          <div style={{
            position: "absolute",
            top: `${100 - pricePct}%`,
            left: 0, right: 0,
            height: 2,
            background: data.zone_color,
            boxShadow: `0 0 8px ${data.zone_color}`,
            zIndex: 10,
          }}>
            <div style={{
              position: "absolute", right: 8, top: -9,
              background: data.zone_color, color: "#000",
              fontSize: "0.55rem", fontWeight: 800,
              padding: "2px 6px", borderRadius: 4,
            }}>
              {pricePct.toFixed(1)}%
            </div>
          </div>
        </div>

        {/* Labels: High / Low */}
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
          <span style={{ fontSize: "0.6rem", color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace" }}>
            L: {levels?.range_low?.toLocaleString("en", { maximumFractionDigits: 5 })}
          </span>
          <span style={{ fontSize: "0.6rem", color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace" }}>
            H: {levels?.range_high?.toLocaleString("en", { maximumFractionDigits: 5 })}
          </span>
        </div>
      </div>

      {/* Key Levels Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 14 }}>
        {[
          { label: "Equilibrium", value: levels?.equilibrium, color: "#f59e0b" },
          { label: "OTE Low",     value: levels?.ote_low,     color: "#a78bfa" },
          { label: "Premium Thr", value: levels?.premium_threshold,  color: "#ef4444" },
          { label: "Discount Thr",value: levels?.discount_threshold, color: "#10b981" },
        ].map((l) => (
          <div key={l.label} style={{ background: "rgba(255,255,255,0.02)", borderRadius: 8, padding: "8px 10px" }}>
            <div style={{ fontSize: "0.55rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 2 }}>{l.label}</div>
            <div style={{ fontSize: "0.72rem", fontWeight: 700, color: l.color, fontFamily: "'JetBrains Mono', monospace" }}>
              {l.value?.toLocaleString("en", { maximumFractionDigits: 5 })}
            </div>
          </div>
        ))}
      </div>

      {/* HTF Bias + OTE status */}
      <div style={{ display: "flex", gap: 8 }}>
        <div style={{
          flex: 1, padding: "8px 12px", borderRadius: 8, textAlign: "center",
          background: data.htf_bias === "BULLISH" ? "rgba(16,185,129,0.1)" : data.htf_bias === "BEARISH" ? "rgba(239,68,68,0.1)" : "rgba(255,255,255,0.03)",
          border: `1px solid ${data.htf_bias === "BULLISH" ? "rgba(16,185,129,0.3)" : data.htf_bias === "BEARISH" ? "rgba(239,68,68,0.3)" : "rgba(255,255,255,0.06)"}`,
        }}>
          <div style={{ fontSize: "0.55rem", color: "var(--text-muted)", marginBottom: 2 }}>HTF BIAS</div>
          <div style={{ fontSize: "0.72rem", fontWeight: 800, color: data.htf_bias === "BULLISH" ? "#10b981" : data.htf_bias === "BEARISH" ? "#ef4444" : "#64748b" }}>
            {data.htf_bias}
          </div>
        </div>
        <div style={{
          flex: 1, padding: "8px 12px", borderRadius: 8, textAlign: "center",
          background: data.is_in_ote ? "rgba(139,92,246,0.12)" : "rgba(255,255,255,0.03)",
          border: `1px solid ${data.is_in_ote ? "rgba(139,92,246,0.3)" : "rgba(255,255,255,0.06)"}`,
        }}>
          <div style={{ fontSize: "0.55rem", color: "var(--text-muted)", marginBottom: 2 }}>OTE STATUS</div>
          <div style={{ fontSize: "0.72rem", fontWeight: 800, color: data.is_in_ote ? "#a78bfa" : "#64748b" }}>
            {data.is_in_ote ? "★ IN OTE" : `${data.distance_to_ote_pct.toFixed(2)}% away`}
          </div>
        </div>
      </div>
    </div>
  );
}
