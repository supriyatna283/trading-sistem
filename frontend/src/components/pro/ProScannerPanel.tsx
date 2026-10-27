"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import { API_URL } from "@/lib/utils";
import { useRouter } from "next/navigation";

interface TradeSetupPlan {
  symbol: string;
  direction: "BUY" | "SELL";
  entry_price?: number;
  entry_low: number;
  entry_high: number;
  stop_loss: number;
  take_profit_1: number;
  take_profit_2: number;
  take_profit_3?: number;
  risk_reward: number;
  risk_pct?: number;
  setup_type?: string;
  pd_zone?: string;
  in_ote?: boolean;
}

interface ScanResult {
  symbol: string;
  trend: string;
  latest_price: number;
  price_change_24h: number;
  liquidity_status?: string;
  setup_status: string;
  signal_score: number;
  signal_grade: "A+" | "VALID" | "WEAK" | "NO_TRADE";
  score_breakdown: { STR: number; PA: number; SMC: number; VOL: number; TIM: number; RR: number };
  hard_rejected?: boolean;
  rejection_reasons?: string[];
  mtf_confirmation: string;
  ict_badges?: string[];
  pd_zone?: string;
  in_ote?: boolean;
  rsi_1h?: number | null;
  orderbook_bias?: string;
  market_cap_tier?: string;
  volume_delta?: number | null;
  setup: TradeSetupPlan | null;
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
  STR: "Strength & HTF",
  PA: "Price Action (Fib/RSI/MACD)",
  SMC: "Smart Money (OB/FVG/Sweep)",
  VOL: "Volume Confirmation",
  TIM: "Session & News Timing",
  RR: "Risk:Reward & Orderflow",
};

function fmtPrice(p: number | undefined | null): string {
  if (p == null || Number.isNaN(Number(p))) return "—";
  const val = Number(p);
  if (val >= 1000) return val.toLocaleString("en-US", { maximumFractionDigits: 2 });
  if (val >= 1) return val.toLocaleString("en-US", { maximumFractionDigits: 4 });
  return val.toFixed(5);
}

export function ProScannerPanel({
  defaultTf = "1h",
  isActive = true,
  onSetWAAlert,
  onSelectSymbol,
  onLoadPosCalc,
}: {
  defaultTf?: string;
  isActive?: boolean;
  onSetWAAlert?: (data: any) => void;
  onSelectSymbol?: (symbol: string) => void;
  onLoadPosCalc?: (plan: any, symbol?: string) => void;
}) {
  const router = useRouter();
  const [data, setData] = useState<ScanResult[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isScanning, setIsScanning] = useState(false);
  const [entryTf, setEntryTf] = useState(defaultTf);
  const [trendFilter, setTrendFilter] = useState<"ALL" | "BULLISH" | "BEARISH">("ALL");
  const [gradeFilter, setGradeFilter] = useState<"READY" | "A+" | "VALID" | "ALL">("READY");
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

  // Auto-refresh every minute for scanner, every 30s for killzone (only when tab is active)
  useEffect(() => {
    if (!isActive) return;
    autoRefreshRef.current = setInterval(() => fetchData(true), 60000);
    const kzInterval = setInterval(fetchKZ, 30000);
    return () => {
      if (autoRefreshRef.current) clearInterval(autoRefreshRef.current);
      clearInterval(kzInterval);
    };
  }, [fetchData, fetchKZ, isActive]);

  // Summary metrics across all scanned pairs
  const readyPairs = data.filter(
    r => !r.hard_rejected && (r.signal_grade === "A+" || r.signal_grade === "VALID") && r.setup !== null
  );
  const aPlusCount = readyPairs.filter(r => r.signal_grade === "A+").length;
  const validCount = readyPairs.filter(r => r.signal_grade === "VALID").length;
  const longCount = readyPairs.filter(r => (r.setup?.direction || (r.trend === "BULLISH" ? "BUY" : "SELL")) === "BUY").length;
  const shortCount = readyPairs.filter(r => (r.setup?.direction || (r.trend === "BEARISH" ? "SELL" : "BUY")) === "SELL").length;
  const avgRR = readyPairs.length > 0
    ? (readyPairs.reduce((acc, r) => acc + Number(r.setup?.risk_reward || 2.0), 0) / readyPairs.length).toFixed(2)
    : "—";

  // Multi-filter: grade + trend
  const filteredPairs = data.filter(r => {
    const isActionable = !r.hard_rejected && (r.signal_grade === "A+" || r.signal_grade === "VALID") && r.setup !== null;
    const gradeOk =
      gradeFilter === "READY"
        ? isActionable
        : gradeFilter === "A+"
        ? isActionable && r.signal_grade === "A+"
        : gradeFilter === "VALID"
        ? isActionable && r.signal_grade === "VALID"
        : true; // "ALL" shows all scanned pairs including Watchlist / Rejected
    const dir = r.setup?.direction === "BUY" ? "BULLISH" : r.setup?.direction === "SELL" ? "BEARISH" : r.trend;
    const trendOk = trendFilter === "ALL" || dir === trendFilter;
    return gradeOk && trendOk;
  });

  const sortedPairs = [...filteredPairs].sort((a, b) => {
    const aReady = (!a.hard_rejected && a.setup !== null) ? 1 : 0;
    const bReady = (!b.hard_rejected && b.setup !== null) ? 1 : 0;
    if (aReady !== bReady) return bReady - aReady;
    return (b.signal_score || 0) - (a.signal_score || 0);
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* ── Killzone Banner ── */}
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
            <span style={{ color: "#e879f9" }}>📡 Institutional Live Market Scanner</span>
            <span style={{ fontSize: "0.62rem", background: "rgba(232,121,249,0.15)", color: "#e879f9", padding: "3px 8px", borderRadius: 6, fontWeight: 800, border: "1px solid rgba(232,121,249,0.3)" }}>
              HYBRID QUANT + ICT
            </span>
          </h2>
          <p style={{ fontSize: "0.73rem", color: "var(--text-muted)", margin: "4px 0 0" }}>
            Scans 20+ pairs for aligned HTF Bias, Structure, Discount/Premium OTE, Liquidity Sweep & OB/FVG Trade Plans.
          </p>
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

      {/* ── Market Pulse Summary Strip ── */}
      {!isLoading && data.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 10 }}>
          <div style={{ padding: "10px 14px", borderRadius: 12, background: "rgba(232,121,249,0.06)", border: "1px solid rgba(232,121,249,0.2)" }}>
            <div style={{ fontSize: "0.58rem", color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase" }}>⚡ Ready Setups</div>
            <div style={{ fontSize: "1.15rem", fontWeight: 900, color: "#e879f9", fontFamily: "'JetBrains Mono', monospace", marginTop: 2 }}>
              {readyPairs.length} <span style={{ fontSize: "0.68rem", color: "var(--text-muted)", fontWeight: 600 }}>/ {data.length} pairs</span>
            </div>
          </div>
          <div style={{ padding: "10px 14px", borderRadius: 12, background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.2)" }}>
            <div style={{ fontSize: "0.58rem", color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase" }}>🏆 A+ / ✅ Valid</div>
            <div style={{ fontSize: "1.15rem", fontWeight: 900, color: "#f59e0b", fontFamily: "'JetBrains Mono', monospace", marginTop: 2 }}>
              {aPlusCount} A+ <span style={{ fontSize: "0.75rem", color: "#10b981" }}>· {validCount} Valid</span>
            </div>
          </div>
          <div style={{ padding: "10px 14px", borderRadius: 12, background: "rgba(16,185,129,0.06)", border: "1px solid rgba(16,185,129,0.2)" }}>
            <div style={{ fontSize: "0.58rem", color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase" }}>📊 Directional Skew</div>
            <div style={{ fontSize: "1.05rem", fontWeight: 900, fontFamily: "'JetBrains Mono', monospace", marginTop: 2 }}>
              <span style={{ color: "#10b981" }}>{longCount} LONG</span>
              <span style={{ color: "var(--text-muted)", margin: "0 6px" }}>/</span>
              <span style={{ color: "#ef4444" }}>{shortCount} SHORT</span>
            </div>
          </div>
          <div style={{ padding: "10px 14px", borderRadius: 12, background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.2)" }}>
            <div style={{ fontSize: "0.58rem", color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase" }}>📐 Avg Risk:Reward</div>
            <div style={{ fontSize: "1.15rem", fontWeight: 900, color: "#818cf8", fontFamily: "'JetBrains Mono', monospace", marginTop: 2 }}>
              {avgRR !== "—" ? `1:${avgRR}` : "—"}
            </div>
          </div>
        </div>
      )}

      {/* ── Filter Bar ── */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", padding: "10px 16px", borderRadius: 12, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
        <span style={{ fontSize: "0.65rem", fontWeight: 700, color: "var(--text-muted)", whiteSpace: "nowrap" }}>🔽 Filter:</span>

        {/* Grade filter */}
        {(["READY", "A+", "VALID", "ALL"] as const).map(g => (
          <button key={g} onClick={() => setGradeFilter(g)} style={{
            padding: "4px 12px", borderRadius: 6, fontSize: "0.65rem", fontWeight: 800, cursor: "pointer",
            background: gradeFilter === g ? "rgba(232,121,249,0.2)" : "rgba(255,255,255,0.04)",
            border: gradeFilter === g ? "1px solid rgba(232,121,249,0.5)" : "1px solid rgba(255,255,255,0.08)",
            color: gradeFilter === g ? "#e879f9" : "var(--text-muted)",
            transition: "all 0.15s",
          }}>
            {g === "READY"
              ? `⚡ Ready (${readyPairs.length})`
              : g === "A+"
              ? `🏆 A+ Only (${aPlusCount})`
              : g === "VALID"
              ? `✅ Valid (${validCount})`
              : `📋 All Scanned (${data.length})`}
          </button>
        ))}

        <div style={{ width: 1, height: 20, background: "rgba(255,255,255,0.08)" }} />

        {/* Trend filter */}
        {(["ALL", "BULLISH", "BEARISH"] as const).map(t => {
          const col = t === "BULLISH" ? "#10b981" : t === "BEARISH" ? "#ef4444" : "#64748b";
          const isAct = trendFilter === t;
          return (
            <button key={t} onClick={() => setTrendFilter(t)} style={{
              padding: "4px 12px", borderRadius: 6, fontSize: "0.65rem", fontWeight: 800, cursor: "pointer",
              background: isAct ? `${col}20` : "rgba(255,255,255,0.04)",
              border: isAct ? `1px solid ${col}50` : "1px solid rgba(255,255,255,0.08)",
              color: isAct ? col : "var(--text-muted)",
              transition: "all 0.15s",
            }}>
              {t === "ALL" ? "🔄 All Bias" : t === "BULLISH" ? "🟢 Long / Bull" : "🔴 Short / Bear"}
            </button>
          );
        })}

        <div style={{ marginLeft: "auto", fontSize: "0.62rem", color: "var(--text-muted)" }}>
          Showing <strong style={{ color: "#e879f9" }}>{sortedPairs.length}</strong> / {data.length} pairs
        </div>
      </div>

      {/* ── Scanner Cards Grid ── */}
      {isLoading ? (
        <div style={{ padding: "60px 0", textAlign: "center" }}>
          <div style={{ width: 40, height: 40, border: "3px solid rgba(232,121,249,0.2)", borderTopColor: "#e879f9", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto" }} />
          <div style={{ marginTop: 16, fontSize: "0.85rem", fontWeight: 700, color: "#e879f9" }}>Scanning all pairs...</div>
        </div>
      ) : sortedPairs.length === 0 ? (
        <div style={{ padding: "50px 20px", textAlign: "center", background: "rgba(255,255,255,0.01)", border: "1px dashed rgba(255,255,255,0.1)", borderRadius: 16 }}>
          <div style={{ fontSize: "2.2rem", marginBottom: 10 }}>🔍</div>
          <div style={{ fontSize: "0.95rem", fontWeight: 800, color: "var(--text-muted)", marginBottom: 6 }}>
            No pairs match this filter on {entryTf.toUpperCase()}
          </div>
          <div style={{ fontSize: "0.73rem", color: "rgba(255,255,255,0.45)", marginBottom: 14 }}>
            Switch to <strong>📋 All Scanned</strong> to inspect forming watchlist pairs or try another timeframe.
          </div>
          {gradeFilter !== "ALL" && (
            <button
              onClick={() => { setGradeFilter("ALL"); setTrendFilter("ALL"); }}
              style={{
                padding: "7px 16px", borderRadius: 8, fontSize: "0.72rem", fontWeight: 800, cursor: "pointer",
                background: "rgba(232,121,249,0.15)", border: "1px solid rgba(232,121,249,0.4)", color: "#e879f9",
              }}
            >
              📋 Show All {data.length} Scanned Pairs
            </button>
          )}
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(330px, 1fr))", gap: 16 }}>
          {sortedPairs.map(row => {
            const chgClr = row.price_change_24h > 0 ? "#22c55e" : row.price_change_24h < 0 ? "#ef4444" : "#64748b";
            const gradeColor =
              row.signal_grade === "A+" ? "#f59e0b" :
              row.signal_grade === "VALID" ? "#10b981" :
              row.signal_grade === "WEAK" ? "#60a5fa" : "#64748b";
            const setup = row.setup;
            const tradeDir = setup?.direction || (row.trend === "BULLISH" ? "BUY" : row.trend === "BEARISH" ? "SELL" : null);
            const dirColor = tradeDir === "BUY" ? "#10b981" : tradeDir === "SELL" ? "#ef4444" : "#94a3b8";
            const badges = Array.isArray(row.ict_badges) ? row.ict_badges : [];

            return (
              <div
                key={row.symbol}
                style={{
                  background: "linear-gradient(145deg, rgba(20,25,45,0.96), rgba(13,18,35,0.99))",
                  border: `1px solid ${setup ? gradeColor + "40" : "rgba(255,255,255,0.08)"}`,
                  borderRadius: 16,
                  padding: 18,
                  position: "relative",
                  boxShadow: row.signal_grade === "A+" ? `0 6px 24px ${gradeColor}18` : "none",
                  transition: "transform 0.2s, border-color 0.2s",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                }}
              >
                <div>
                  {/* ── Card Header: Symbol, Grade, Direction Pill, Score ── */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 5, flexWrap: "wrap" }}>
                        <span style={{ fontSize: "1.18rem", fontWeight: 900, color: "#fff", letterSpacing: "-0.02em" }}>
                          {row.symbol.replace("USDT", "")}
                          <span style={{ fontSize: "0.65rem", color: "var(--text-muted)", fontWeight: 600 }}>/USDT</span>
                        </span>
                        <span style={{
                          fontSize: "0.6rem", fontWeight: 900, color: gradeColor,
                          background: `${gradeColor}18`, border: `1px solid ${gradeColor}45`,
                          padding: "2px 7px", borderRadius: 5,
                        }}>
                          {row.signal_grade}
                        </span>
                        {tradeDir && (
                          <span style={{
                            fontSize: "0.6rem", fontWeight: 900, color: dirColor,
                            background: `${dirColor}18`, border: `1px solid ${dirColor}45`,
                            padding: "2px 8px", borderRadius: 5,
                          }}>
                            {tradeDir === "BUY" ? "🟢 LONG" : "🔴 SHORT"}
                          </span>
                        )}
                      </div>
                      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.9rem", color: "#e2e8f0", fontWeight: 800 }}>
                          ${fmtPrice(row.latest_price)}
                        </span>
                        <span style={{ fontSize: "0.68rem", fontWeight: 700, color: chgClr }}>
                          {row.price_change_24h > 0 ? "+" : ""}{row.price_change_24h.toFixed(2)}%
                        </span>
                        {row.rsi_1h != null && (
                          <span style={{ fontSize: "0.58rem", color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace" }}>
                            RSI {Number(row.rsi_1h).toFixed(0)}
                          </span>
                        )}
                      </div>
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
                      <div style={{ fontSize: "0.55rem", color: "var(--text-muted)", fontWeight: 800, letterSpacing: "0.05em" }}>SCORE</div>
                      <div style={{ fontSize: "1.35rem", fontFamily: "'JetBrains Mono', monospace", fontWeight: 900, color: gradeColor, lineHeight: 1.1 }}>
                        {row.signal_score}
                      </div>
                      <div style={{ fontSize: "0.55rem", color: "#94a3b8", fontWeight: 700, marginTop: 2 }}>
                        MTF: {row.mtf_confirmation?.replace("_", " ") || "NONE"}
                      </div>
                    </div>
                  </div>

                  {/* ── ICT & Quant Confluence Badges ── */}
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 12 }}>
                    {badges.length > 0 ? (
                      badges.map((b, idx) => (
                        <span
                          key={idx}
                          style={{
                            fontSize: "0.58rem",
                            fontWeight: 800,
                            padding: "2px 7px",
                            borderRadius: 5,
                            background: b.includes("OTE") || b.includes("Sweep")
                              ? "rgba(245,158,11,0.14)"
                              : b.includes("FVG") || b.includes("OB") || b.includes("Breaker")
                              ? "rgba(99,102,241,0.16)"
                              : "rgba(255,255,255,0.06)",
                            color: b.includes("OTE") || b.includes("Sweep")
                              ? "#fbbf24"
                              : b.includes("FVG") || b.includes("OB") || b.includes("Breaker")
                              ? "#a5b4fc"
                              : "#cbd5e1",
                            border: "1px solid rgba(255,255,255,0.08)",
                          }}
                        >
                          {b}
                        </span>
                      ))
                    ) : (
                      <span style={{ fontSize: "0.6rem", color: "var(--text-muted)" }}>
                        {row.setup_status}
                      </span>
                    )}
                    {row.orderbook_bias && row.orderbook_bias !== "NEUTRAL" && (
                      <span style={{
                        fontSize: "0.56rem", fontWeight: 700, padding: "2px 6px", borderRadius: 5,
                        background: "rgba(255,255,255,0.04)", color: "#94a3b8", border: "1px solid rgba(255,255,255,0.06)"
                      }}>
                        OBook: {row.orderbook_bias}
                      </span>
                    )}
                  </div>

                  {/* ── Actionable Institutional Trade Plan Box (or Watchlist Status) ── */}
                  {setup ? (
                    <div style={{
                      padding: "10px 12px",
                      borderRadius: 10,
                      background: tradeDir === "BUY" ? "rgba(16,185,129,0.06)" : "rgba(239,68,68,0.06)",
                      border: `1px solid ${tradeDir === "BUY" ? "rgba(16,185,129,0.22)" : "rgba(239,68,68,0.22)"}`,
                      marginBottom: 12,
                    }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 7 }}>
                        <span style={{ fontSize: "0.62rem", fontWeight: 800, color: dirColor }}>
                          🎯 {setup.setup_type || `${setup.direction} Setup`}
                        </span>
                        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                          {setup.risk_pct != null && (
                            <span style={{ fontSize: "0.56rem", color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace" }}>
                              Risk {setup.risk_pct}%
                            </span>
                          )}
                          <span style={{
                            fontSize: "0.6rem", fontWeight: 900, fontFamily: "'JetBrains Mono', monospace",
                            padding: "1px 6px", borderRadius: 4, background: "rgba(255,255,255,0.08)", color: "#f8fafc"
                          }}>
                            R:R 1:{setup.risk_reward}
                          </span>
                        </div>
                      </div>

                      <div style={{ display: "grid", gridTemplateColumns: "1.35fr 1fr 1fr 1fr", gap: 6, fontSize: "0.62rem", fontFamily: "'JetBrains Mono', monospace" }}>
                        <div style={{ background: "rgba(0,0,0,0.25)", padding: "5px 7px", borderRadius: 6 }}>
                          <div style={{ fontSize: "0.5rem", color: "var(--text-muted)", fontWeight: 700, marginBottom: 1 }}>ENTRY ZONE</div>
                          <div style={{ color: "#e2e8f0", fontWeight: 800, fontSize: "0.6rem" }}>
                            {fmtPrice(setup.entry_low)}–{fmtPrice(setup.entry_high)}
                          </div>
                        </div>
                        <div style={{ background: "rgba(0,0,0,0.25)", padding: "5px 7px", borderRadius: 6 }}>
                          <div style={{ fontSize: "0.5rem", color: "#fca5a5", fontWeight: 700, marginBottom: 1 }}>STOP LOSS</div>
                          <div style={{ color: "#ef4444", fontWeight: 800 }}>{fmtPrice(setup.stop_loss)}</div>
                        </div>
                        <div style={{ background: "rgba(0,0,0,0.25)", padding: "5px 7px", borderRadius: 6 }}>
                          <div style={{ fontSize: "0.5rem", color: "#86efac", fontWeight: 700, marginBottom: 1 }}>TP1 (1.5R)</div>
                          <div style={{ color: "#22c55e", fontWeight: 800 }}>{fmtPrice(setup.take_profit_1)}</div>
                        </div>
                        <div style={{ background: "rgba(0,0,0,0.25)", padding: "5px 7px", borderRadius: 6 }}>
                          <div style={{ fontSize: "0.5rem", color: "#4ade80", fontWeight: 700, marginBottom: 1 }}>TP2 (2.5R)</div>
                          <div style={{ color: "#10b981", fontWeight: 800 }}>{fmtPrice(setup.take_profit_2)}</div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div style={{
                      padding: "9px 12px", borderRadius: 10, marginBottom: 12,
                      background: "rgba(255,255,255,0.02)", border: "1px dashed rgba(255,255,255,0.08)",
                      fontSize: "0.64rem", color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 8
                    }}>
                      <span>⏳</span>
                      <span>
                        <strong>Watchlist / Filtered:</strong>{" "}
                        {row.rejection_reasons && row.rejection_reasons.length > 0
                          ? row.rejection_reasons.join(" · ")
                          : row.setup_status || "Waiting for higher confluence"}
                      </span>
                    </div>
                  )}

                  {/* ── 6-Pillar Confluence Bar ── */}
                  <div style={{ display: "flex", gap: 3, height: 6, borderRadius: 3, overflow: "hidden", marginBottom: 5 }}>
                    {(["STR", "PA", "SMC", "VOL", "TIM", "RR"] as const).map(k => {
                      const val = row.score_breakdown?.[k] || 0;
                      const bColor = val >= 70 ? "#22c55e" : val >= 40 ? "#f59e0b" : "#ef4444";
                      return <div key={k} style={{ flex: 1, background: bColor, opacity: val > 0 ? 1 : 0.2 }} title={`${SCORE_LABELS[k]}: ${val}/100`} />;
                    })}
                  </div>
                  <div style={{ display: "flex", gap: 3 }}>
                    {(["STR", "PA", "SMC", "VOL", "TIM", "RR"] as const).map(k => {
                      const val = row.score_breakdown?.[k] || 0;
                      return (
                        <div key={k} style={{ flex: 1, textAlign: "center", fontSize: "0.46rem", color: "var(--text-muted)", fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>
                          {k} <span style={{ color: val >= 70 ? "#22c55e" : val >= 40 ? "#f59e0b" : "#94a3b8" }}>{val}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* ── Action Buttons ── */}
                <div style={{ display: "flex", gap: 6, marginTop: 14 }}>
                  {onSelectSymbol && (
                    <button
                      onClick={(e) => { e.stopPropagation(); onSelectSymbol(row.symbol); }}
                      style={{
                        flex: 1, padding: "7px 0", borderRadius: 8,
                        background: "rgba(99,102,241,0.14)", border: "1px solid rgba(99,102,241,0.3)",
                        color: "#818cf8", fontSize: "0.65rem", fontWeight: 800, cursor: "pointer",
                      }}
                      title="Open deep ICT Confluence analysis for this pair"
                    >
                      ⚡ ICT Detail
                    </button>
                  )}
                  {setup && onLoadPosCalc && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        const entryMid = setup.entry_price ?? (setup.entry_low + setup.entry_high) / 2;
                        onLoadPosCalc(
                          {
                            entry: entryMid,
                            stop_loss: setup.stop_loss,
                            tp1: setup.take_profit_1,
                            tp2: setup.take_profit_2,
                            direction: setup.direction,
                            source: `Live Scanner (${row.symbol} ${entryTf.toUpperCase()})`,
                          },
                          row.symbol
                        );
                      }}
                      style={{
                        flex: 1, padding: "7px 0", borderRadius: 8,
                        background: "rgba(167,139,250,0.14)", border: "1px solid rgba(167,139,250,0.35)",
                        color: "#c4b5fd", fontSize: "0.65rem", fontWeight: 800, cursor: "pointer",
                      }}
                      title="Load Entry, Stop Loss & TP into Position Sizing Calculator"
                    >
                      🔢 Pos Calc
                    </button>
                  )}
                  <button
                    onClick={(e) => { e.stopPropagation(); onSetWAAlert?.(row); }}
                    style={{
                      flex: 1, padding: "7px 0", borderRadius: 8,
                      background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.25)",
                      color: "#10b981", fontSize: "0.65rem", fontWeight: 800, cursor: "pointer",
                    }}
                    title="Send Trade Plan to WhatsApp"
                  >
                    🔔 WA
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); router.push(`/charts?symbol=${row.symbol}`); }}
                    style={{
                      flex: 0.9, padding: "7px 0", borderRadius: 8,
                      background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)",
                      color: "#fff", fontSize: "0.65rem", fontWeight: 800, cursor: "pointer",
                    }}
                    title="Open interactive chart + DeepSeek AI"
                  >
                    📈 Chart
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
