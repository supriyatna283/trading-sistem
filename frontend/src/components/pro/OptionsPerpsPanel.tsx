"use client";

import { useState, useEffect } from "react";
import { API_URL } from "@/lib/utils";

interface OptionsPerpsData {
  symbol: string;
  perp_source?: string;
  spot_price: number;
  mark_price?: number | null;
  iv_30d_pct: number;
  put_call_ratio: number;
  max_pain: number;
  skew_pct: number;
  options_bias: string;
  signals?: string[];
  confluence_score?: number;
  funding_rate_8h: number | null;
  funding_annualized?: number | null;
  funding_sentiment: string;
  oi_trend: string;
  open_interest_usd?: number | null;
  open_interest_coins?: number | null;
  long_short_ratio: number | null;
  ls_signal: string;
  basis_pct: number | null;
  carry_signal?: string;
  data_disclaimer?: string | null;
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
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4, flexWrap: "wrap" }}>
            <span style={{ fontSize: "1.2rem" }}>📈</span>
            <span style={{ fontWeight: 800, fontSize: "1rem", color: "#fff" }}>Options & Perpetuals Edge — {data.symbol}</span>
            <span style={{ fontSize: "0.65rem", padding: "2px 6px", borderRadius: 4, background: "rgba(99,102,241,0.1)", color: "#818cf8", border: "1px solid rgba(99,102,241,0.3)" }}>
              {data.perp_source && data.perp_source !== "unavailable" ? `LIVE (${data.perp_source.toUpperCase()})` : "Crypto Edge"}
            </span>
            {data.options_bias && (
              <span style={{
                fontSize: "0.65rem", fontWeight: 800, padding: "2px 8px", borderRadius: 5,
                background: data.options_bias === "BULLISH" ? "rgba(16,185,129,0.15)" : data.options_bias === "BEARISH" ? "rgba(239,68,68,0.15)" : "rgba(100,116,139,0.15)",
                color: data.options_bias === "BULLISH" ? "#10b981" : data.options_bias === "BEARISH" ? "#ef4444" : "#94a3b8",
                border: `1px solid ${data.options_bias === "BULLISH" ? "rgba(16,185,129,0.35)" : data.options_bias === "BEARISH" ? "rgba(239,68,68,0.35)" : "rgba(100,116,139,0.3)"}`,
              }}>
                {data.options_bias} BIAS
              </span>
            )}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Live Perpetual Futures Positioning & Black-Scholes Options Structure</div>
        </div>
        <button onClick={fetchData} style={{ background: "transparent", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "1rem" }}>
          🔄
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 12 }}>
        {/* Funding Rate */}
        <div style={{ padding: 16, borderRadius: 12, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.05)" }}>
          <div style={{ fontSize: "0.65rem", textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 6, fontWeight: 700 }}>8h Funding Rate</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={{ fontSize: "1.1rem", fontWeight: 800, color: data.funding_rate_8h == null ? "#64748b" : data.funding_rate_8h > 0 ? "#10b981" : "#ef4444", fontFamily: "'JetBrains Mono', monospace" }}>
              {data.funding_rate_8h == null ? "N/A" : `${data.funding_rate_8h > 0 ? "+" : ""}${data.funding_rate_8h.toFixed(4)}%`}
            </span>
            <span style={{ fontSize: "0.6rem", padding: "2px 6px", borderRadius: 4, background: "rgba(255,255,255,0.05)", color: "#fff" }}>
              {data.funding_sentiment}
            </span>
          </div>
          {data.funding_annualized != null && (
            <div style={{ marginTop: 4, fontSize: "0.65rem", color: "#94a3b8", fontFamily: "'JetBrains Mono', monospace" }}>
              Annualized: <strong>{data.funding_annualized > 0 ? "+" : ""}{data.funding_annualized.toFixed(1)}% APR</strong>
            </div>
          )}
          <div style={{ marginTop: 6, fontSize: "0.6rem", color: "var(--text-muted)" }}>
            {data.funding_rate_8h == null ? "Menunggu koneksi live derivatives." : data.funding_rate_8h > 0 ? "Longs pay shorts (Bullish/Greedy positioning)." : "Shorts pay longs (Bearish/Fearful positioning)."}
          </div>
        </div>

        {/* Long/Short Ratio */}
        <div style={{ padding: 16, borderRadius: 12, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.05)" }}>
          <div style={{ fontSize: "0.65rem", textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 6, fontWeight: 700 }}>Long/Short Account Ratio</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={{ fontSize: "1.1rem", fontWeight: 800, color: data.long_short_ratio == null ? "#64748b" : data.long_short_ratio > 1.3 ? "#ef4444" : data.long_short_ratio < 0.77 ? "#10b981" : "#e2e8f0", fontFamily: "'JetBrains Mono', monospace" }}>
              {data.long_short_ratio == null ? "N/A" : data.long_short_ratio.toFixed(2)}
            </span>
            <span style={{ fontSize: "0.6rem", padding: "2px 6px", borderRadius: 4, background: "rgba(255,255,255,0.05)", color: "#fff" }}>
              {data.ls_signal}
            </span>
          </div>
          <div style={{ marginTop: 8, fontSize: "0.6rem", color: "var(--text-muted)" }}>
            {data.long_short_ratio == null ? "Data long/short tidak tersedia." : data.long_short_ratio > 1 ? "Retail lebih banyak di posisi Long (contrarian watch)." : "Retail lebih banyak di posisi Short (squeeze watch)."}
          </div>
        </div>

        {/* Open Interest & IV */}
        <div style={{ padding: 16, borderRadius: 12, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.05)" }}>
          <div style={{ fontSize: "0.65rem", textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 6, fontWeight: 700 }}>Open Interest & Basis</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.72rem", color: "#cbd5e1" }}>Open Interest</span>
              <span style={{ fontSize: "0.75rem", fontWeight: 800, color: "#fff", fontFamily: "'JetBrains Mono', monospace" }}>
                {data.open_interest_usd != null
                  ? (data.open_interest_usd >= 1e9 ? `$${(data.open_interest_usd / 1e9).toFixed(2)}B` : `$${(data.open_interest_usd / 1e6).toFixed(1)}M`)
                  : data.oi_trend}
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.72rem", color: "#cbd5e1" }}>Activity / OI Trend</span>
              <span style={{ fontSize: "0.72rem", fontWeight: 800, color: data.oi_trend === "RISING" ? "#10b981" : data.oi_trend === "FALLING" ? "#ef4444" : "#94a3b8" }}>
                {data.oi_trend}
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.72rem", color: "#cbd5e1" }}>Basis (Perp vs Spot)</span>
              <span style={{ fontSize: "0.75rem", fontWeight: 800, color: data.basis_pct == null ? "#64748b" : data.basis_pct > 0 ? "#10b981" : "#ef4444", fontFamily: "'JetBrains Mono', monospace" }}>
                {data.basis_pct == null ? "N/A" : `${data.basis_pct > 0 ? "+" : ""}${data.basis_pct.toFixed(3)}%`}
              </span>
            </div>
          </div>
        </div>

        {/* Options Structure (Max Pain, Put/Call, Skew, IV) */}
        <div style={{ padding: 16, borderRadius: 12, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.05)" }}>
          <div style={{ fontSize: "0.65rem", textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 6, fontWeight: 700 }}>Options Structure (30d)</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.72rem", color: "#cbd5e1" }}>Max Pain Strike</span>
              <span style={{ fontSize: "0.75rem", fontWeight: 800, color: "#f59e0b", fontFamily: "'JetBrains Mono', monospace" }}>
                ${data.max_pain?.toLocaleString("en", { maximumFractionDigits: data.spot_price < 1 ? 6 : 2 })}
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.72rem", color: "#cbd5e1" }}>Put/Call Ratio · Skew</span>
              <span style={{ fontSize: "0.72rem", fontWeight: 800, color: "#fff", fontFamily: "'JetBrains Mono', monospace" }}>
                {data.put_call_ratio?.toFixed(2)} · {data.skew_pct > 0 ? "+" : ""}{data.skew_pct?.toFixed(1)}%
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.72rem", color: "#cbd5e1" }}>Realized Vol (30d)</span>
              <span style={{ fontSize: "0.75rem", fontWeight: 800, color: "#818cf8", fontFamily: "'JetBrains Mono', monospace" }}>
                {data.iv_30d_pct != null ? `${data.iv_30d_pct.toFixed(1)}%` : "N/A"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {data.signals && data.signals.length > 0 && (
        <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 6 }}>
          {data.signals.map((sig, i) => (
            <div key={i} style={{ padding: "8px 12px", borderRadius: 8, background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.2)", fontSize: "0.7rem", color: "#e2e8f0" }}>
              {sig}
            </div>
          ))}
        </div>
      )}
      
      {data.data_disclaimer && (
        <div style={{ marginTop: 16, padding: "10px 14px", borderRadius: 8, background: "rgba(100,116,139,0.08)", border: "1px solid rgba(100,116,139,0.3)", fontSize: "0.68rem", color: "#94a3b8", lineHeight: 1.5 }}>
          ⚠️ {data.data_disclaimer}
        </div>
      )}
      <div style={{ marginTop: 16, padding: "10px 14px", borderRadius: 8, background: "rgba(245,158,11,0.05)", border: "1px solid rgba(245,158,11,0.2)", fontSize: "0.7rem", color: "#f59e0b", display: "flex", alignItems: "center", gap: 8 }}>
        <span>💡</span>
        <span>Contrarian Edge: Smart money hunts liquidity when Retail Long/Short Ratio is extremely high and Funding Rate is heavily skewed.</span>
      </div>
    </div>
  );
}
