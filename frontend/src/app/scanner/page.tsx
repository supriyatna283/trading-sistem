"use client";

import MainLayout from "@/components/layout/MainLayout";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";

function BiasTag({ bias }: { bias: string }) {
  if (!bias) return <span className="badge" style={{ fontSize: "0.65rem", padding: "2px 6px", color: "var(--text-muted)" }}>-</span>;
  
  const cls = bias === "BULLISH" ? "badge-bullish" : bias === "BEARISH" ? "badge-bearish" : "badge-sideways";
  const arrow = bias === "BULLISH" ? "▲" : bias === "BEARISH" ? "▼" : "◆";
  return <span className={`badge ${cls}`} style={{ fontSize: "0.65rem", padding: "2px 6px" }}>{arrow}</span>;
}

function RSITag({ val }: { val: number | null }) {
  if (val === null || val === undefined) return <span style={{ color: "var(--text-muted)" }}>-</span>;
  
  const color = val <= 30 ? "var(--accent-green)" : val >= 70 ? "var(--accent-red)" : "var(--text-secondary)";
  const fontWeight = (val <= 25 || val >= 75) ? 800 : 500;
  const bgColor = val <= 25 ? "rgba(34,197,94,0.1)" : val >= 75 ? "rgba(239,68,68,0.1)" : "transparent";
  
  return (
    <span style={{ 
      color, 
      fontWeight, 
      background: bgColor, 
      padding: "2px 6px", 
      borderRadius: 4,
      fontFamily: "JetBrains Mono, monospace",
      fontSize: "0.75rem"
    }}>
      {val.toFixed(1)}
    </span>
  );
}

function OBRatioTag({ ratio, bias }: { ratio: number; bias: string }) {
  const color = bias === "BULLISH" ? "var(--accent-green)" : bias === "BEARISH" ? "var(--accent-red)" : "var(--text-muted)";
  return (
    <span style={{ color, fontWeight: 600, fontFamily: "JetBrains Mono, monospace", fontSize: "0.75rem" }}>
      {ratio.toFixed(2)}x
    </span>
  );
}

function MCAPTierTag({ tier }: { tier: string }) {
  const colors: Record<string, string> = {
    LARGE: "var(--accent-green)",
    MID: "var(--accent-blue)",
    SMALL: "var(--accent-yellow)",
    MICRO: "var(--accent-red)",
    UNKNOWN: "var(--text-muted)",
  };
  return (
    <span style={{
      color: colors[tier] || "var(--text-muted)",
      fontWeight: 600,
      fontSize: "0.7rem",
      background: (colors[tier] || "var(--text-muted)").replace(")", ",0.1)").replace("var(", ""),
      padding: "2px 6px",
      borderRadius: 4,
    }}>
      {tier || "-"}
    </span>
  );
}

function PriceTag({ price, label }: { price: number; label: string }) {
  if (!price || price <= 0) return <span style={{ color: "var(--text-muted)", fontSize: "0.7rem" }}>-</span>;
  const formatted = price > 10 ? price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : price.toFixed(4);
  return (
    <span style={{ fontSize: "0.7rem", fontFamily: "JetBrains Mono, monospace", color: label === "S" ? "var(--accent-green)" : "var(--accent-red)" }}>
      {label}:{formatted}
    </span>
  );
}

export default function ScannerPage() {
  const [filter, setFilter] = useState("ALL");
  const [scannerData, setScannerData] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchScanner = async () => {
      try {
        const res = await api.getScanner();
        setScannerData(Array.isArray(res?.results) ? res.results : []);
      } catch (err) {
        console.error("Scanner fetch error:", err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchScanner();
  }, []);

  const handleRunScan = async () => {
    setIsLoading(true);
    try {
      await api.runScanner();
      const res = await api.getScanner();
      setScannerData(Array.isArray(res?.results) ? res.results : []);
    } catch (err) {
      console.error("Manual scan error:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const filtered = filter === "ALL" ? scannerData :
    filter === "SETUPS" ? scannerData.filter(r => (r.setup_status || "").includes("setup")) :
    filter === "ACTIONABLE" ? scannerData.filter(r => ["A+","VALID"].includes(r.signal_grade)) :
    filter === "WATCHLIST" ? scannerData.filter(r => r.signal_grade === "WEAK") :
    filter === "REJECTED" ? scannerData.filter(r => r.hard_rejected) :
    scannerData.filter(r => r.trend === filter);

  // Get BTC dominance from first result (shared across all)
  const btcDominance = scannerData.length > 0 ? scannerData[0].btc_dominance : 0;

  function TierBadge({ tier }: { tier: string }) {
    const cfg: Record<string, { color: string; bg: string }> = {
      "A+":       { color: "#f59e0b", bg: "rgba(245,158,11,0.15)" },
      "VALID":    { color: "#10b981", bg: "rgba(16,185,129,0.12)" },
      "WEAK":     { color: "#60a5fa", bg: "rgba(96,165,250,0.12)" },
      "NO_TRADE": { color: "#94a3b8", bg: "rgba(148,163,184,0.08)" },
    };
    const c = cfg[tier] || cfg.NO_TRADE;
    return (
      <span style={{
        display: "inline-flex", alignItems: "center", gap: 3,
        padding: "3px 8px", borderRadius: 6, fontSize: "0.62rem", fontWeight: 800,
        letterSpacing: "0.04em", color: c.color, background: c.bg,
        border: `1px solid ${c.color}40`,
      }}>{tier || "NO_TRADE"}</span>
    );
  }

  return (
    <MainLayout>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 32 }}>
        <div>
          <h1 style={{ fontSize: "1.75rem", fontWeight: 900, letterSpacing: "-0.04em", margin: 0, background: "linear-gradient(135deg, #fff, #94a3b8)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>Market Scanner</h1>
          <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", margin: "8px 0 0" }}>
            V7 Professional — 6-Layer Multi-Point Analysis · Institutional SMC V3
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          {btcDominance > 0 && (
            <div style={{
              background: "rgba(234,179,8,0.08)",
              border: "1px solid rgba(234,179,8,0.2)",
              borderRadius: 10,
              padding: "8px 16px",
              fontSize: "0.8rem",
              fontWeight: 800,
              color: "#eab308",
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              BTC.D: {btcDominance.toFixed(1)}%
            </div>
          )}
          <button 
            className="btn-primary" 
            onClick={handleRunScan}
            disabled={isLoading}
            style={{ opacity: isLoading ? 0.7 : 1, padding: "10px 22px", fontWeight: 800 }}
          >
            {isLoading ? "🔄 Analyzing Markets..." : "⚡ Run Global Scan"}
          </button>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: "flex", gap: 10, marginBottom: 24 }}>
        {["ALL", "BULLISH", "BEARISH", "ACTIONABLE", "WATCHLIST", "SETUPS", "REJECTED"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            style={{
              background: filter === f ? "rgba(59,130,246,0.12)" : "transparent",
              border: filter === f ? "1px solid rgba(59,130,246,0.3)" : "1px solid var(--border)",
              color: filter === f ? "var(--accent-blue)" : "var(--text-muted)",
              padding: "8px 18px",
              borderRadius: 10,
              fontSize: "0.82rem",
              fontWeight: 700,
              cursor: "pointer",
              transition: "all 0.2s",
            }}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="glass-card" style={{ padding: 0, overflow: "hidden", border: "1px solid var(--border)" }}>
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Pair</th>
                <th>Price</th>
                <th>24h</th>
                <th>Trend</th>
                <th>RSI (1h)</th>
                <th>RSI (4h)</th>
                <th>OB Ratio</th>
                <th>S/R Levels</th>
                <th>MCap</th>
                <th>Signal</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => {
                const price = row.latest_price || 0;
                const change = row.price_change_24h || 0;
                const score = row.signal_score ?? 0;
                const scoreColor = score >= 80 ? "#f59e0b" : score >= 65 ? "#10b981" : score >= 50 ? "#3b82f6" : "#ef4444";

                return (
                  <tr key={row.symbol} style={{ opacity: row.hard_rejected ? 0.5 : 1, transition: "opacity 0.3s" }}>
                    <td style={{ fontWeight: 900, color: "#fff" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        {row.symbol}
                        {(row.setup_status || "").includes("setup") && <span style={{ color: "#f59e0b", fontSize: "0.9rem" }}>⚡</span>}
                      </div>
                    </td>
                    <td style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700 }}>
                      {price > 0 ? (
                        price > 10 ? price.toLocaleString("en-US", { minimumFractionDigits: 2 }) : price.toFixed(4)
                      ) : (
                        <span style={{ color: "var(--text-muted)" }}>...</span>
                      )}
                    </td>
                    <td style={{ color: change > 0 ? "#10b981" : change < 0 ? "#ef4444" : "var(--text-muted)", fontWeight: 800 }}>
                      {change > 0 ? "+" : ""}{change.toFixed(2)}%
                    </td>
                    <td>
                      <span className={`badge badge-${(row.trend || "sideways").toLowerCase()}`} style={{ fontWeight: 800 }}>{row.trend}</span>
                    </td>
                    <td><RSITag val={row.rsi_1h} /></td>
                    <td><RSITag val={row.rsi_4h} /></td>
                    <td><OBRatioTag ratio={row.orderbook_ratio || 1} bias={row.orderbook_bias || "NEUTRAL"} /></td>
                    <td>
                      <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                        <PriceTag price={row.nearest_support} label="S" />
                        <PriceTag price={row.nearest_resistance} label="R" />
                      </div>
                    </td>
                    <td><MCAPTierTag tier={row.market_cap_tier || "UNKNOWN"} /></td>
                    <td>
                      <TierBadge tier={row.signal_grade || "NO_TRADE"} />
                      {row.hard_rejected && (
                        <div style={{ fontSize: "0.55rem", color: "#ef4444", marginTop: 4, fontWeight: 700, maxWidth: 100, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          ⚠️ {(row.rejection_reasons || [])[0] || "REJECTED"}
                        </div>
                      )}
                    </td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <div style={{ width: 45, height: 6, borderRadius: 3, background: "rgba(255,255,255,0.05)", overflow: "hidden" }}>
                          <div style={{
                            width: `${score}%`, height: "100%", borderRadius: 3,
                            background: scoreColor, boxShadow: score >= 80 ? `0 0 8px ${scoreColor}40` : "none"
                          }} />
                        </div>
                        <span style={{ fontSize: "0.8rem", fontFamily: "'JetBrains Mono', monospace", color: scoreColor, fontWeight: 800 }}>{score}</span>
                      </div>
                    </td>
                  </tr>
                );
              })}
              
              {filtered.length === 0 && !isLoading && (
                <tr>
                  <td colSpan={11} style={{ textAlign: "center", padding: "64px", color: "var(--text-muted)" }}>
                    <div style={{ fontSize: "2rem", marginBottom: 12 }}>📡</div>
                    <div style={{ fontWeight: 800, color: "var(--text-primary)" }}>No scan results found.</div>
                    <div style={{ marginTop: 8, fontSize: "0.85rem" }}>Ensure the Engine is active and symbols are configured correctly.</div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </MainLayout>
  );
}
