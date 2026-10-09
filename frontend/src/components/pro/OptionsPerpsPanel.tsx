"use client";

import { useState, useEffect } from "react";
import { API_URL } from "@/lib/utils";

interface OptionsPerpsData {
  symbol: string;
  spot_price: number;
  iv_30d: number;
  funding_rate_8h: number;
  funding_sentiment: string;
  oi_trend: string;
  long_short_ratio: number;
  ls_signal: string;
  basis_pct: number;
  options_bias: string;
}

export function OptionsPerpsPanel({ symbol, autoLoad = true }: { symbol: string; autoLoad?: boolean }) {
  const [data, setData] = useState<OptionsPerpsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchData = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/api/v1/pro/options-perps`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (e: any) {
      setError(e.message || "Failed to fetch Options/Perps data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (autoLoad && symbol) {
      fetchData();
    }
  }, [symbol, autoLoad]);

  if (loading) {
    return <div style={{ padding: 20, color: "var(--text-muted)", fontSize: "0.8rem" }}>⏳ Loading Funding Rate & OI...</div>;
  }

  if (error) {
    return <div style={{ padding: 20, color: "#ef4444", fontSize: "0.8rem" }}>⚠️ {error}</div>;
  }

  if (!data) return null;

  return (
    <div style={{ padding: 24, borderRadius: 16, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
            <span style={{ fontSize: "1.2rem" }}>📈</span>
            <span style={{ fontWeight: 800, fontSize: "1rem", color: "#fff" }}>Funding Rate & OI</span>
            <span style={{ fontSize: "0.65rem", padding: "2px 6px", borderRadius: 4, background: "rgba(99,102,241,0.1)", color: "#818cf8", border: "1px solid rgba(99,102,241,0.3)" }}>Crypto Edge</span>
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Perpetual Futures Market Context</div>
        </div>
        <button onClick={fetchData} style={{ background: "transparent", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "1rem" }}>
          🔄
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
        {/* Funding Rate */}
        <div style={{ padding: 16, borderRadius: 12, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.05)" }}>
          <div style={{ fontSize: "0.65rem", textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 6, fontWeight: 700 }}>8h Funding Rate</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: "1.1rem", fontWeight: 800, color: data.funding_rate_8h > 0 ? "#10b981" : "#ef4444", fontFamily: "'JetBrains Mono', monospace" }}>
              {data.funding_rate_8h.toFixed(4)}%
            </span>
            <span style={{ fontSize: "0.6rem", padding: "2px 6px", borderRadius: 4, background: "rgba(255,255,255,0.05)", color: "#fff" }}>
              {data.funding_sentiment}
            </span>
          </div>
          <div style={{ marginTop: 8, fontSize: "0.6rem", color: "var(--text-muted)" }}>
            {data.funding_rate_8h > 0 ? "Longs pay shorts. Market is bullish/greedy." : "Shorts pay longs. Market is bearish/fearful."}
          </div>
        </div>

        {/* Long/Short Ratio */}
        <div style={{ padding: 16, borderRadius: 12, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.05)" }}>
          <div style={{ fontSize: "0.65rem", textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 6, fontWeight: 700 }}>Long/Short Ratio</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: "1.1rem", fontWeight: 800, color: data.long_short_ratio > 1 ? "#ef4444" : "#10b981", fontFamily: "'JetBrains Mono', monospace" }}>
              {data.long_short_ratio.toFixed(2)}
            </span>
            <span style={{ fontSize: "0.6rem", padding: "2px 6px", borderRadius: 4, background: "rgba(255,255,255,0.05)", color: "#fff" }}>
              {data.ls_signal}
            </span>
          </div>
          <div style={{ marginTop: 8, fontSize: "0.6rem", color: "var(--text-muted)" }}>
            {data.long_short_ratio > 1 ? "Retail is overwhelmingly long." : "Retail is predominantly short."}
          </div>
        </div>

        {/* Open Interest & IV */}
        <div style={{ padding: 16, borderRadius: 12, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.05)" }}>
          <div style={{ fontSize: "0.65rem", textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 6, fontWeight: 700 }}>OI & Volatility</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.75rem", color: "#cbd5e1" }}>OI Trend</span>
              <span style={{ fontSize: "0.75rem", fontWeight: 800, color: data.oi_trend === "RISING" ? "#10b981" : data.oi_trend === "FALLING" ? "#ef4444" : "#f59e0b" }}>
                {data.oi_trend}
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.75rem", color: "#cbd5e1" }}>Implied Vol (30d)</span>
              <span style={{ fontSize: "0.75rem", fontWeight: 800, color: "#fff", fontFamily: "'JetBrains Mono', monospace" }}>
                {(data.iv_30d * 100).toFixed(1)}%
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.75rem", color: "#cbd5e1" }}>Basis (Premium)</span>
              <span style={{ fontSize: "0.75rem", fontWeight: 800, color: data.basis_pct > 0 ? "#10b981" : "#ef4444", fontFamily: "'JetBrains Mono', monospace" }}>
                {data.basis_pct.toFixed(3)}%
              </span>
            </div>
          </div>
        </div>
      </div>
      
      <div style={{ marginTop: 16, padding: "10px 14px", borderRadius: 8, background: "rgba(245,158,11,0.05)", border: "1px solid rgba(245,158,11,0.2)", fontSize: "0.7rem", color: "#f59e0b", display: "flex", alignItems: "center", gap: 8 }}>
        <span>💡</span>
        <span>Contrarian Edge: Smart money hunts liquidity when Retail Long/Short Ratio is extremely high and Funding Rate is heavily skewed.</span>
      </div>
    </div>
  );
}
