"use client";
import { useState, useEffect, useCallback } from "react";
import MainLayout from "@/components/layout/MainLayout";
import { api } from "@/lib/api";

const SYMBOLS = [
  // Mega caps
  "BTCUSDT", "ETHUSDT",
  // Large caps
  "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT",
  "AVAXUSDT", "DOTUSDT", "LINKUSDT", "DOGEUSDT",
  // Mid caps
  "LTCUSDT", "UNIUSDT", "AAVEUSDT", "ATOMUSDT",
  "NEARUSDT", "FTMUSDT", "MATICUSDT", "OPUSDT",
  "ARBUSDT", "APTUSDT", "SUIUSDT", "SEIUSDT",
  // DeFi
  "MKRUSDT", "CRVUSDT", "LDOUSDT", "SNXUSDT",
  "COMPUSDT", "1INCHUSDT",
  // AI / Data
  "FETUSDT", "RENDERUSDT", "WLDUSDT", "TAOUSDT",
  // Gaming / Metaverse
  "SANDUSDT", "MANAUSDT", "AXSUSDT", "IMXUSDT",
  // Layer 1 Alts
  "KASUSDT", "INJUSDT", "TIAUSDT", "STXUSDT",
];
const TIMEFRAMES = ["1d", "4h", "1h", "15m", "5m"];
const TF_LABELS: Record<string, string> = { "1d": "Daily", "4h": "4H", "1h": "1H", "15m": "15m", "5m": "5m" };

const BIAS_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  BULLISH:  { bg: "rgba(16,185,129,0.15)", text: "#10b981", border: "rgba(16,185,129,0.4)" },
  BEARISH:  { bg: "rgba(239,68,68,0.15)",  text: "#ef4444", border: "rgba(239,68,68,0.4)" },
  SIDEWAYS: { bg: "rgba(148,163,184,0.1)", text: "#94a3b8", border: "rgba(148,163,184,0.2)" },
};

const CONFIRM_COLORS: Record<string, string> = {
  STRONG:   "#10b981",
  MODERATE: "#f59e0b",
  WEAK:     "#f97316",
  NONE:     "#6b7280",
};

const CONFIRM_ICONS: Record<string, string> = {
  STRONG: "✅", MODERATE: "⚡", WEAK: "⚠️", NONE: "❌",
};

export default function MTFPage() {
  const [results, setResults] = useState<Record<string, any>>({});
  const [selected, setSelected] = useState("BTCUSDT");
  const [loading, setLoading] = useState(false);
  const [batchLoading, setBatchLoading] = useState(false);

  const loadSingle = useCallback(async (sym: string) => {
    setLoading(true);
    try {
      const res = await api.getMTFAnalysis(sym);
      setResults(prev => ({ ...prev, [sym]: res.mtf }));
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  const loadBatch = useCallback(async () => {
    setBatchLoading(true);
    try {
      const res = await api.getMTFBatch(SYMBOLS);
      const map: Record<string, any> = {};
      (res.results || []).forEach((r: any) => { map[r.symbol] = r; });
      setResults(map);
    } catch (e) { console.error(e); }
    finally { setBatchLoading(false); }
  }, []);

  useEffect(() => { loadSingle("BTCUSDT"); }, [loadSingle]);

  const detail = results[selected];

  return (
    <MainLayout>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 800, margin: 0, letterSpacing: "-0.03em" }}>
            Multi-Timeframe Confirmation
          </h1>
          <p style={{ color: "var(--text-secondary)", margin: "4px 0 0", fontSize: "0.85rem" }}>
            Signal is valid only when ≥2 consecutive timeframes align
          </p>
        </div>
        <button className="btn-primary" onClick={loadBatch} disabled={batchLoading}
          style={{ opacity: batchLoading ? 0.7 : 1 }}>
          {batchLoading ? "Scanning…" : "⚡ Scan All"}
        </button>
      </div>

      {/* Symbol Selector */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 24 }}>
        {SYMBOLS.map(sym => {
          const r = results[sym];
          const level = r?.confirmation_level || "NONE";
          const isSelected = selected === sym;
          return (
            <button key={sym} onClick={() => { setSelected(sym); if (!results[sym]) loadSingle(sym); }}
              style={{
                padding: "8px 14px", borderRadius: 10, border: `2px solid ${isSelected ? "var(--accent)" : "var(--border)"}`,
                background: isSelected ? "rgba(139,92,246,0.15)" : "var(--card-bg)",
                color: isSelected ? "var(--accent)" : "var(--text-primary)",
                cursor: "pointer", fontWeight: isSelected ? 700 : 500, fontSize: "0.82rem",
                display: "flex", alignItems: "center", gap: 6, transition: "all 0.2s",
              }}>
              {CONFIRM_ICONS[level]} {sym.replace("USDT", "")}
            </button>
          );
        })}
      </div>

      {loading && !detail && (
        <div style={{ textAlign: "center", padding: "60px 0", color: "var(--text-secondary)" }}>
          Analyzing timeframes…
        </div>
      )}

      {detail && (
        <>
          {/* Summary Banner */}
          <div style={{
            background: `linear-gradient(135deg, ${CONFIRM_COLORS[detail.confirmation_level]}22 0%, transparent 100%)`,
            border: `1px solid ${CONFIRM_COLORS[detail.confirmation_level]}55`,
            borderRadius: 16, padding: "20px 24px", marginBottom: 24,
            display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12,
          }}>
            <div>
              <div style={{ fontSize: "1.1rem", fontWeight: 700, color: CONFIRM_COLORS[detail.confirmation_level] }}>
                {CONFIRM_ICONS[detail.confirmation_level]} {detail.confirmation_level} CONFIRMATION
              </div>
              <div style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: 4 }}>
                {detail.summary}
              </div>
            </div>
            <div style={{ display: "flex", gap: 20 }}>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: "1.8rem", fontWeight: 800, color: CONFIRM_COLORS[detail.confirmation_level] }}>
                  {detail.agreement_score}/{detail.total_timeframes}
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", textTransform: "uppercase" }}>TFs Aligned</div>
              </div>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: "1.8rem", fontWeight: 800,
                  color: detail.dominant_bias === "BULLISH" ? "#10b981" : detail.dominant_bias === "BEARISH" ? "#ef4444" : "#94a3b8" }}>
                  {detail.dominant_bias === "BULLISH" ? "▲" : detail.dominant_bias === "BEARISH" ? "▼" : "—"}
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", textTransform: "uppercase" }}>Bias</div>
              </div>
            </div>
          </div>

          {/* MTF Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12, marginBottom: 24 }}>
            {TIMEFRAMES.map(tf => {
              const t = detail.per_tf?.[tf];
              if (!t) return null;
              const c = BIAS_COLORS[t.bias] || BIAS_COLORS.SIDEWAYS;
              return (
                <div key={tf} style={{
                  background: c.bg, border: `1px solid ${c.border}`, borderRadius: 14,
                  padding: "18px 16px", position: "relative", overflow: "hidden",
                }}>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>
                    {t.label}
                  </div>
                  <div style={{ fontSize: "1.2rem", fontWeight: 800, color: c.text, marginBottom: 12 }}>
                    {t.bias}
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                    {[
                      { label: "OBs", val: t.ob_count },
                      { label: "FVGs", val: t.fvg_count },
                      { label: "Liq Levels", val: t.liq_levels },
                    ].map(({ label, val }) => (
                      <div key={label} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.78rem" }}>
                        <span style={{ color: "var(--text-secondary)" }}>{label}</span>
                        <span style={{ fontWeight: 700, color: "var(--text-primary)" }}>{val}</span>
                      </div>
                    ))}
                    {t.bos && <span style={{ fontSize: "0.72rem", color: "#f59e0b", fontWeight: 600, marginTop: 4 }}>⚡ BOS</span>}
                    {t.choch && <span style={{ fontSize: "0.72rem", color: "#a78bfa", fontWeight: 600, marginTop: 4 }}>🔄 CHOCH</span>}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Batch Overview */}
          {Object.keys(results).length > 1 && (
            <>
              <h2 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: 14 }}>All Symbols Overview</h2>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
                {Object.values(results).map((r: any) => (
                  <div key={r.symbol} onClick={() => setSelected(r.symbol)}
                    style={{
                      padding: "14px 18px", background: "var(--card-bg)", border: `1px solid ${selected === r.symbol ? "var(--accent)" : "var(--border)"}`,
                      borderRadius: 12, cursor: "pointer", transition: "all 0.2s",
                      display: "flex", alignItems: "center", justifyContent: "space-between",
                    }}>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>{r.symbol}</div>
                      <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: 2 }}>{r.summary}</div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: "1.4rem" }}>{CONFIRM_ICONS[r.confirmation_level]}</div>
                      <div style={{ fontSize: "0.72rem", color: CONFIRM_COLORS[r.confirmation_level], fontWeight: 700 }}>
                        {r.confirmation_level}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </MainLayout>
  );
}
