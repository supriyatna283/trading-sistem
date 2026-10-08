"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import { API_URL } from "@/lib/utils";
import { useRouter } from "next/navigation";

// Reuse the Scanner types
interface ScanResult {
  symbol: string;
  trend: string;
  latest_price: number;
  price_change_24h: number;
  setup_status: string;
  signal_score: number;
  signal_grade: "A+" | "VALID" | "WEAK" | "NO_TRADE";
  score_breakdown: { STR: number; PA: number; SMC: number; VOL: number; TIM: number; RR: number };
  mtf_confirmation: string;
  volume_delta?: number | null;
  setup: any | null;
}

interface KZData {
  current_session: string;
  is_killzone_active: boolean;
  is_high_volume_kz: boolean;
  trade_advice: string;
  current_kz: { color: string; name: string; desc: string } | null;
  time_to_next: string;
}

const SCORE_LABELS: Record<string, string> = {
  STR: "Strength", PA: "Price Action", SMC: "Smart Money",
  VOL: "Volume", TIM: "Timing", RR: "Risk:Reward",
};

export function ProScannerPanel({ defaultTf = "1h", onSetWAAlert }: { defaultTf?: string; onSetWAAlert?: (data: any) => void }) {
  const router = useRouter();
  const [data, setData] = useState<ScanResult[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isScanning, setIsScanning] = useState(false);
  const [entryTf, setEntryTf] = useState(defaultTf);
  const [trendFilter, setTrendFilter] = useState<"ALL" | "BULLISH" | "BEARISH">("ALL");
  const [gradeFilter, setGradeFilter] = useState<"ALL" | "A+" | "VALID">("ALL");
  const [kzData, setKzData] = useState<KZData | null>(null);

  const autoRefreshRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async (silent = false) => {
    if (!silent) setIsLoading(true);
    try {
      const res = await api.getScanner(entryTf);
      setData(Array.isArray(res?.results) ? res.results : []);
    } catch (err) {
      console.error("Scanner fetch error:", err);
    } finally {
      setIsLoading(false);
    }
  }, [entryTf]);

  const handleScan = useCallback(async () => {
    setIsScanning(true);
    try {
      const res = await api.runScanner([], entryTf);
      if (Array.isArray(res?.results)) {
        setData(res.results);
      }
    } catch (err: any) {
      if (err?.message?.includes("Rate limited") || err?.message?.includes("429")) {
        await fetchData(true);
      } else {
        console.error("Scan error:", err);
      }
    } finally {
      setIsScanning(false);
    }
  }, [fetchData, entryTf]);

  const fetchKZ = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/pro/killzones`);
      if (res.ok) setKzData(await res.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchData(); fetchKZ(); }, [fetchData, fetchKZ]);

  // Auto-refresh every minute for scanner, every 30s for killzone
  useEffect(() => {
    autoRefreshRef.current = setInterval(() => fetchData(true), 60000);
    const kzInterval = setInterval(fetchKZ, 30000);
    return () => {
      if (autoRefreshRef.current) clearInterval(autoRefreshRef.current);
      clearInterval(kzInterval);
    };
  }, [fetchData, fetchKZ]);

  // Multi-filter: grade + trend
  const filteredPairs = data.filter(r => {
    const gradeOk = gradeFilter === "ALL"
      ? (r.signal_grade === "A+" || r.signal_grade === "VALID" || r.setup !== null)
      : r.signal_grade === gradeFilter;
    const trendOk = trendFilter === "ALL" || r.trend === trendFilter;
    return gradeOk && trendOk;
  });
  const sortedPairs = [...filteredPairs].sort((a, b) => (b.signal_score || 0) - (a.signal_score || 0));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* ── Killzone Banner (Bug #7) ── */}
      {kzData && (
        <div style={{
          display: "flex", alignItems: "center", gap: 12, padding: "10px 18px",
          borderRadius: 12, flexWrap: "wrap",
          background: kzData.is_killzone_active ? `${kzData.current_kz?.color || "#f59e0b"}12` : "rgba(255,255,255,0.02)",
          border: `1px solid ${kzData.is_killzone_active ? (kzData.current_kz?.color || "#f59e0b") + "40" : "rgba(255,255,255,0.07)"}`,
          boxShadow: kzData.is_killzone_active ? `0 0 20px ${kzData.current_kz?.color || "#f59e0b"}15` : "none",
          transition: "all 0.4s",
        }}>
          {kzData.is_killzone_active && (
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: kzData.current_kz?.color || "#f59e0b", boxShadow: `0 0 8px ${kzData.current_kz?.color || "#f59e0b"}` }} className="animate-pulse-dot" />
          )}
          <div style={{ flex: 1 }}>
            <span style={{ fontWeight: 800, fontSize: "0.78rem", color: kzData.is_killzone_active ? (kzData.current_kz?.color || "#f59e0b") : "var(--text-muted)" }}>
              {kzData.is_killzone_active ? "🔥" : "⏰"} {kzData.trade_advice}
            </span>
            <span style={{ fontSize: "0.6rem", color: "var(--text-muted)", marginLeft: 10 }}>
              {kzData.current_session?.replace(/_/g, " ")} · Next KZ in {kzData.time_to_next}
            </span>
          </div>
          {kzData.is_high_volume_kz && (
            <span style={{ fontSize: "0.62rem", fontWeight: 800, padding: "3px 10px", borderRadius: 6, background: "rgba(16,185,129,0.15)", color: "#10b981", border: "1px solid rgba(16,185,129,0.3)" }}>
              ✅ BEST ENTRY WINDOW
            </span>
          )}
        </div>
      )}

      {/* ── Header & Controls ── */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", padding: "16px 20px", borderRadius: 16, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ fontSize: "1.2rem", fontWeight: 900, margin: 0, display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ color: "#e879f9" }}>📡 Live Market Scanner</span>
            <span style={{ fontSize: "0.65rem", background: "rgba(232,121,249,0.15)", color: "#e879f9", padding: "3px 8px", borderRadius: 6, fontWeight: 800 }}>READY PAIRS</span>
          </h2>
          <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", margin: "4px 0 0" }}>Auto-detecting A+ and Valid setups across the market.</p>
        </div>
        
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          {/* TF Selector */}
          <div style={{ display: "flex", background: "rgba(0,0,0,0.2)", borderRadius: 8, padding: 3, border: "1px solid rgba(255,255,255,0.05)" }}>
            {(["15m", "1h", "4h"] as const).map(tf => (
              <button
                key={tf}
                onClick={() => setEntryTf(tf)}
                style={{
                  padding: "6px 14px", borderRadius: 6, fontSize: "0.7rem", fontWeight: 800, cursor: "pointer", border: "none",
                  background: entryTf === tf ? "rgba(59,130,246,0.2)" : "transparent",
                  color: entryTf === tf ? "#60a5fa" : "#64748b",
                  transition: "all 0.2s"
                }}
              >
                {tf.toUpperCase()}
              </button>
            ))}
          </div>

          <button
            onClick={handleScan}
            disabled={isScanning || isLoading}
            style={{
              padding: "8px 16px", borderRadius: 8, fontSize: "0.75rem", fontWeight: 800, cursor: "pointer",
              background: "linear-gradient(135deg, #e879f9, #a855f7)",
              color: "#fff", border: "none", opacity: isScanning ? 0.7 : 1,
              display: "flex", alignItems: "center", gap: 8,
              boxShadow: "0 4px 14px rgba(232,121,249,0.25)",
            }}
          >
            {isScanning ? (
              <><span style={{ width: 12, height: 12, border: "2px solid rgba(255,255,255,0.3)", borderTopColor: "#fff", borderRadius: "50%", animation: "spin 0.8s linear infinite", display: "inline-block" }} />Scanning</>
            ) : "⚡ Force Scan"}
          </button>
        </div>
      </div>

      {/* ── Filter Bar (Bug #7) ── */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", padding: "10px 16px", borderRadius: 12, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
        <span style={{ fontSize: "0.65rem", fontWeight: 700, color: "var(--text-muted)", whiteSpace: "nowrap" }}>🔽 Filter:</span>

        {/* Grade filter */}
        {(["ALL", "A+", "VALID"] as const).map(g => (
          <button key={g} onClick={() => setGradeFilter(g)} style={{
            padding: "4px 12px", borderRadius: 6, fontSize: "0.65rem", fontWeight: 800, cursor: "pointer",
            background: gradeFilter === g ? "rgba(232,121,249,0.2)" : "rgba(255,255,255,0.04)",
            border: gradeFilter === g ? "1px solid rgba(232,121,249,0.5)" : "1px solid rgba(255,255,255,0.08)",
            color: gradeFilter === g ? "#e879f9" : "var(--text-muted)",
            transition: "all 0.15s",
          }}>
            {g === "ALL" ? "⭐ All" : g === "A+" ? "🏆 A+ Only" : "✅ Valid+"}
          </button>
        ))}

        <div style={{ width: 1, height: 20, background: "rgba(255,255,255,0.08)" }} />

        {/* Trend filter */}
        {(["ALL", "BULLISH", "BEARISH"] as const).map(t => {
          const col = t === "BULLISH" ? "#10b981" : t === "BEARISH" ? "#ef4444" : "#64748b";
          const isActive = trendFilter === t;
          return (
            <button key={t} onClick={() => setTrendFilter(t)} style={{
              padding: "4px 12px", borderRadius: 6, fontSize: "0.65rem", fontWeight: 800, cursor: "pointer",
              background: isActive ? `${col}20` : "rgba(255,255,255,0.04)",
              border: isActive ? `1px solid ${col}50` : "1px solid rgba(255,255,255,0.08)",
              color: isActive ? col : "var(--text-muted)",
              transition: "all 0.15s",
            }}>
              {t === "ALL" ? "🔄 All Trend" : t === "BULLISH" ? "▲ Bull" : "▼ Bear"}
            </button>
          );
        })}

        <div style={{ marginLeft: "auto", fontSize: "0.62rem", color: "var(--text-muted)" }}>
          Showing <strong style={{ color: "#e879f9" }}>{sortedPairs.length}</strong> / {data.length} pairs
        </div>
      </div>

      {/* ── Ready Pairs Grid ── */}
      {isLoading ? (
        <div style={{ padding: "60px 0", textAlign: "center" }}>
          <div style={{ width: 40, height: 40, border: "3px solid rgba(232,121,249,0.2)", borderTopColor: "#e879f9", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto" }} />
          <div style={{ marginTop: 16, fontSize: "0.85rem", fontWeight: 700, color: "#e879f9" }}>Scanning all pairs...</div>
        </div>
      ) : sortedPairs.length === 0 ? (
        <div style={{ padding: "60px 0", textAlign: "center", background: "rgba(255,255,255,0.01)", border: "1px dashed rgba(255,255,255,0.1)", borderRadius: 16 }}>
          <div style={{ fontSize: "2.5rem", marginBottom: 12 }}>🔍</div>
          <div style={{ fontSize: "0.95rem", fontWeight: 800, color: "var(--text-muted)", marginBottom: 4 }}>No ready pairs found for {entryTf.toUpperCase()}</div>
          <div style={{ fontSize: "0.75rem", color: "rgba(255,255,255,0.3)" }}>Wait for the next scan or switch timeframes.</div>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
          {sortedPairs.map(row => {
            const chgClr = row.price_change_24h > 0 ? "#22c55e" : row.price_change_24h < 0 ? "#ef4444" : "#64748b";
            const gradeColor = row.signal_grade === "A+" ? "#f59e0b" : "#10b981";
            
            return (
              <div key={row.symbol} style={{
                background: "linear-gradient(145deg, rgba(20,25,45,0.95), rgba(15,20,40,0.98))",
                border: `1px solid ${gradeColor}30`,
                borderRadius: 14, padding: 18, position: "relative",
                boxShadow: row.signal_grade === "A+" ? `0 4px 20px ${gradeColor}15` : "none",
                transition: "transform 0.2s",
                cursor: "pointer",
              }}
              className="pro-scanner-card"
              onClick={() => router.push(`/charts?symbol=${row.symbol}`)}
              >
                <style>{`
                  .pro-scanner-card:hover { transform: translateY(-3px); border-color: ${gradeColor}60 !important; }
                `}</style>
                
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 14 }}>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      <span style={{ fontSize: "1.15rem", fontWeight: 900, color: "#fff" }}>{row.symbol.replace("USDT","")}</span>
                      <span style={{ fontSize: "0.6rem", fontWeight: 800, color: gradeColor, background: `${gradeColor}15`, padding: "2px 6px", borderRadius: 4 }}>{row.signal_grade}</span>
                    </div>
                    <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.85rem", color: "#e2e8f0", fontWeight: 700 }}>
                        {row.latest_price >= 1 ? row.latest_price.toLocaleString("en-US", { maximumFractionDigits: 3 }) : row.latest_price.toFixed(5)}
                      </span>
                      <span style={{ fontSize: "0.65rem", fontWeight: 700, color: chgClr }}>
                        {row.price_change_24h > 0 ? "+" : ""}{row.price_change_24h.toFixed(2)}%
                      </span>
                    </div>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
                    <div style={{ fontSize: "0.6rem", color: "var(--text-muted)", fontWeight: 700, marginBottom: 2 }}>SCORE</div>
                    <div style={{ fontSize: "1.3rem", fontFamily: "'JetBrains Mono', monospace", fontWeight: 900, color: gradeColor }}>
                      {row.signal_score}
                    </div>
                  </div>
                </div>

                {/* Tags / Info */}
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 14 }}>
                  <div style={{ fontSize: "0.6rem", background: "rgba(255,255,255,0.05)", padding: "3px 8px", borderRadius: 5, color: "#94a3b8" }}>
                    {row.trend === "BULLISH" ? "▲ BULL" : row.trend === "BEARISH" ? "▼ BEAR" : "◆ SIDE"}
                  </div>
                  <div style={{ fontSize: "0.6rem", background: "rgba(255,255,255,0.05)", padding: "3px 8px", borderRadius: 5, color: "#94a3b8" }}>
                    {row.mtf_confirmation.replace("_", " ")}
                  </div>
                  {row.setup_status && row.setup_status !== "No setup" && (
                    <div style={{ fontSize: "0.6rem", background: "rgba(245,158,11,0.1)", color: "#f59e0b", padding: "3px 8px", borderRadius: 5, fontWeight: 700 }}>
                      ⚡ {row.setup_status}
                    </div>
                  )}
                </div>

                {/* Confluence Bar with Labels */}
                <div style={{ display: "flex", gap: 2, height: 6, borderRadius: 3, overflow: "hidden", marginBottom: 4 }}>
                  {(["STR", "PA", "SMC", "VOL", "TIM", "RR"] as const).map(k => {
                    const val = row.score_breakdown?.[k] || 0;
                    const bColor = val >= 70 ? "#22c55e" : val >= 40 ? "#f59e0b" : "#ef4444";
                    return <div key={k} style={{ flex: 1, background: bColor, opacity: val > 0 ? 1 : 0.2 }} title={`${SCORE_LABELS[k]}: ${val}/100`} />;
                  })}
                </div>
                <div style={{ display: "flex", gap: 2 }}>
                  {(["STR", "PA", "SMC", "VOL", "TIM", "RR"] as const).map(k => (
                    <div key={k} style={{ flex: 1, textAlign: "center", fontSize: "0.42rem", color: "var(--text-muted)", fontWeight: 700 }}>{k}</div>
                  ))}
                </div>

                {/* Actions */}
                <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
                  <button onClick={(e) => { e.stopPropagation(); onSetWAAlert?.(row); }} style={{ flex: 1, padding: "8px 0", borderRadius: 8, background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.2)", color: "#10b981", fontSize: "0.7rem", fontWeight: 800, cursor: "pointer", transition: "all 0.2s" }} onMouseEnter={e => e.currentTarget.style.background = "rgba(16,185,129,0.2)"} onMouseLeave={e => e.currentTarget.style.background = "rgba(16,185,129,0.1)"}>
                    🔔 WA Alert
                  </button>
                  <button onClick={(e) => { e.stopPropagation(); router.push(`/charts?symbol=${row.symbol}`); }} style={{ flex: 1, padding: "8px 0", borderRadius: 8, background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", color: "#fff", fontSize: "0.7rem", fontWeight: 800, cursor: "pointer", transition: "all 0.2s" }} onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.1)"} onMouseLeave={e => e.currentTarget.style.background = "rgba(255,255,255,0.05)"}>
                    📈 Open Chart
                  </button>
                </div>

              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
