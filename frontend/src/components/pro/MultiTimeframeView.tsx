"use client";

/**
 * Multi-Timeframe Confluence View
 * =================================
 * Shows 4H bias (HTF) + 1H setup (MTF) + 15M entry (LTF) in one view.
 * Each TF shows FVG bias + entry zone for that timeframe.
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { API_URL } from "@/lib/utils";

interface MTFProps {
  symbol: string;
}

interface TFData {
  tf: string;
  label: string;
  role: string;
  roleDesc: string;
  color: string;
  bias: string | null;
  grade: string | null;
  score: number;
  freshFVGs: number;
  nearestEntry: number | null;
  nearestSL: number | null;
  loading: boolean;
  error?: string;
}

const BIAS_COLOR: Record<string, string> = {
  STRONG_BUY: "#10b981", BUY: "#34d399",
  STRONG_SELL: "#ef4444", SELL: "#f87171",
  NEUTRAL: "#64748b",
};

const GRADE_COLOR: Record<string, string> = {
  "A+": "#10b981", "A": "#34d399", "B": "#3b82f6",
  "C": "#f59e0b", "D": "#f97316", "WAIT": "#64748b",
};

const TF_CONFIG = [
  { tf: "4h", label: "4H",  role: "HTF Bias",    color: "#6366f1", roleDesc: "Market Structure Direction" },
  { tf: "1h", label: "1H",  role: "MTF Setup",   color: "#3b82f6", roleDesc: "Setup Formation Zone" },
  { tf: "15m",label: "15M", role: "LTF Entry",   color: "#10b981", roleDesc: "Precision Entry Trigger" },
];

function TFCard({ data, price }: { data: TFData; price?: number }) {
  const biasColor = BIAS_COLOR[data.bias || "NEUTRAL"] || "#64748b";
  const gradeColor = GRADE_COLOR[data.grade || "D"] || "#64748b";

  return (
    <div style={{ borderRadius: 14, background: `${data.color}06`, border: `1px solid ${data.color}25`, overflow: "hidden", flex: 1, minWidth: 200 }}>
      {/* Header */}
      <div style={{ padding: "12px 16px", background: `${data.color}12`, borderBottom: `1px solid ${data.color}20` }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <div style={{ fontWeight: 900, fontSize: "1.4rem", color: data.color, lineHeight: 1 }}>{data.label}</div>
            <div style={{ fontSize: "0.6rem", color: "var(--text-muted)", marginTop: 2 }}>{data.role}</div>
          </div>
          {data.grade && (
            <div style={{ padding: "4px 12px", borderRadius: 8, background: `${gradeColor}20`, border: `1px solid ${gradeColor}40`, fontSize: "0.8rem", fontWeight: 900, color: gradeColor }}>
              {data.grade}
            </div>
          )}
        </div>
        <div style={{ fontSize: "0.55rem", color: `${data.color}80`, marginTop: 4 }}>{data.roleDesc}</div>
      </div>

      {/* Body */}
      <div style={{ padding: "14px 16px" }}>
        {data.loading ? (
          <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--text-muted)", fontSize: "0.7rem" }}>
            <span style={{ display: "inline-block", animation: "spin .9s linear infinite" }}>⟳</span> Loading...
          </div>
        ) : data.error ? (
          <div style={{ fontSize: "0.65rem", color: "#ef4444" }}>⚠️ {data.error}</div>
        ) : (
          <>
            {/* Bias */}
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: "0.55rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 4 }}>Bias</div>
              <div style={{ padding: "6px 12px", borderRadius: 8, background: `${biasColor}15`, border: `1px solid ${biasColor}30`, fontSize: "0.75rem", fontWeight: 900, color: biasColor, display: "inline-block" }}>
                {data.bias || "NEUTRAL"}
              </div>
            </div>

            {/* Score bar */}
            <div style={{ marginBottom: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.55rem", color: "var(--text-muted)", marginBottom: 4 }}>
                <span>Confluence Score</span>
                <span>{data.score}/100</span>
              </div>
              <div style={{ height: 6, borderRadius: 99, background: "rgba(255,255,255,0.05)", overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${data.score}%`, background: gradeColor, borderRadius: 99, transition: "width .6s" }} />
              </div>
            </div>

            {/* Metrics */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 12 }}>
              <div style={{ padding: "8px 10px", borderRadius: 8, background: "rgba(255,255,255,0.03)", textAlign: "center" }}>
                <div style={{ fontSize: "1rem", fontWeight: 900, color: "#6366f1" }}>{data.freshFVGs}</div>
                <div style={{ fontSize: "0.5rem", color: "var(--text-muted)" }}>Fresh FVGs</div>
              </div>
              <div style={{ padding: "8px 10px", borderRadius: 8, background: "rgba(255,255,255,0.03)", textAlign: "center" }}>
                <div style={{ fontSize: "0.72rem", fontWeight: 900, color: "#f59e0b", fontFamily: "monospace" }}>
                  {data.nearestEntry ? data.nearestEntry.toLocaleString("en", { maximumFractionDigits: 5 }) : "—"}
                </div>
                <div style={{ fontSize: "0.5rem", color: "var(--text-muted)" }}>Nearest Entry</div>
              </div>
            </div>

            {/* Price distance */}
            {price && data.nearestEntry && (
              <div style={{ padding: "6px 10px", borderRadius: 8, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", fontSize: "0.62rem", color: "var(--text-muted)" }}>
                Distance to entry: <strong style={{ color: data.color }}>
                  {Math.abs(((data.nearestEntry - price) / price) * 100).toFixed(2)}%
                </strong>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export function MultiTimeframeView({ symbol }: MTFProps) {
  const [tfData, setTFData] = useState<TFData[]>(
    TF_CONFIG.map(c => ({ ...c, bias: null, grade: null, score: 0, freshFVGs: 0, nearestEntry: null, nearestSL: null, loading: true }))
  );
  const [currentPrice, setCurrentPrice] = useState<number | undefined>();
  const [alignment, setAlignment] = useState<"bullish" | "bearish" | "mixed" | "neutral">("neutral");

  const fetchTF = useCallback(async (cfg: typeof TF_CONFIG[0]) => {
    try {
      const r = await fetch(`${API_URL}/api/v1/pro/fvg-breaker`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, timeframe: cfg.tf, limit: 80 }),
      });
      const data = await r.json();
      if (!currentPrice && data.current_price) setCurrentPrice(data.current_price);

      const freshFVGs = (data.bullish_fvgs || []).filter((f: any) => f.status === "FRESH").length
        + (data.bearish_fvgs || []).filter((f: any) => f.status === "FRESH").length;

      const bias = data.signals?.entry_bias || "NEUTRAL";
      let nearestFVG = null;
      if (bias.includes("BUY")) {
        nearestFVG = data.nearest?.bullish_fvg;
      } else if (bias.includes("SELL")) {
        nearestFVG = data.nearest?.bearish_fvg;
      }

      setTFData(prev => prev.map(d =>
        d.tf === cfg.tf ? {
          ...d,
          bias: bias,
          grade: data.ict_setup?.grade || "D",
          score: data.signals?.confluence_score || 0,
          freshFVGs,
          nearestEntry: nearestFVG?.entry_zone?.entry || null,
          nearestSL: nearestFVG?.entry_zone?.stop_loss || null,
          loading: false,
        } : d
      ));
    } catch (e: any) {
      setTFData(prev => prev.map(d =>
        d.tf === cfg.tf ? { ...d, loading: false, error: e.message } : d
      ));
    }
  }, [symbol, currentPrice]);

  const fetchAll = useCallback(() => {
    setTFData(prev => prev.map(d => ({ ...d, loading: true, error: undefined })));
    TF_CONFIG.forEach(cfg => fetchTF(cfg));
  }, [fetchTF]);

  // Bug #4 Fix: Debounce the API calls
  const debounceRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    setTFData(prev => prev.map(d => ({ ...d, loading: true, error: undefined })));
    
    debounceRef.current = setTimeout(() => {
      TF_CONFIG.forEach(cfg => fetchTF(cfg));
    }, 400); // 400ms debounce
    
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [symbol, fetchTF]);

  // Compute alignment
  useEffect(() => {
    const biases = tfData.filter(d => d.bias && d.bias !== "NEUTRAL").map(d => d.bias);
    const bullish = biases.filter(b => b?.includes("BUY")).length;
    const bearish = biases.filter(b => b?.includes("SELL")).length;
    if (bullish === 3) setAlignment("bullish");
    else if (bearish === 3) setAlignment("bearish");
    else if (bullish > bearish) setAlignment("bullish");
    else if (bearish > bullish) setAlignment("bearish");
    else setAlignment("neutral");
  }, [tfData]);

  const alignmentColor = { bullish: "#10b981", bearish: "#ef4444", mixed: "#f59e0b", neutral: "#64748b" }[alignment];
  const alignmentLabel = { bullish: "🟢 FULL BULLISH ALIGNMENT", bearish: "🔴 FULL BEARISH ALIGNMENT", mixed: "🟡 MIXED SIGNAL", neutral: "⚪ NEUTRAL" }[alignment];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div>
          <div style={{ fontWeight: 900, fontSize: "0.95rem" }}>📊 Multi-Timeframe Analysis — {symbol}</div>
          <div style={{ fontSize: "0.6rem", color: "var(--text-muted)", marginTop: 2 }}>4H HTF Bias → 1H Setup → 15M Entry</div>
        </div>
        <button onClick={fetchAll} style={{ padding: "6px 14px", borderRadius: 8, background: "rgba(59,130,246,0.12)", border: "1px solid rgba(59,130,246,0.3)", color: "#3b82f6", fontSize: "0.7rem", fontWeight: 800, cursor: "pointer" }}>
          🔄 Refresh
        </button>
      </div>

      {/* Alignment Banner */}
      <div style={{ padding: "10px 16px", borderRadius: 10, background: `${alignmentColor}10`, border: `1px solid ${alignmentColor}30`, marginBottom: 16, fontSize: "0.78rem", fontWeight: 800, color: alignmentColor }}>
        {alignmentLabel}
        {alignment === "bullish" && <span style={{ fontSize: "0.62rem", fontWeight: 400, color: "var(--text-muted)", marginLeft: 8 }}>→ All timeframes confirm BUY. Highest probability setup.</span>}
        {alignment === "bearish" && <span style={{ fontSize: "0.62rem", fontWeight: 400, color: "var(--text-muted)", marginLeft: 8 }}>→ All timeframes confirm SELL. Highest probability setup.</span>}
        {alignment === "mixed" && <span style={{ fontSize: "0.62rem", fontWeight: 400, color: "var(--text-muted)", marginLeft: 8 }}>→ Wait for higher TF to resolve before entry.</span>}
      </div>

      {/* TF Cards */}
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
        {tfData.map(d => (
          <TFCard key={d.tf} data={d} price={currentPrice} />
        ))}
      </div>

      {/* Cascade explanation */}
      <div style={{ marginTop: 16, padding: "12px 16px", borderRadius: 10, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", fontSize: "0.65rem", color: "var(--text-muted)", lineHeight: 1.6 }}>
        <strong style={{ color: "#fff" }}>📖 ICT Top-Down Analysis Rule:</strong>{" "}
        HTF (4H) menentukan arah bias. MTF (1H) membentuk setup & zone. LTF (15M) memberikan trigger entry presisi.
        Entry hanya valid jika 4H bias, 1H setup, dan 15M trigger semuanya aligned.
      </div>
    </div>
  );
}