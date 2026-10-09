"use client";

import { useState, useEffect } from "react";
import { API_URL } from "@/lib/utils";

interface WyckoffEvent {
  name: string;
  description: string;
}

interface WyckoffData {
  symbol: string;
  timeframe: string;
  schematic: string;
  phase: string;
  is_actionable: boolean;
  signal: string;
  events: WyckoffEvent[];
  description: string;
  range_high: number;
  range_low: number;
}

export function WyckoffPanel({ symbol, timeframe, autoLoad = true }: { symbol: string; timeframe: string; autoLoad?: boolean }) {
  const [data, setData] = useState<WyckoffData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchData = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/api/v1/pro/wyckoff`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, timeframe, limit: 150 })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (e: any) {
      setError(e.message || "Failed to fetch Wyckoff data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (autoLoad && symbol && timeframe) {
      fetchData();
    }
  }, [symbol, timeframe, autoLoad]);

  if (loading) {
    return <div style={{ padding: 20, color: "var(--text-muted)", fontSize: "0.8rem" }}>⏳ Analyzing Wyckoff schematics...</div>;
  }

  if (error) {
    return <div style={{ padding: 20, color: "#ef4444", fontSize: "0.8rem" }}>⚠️ {error}</div>;
  }

  if (!data) return null;

  const isAccum = data.schematic === "ACCUMULATION";
  const isDist = data.schematic === "DISTRIBUTION";
  const color = isAccum ? "#10b981" : isDist ? "#ef4444" : "#f59e0b";

  return (
    <div style={{ padding: 24, borderRadius: 16, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
            <span style={{ fontSize: "1.2rem" }}>📊</span>
            <span style={{ fontWeight: 800, fontSize: "1rem", color: "#fff" }}>Wyckoff Context</span>
            <span style={{ fontSize: "0.65rem", padding: "2px 6px", borderRadius: 4, background: "rgba(255,255,255,0.1)", color: "#cbd5e1" }}>Macro</span>
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{data.symbol} • {data.timeframe}</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <div style={{ padding: "4px 10px", borderRadius: 8, background: `${color}15`, border: `1px solid ${color}40`, color, fontSize: "0.75rem", fontWeight: 800 }}>
            {data.schematic}
          </div>
          <div style={{ padding: "4px 10px", borderRadius: 8, background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", color: "#fff", fontSize: "0.75rem", fontWeight: 800 }}>
            Phase {data.phase}
          </div>
        </div>
      </div>

      <p style={{ fontSize: "0.8rem", color: "#e2e8f0", lineHeight: 1.6, marginBottom: 20 }}>
        {data.description || (data.schematic === "NONE" ? "Market is currently not displaying a clear Wyckoff accumulation or distribution pattern." : `Market is currently in Wyckoff Phase ${data.phase} of ${data.schematic}.`)}
      </p>

      {data.schematic !== "NONE" && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
            <div style={{ padding: 12, borderRadius: 10, background: "rgba(16,185,129,0.05)", border: "1px dashed rgba(16,185,129,0.2)" }}>
              <div style={{ fontSize: "0.6rem", textTransform: "uppercase", color: "#10b981", marginBottom: 4, fontWeight: 700 }}>Range High</div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.9rem", color: "#fff", fontWeight: 800 }}>{data.range_high?.toLocaleString("en")}</div>
            </div>
            <div style={{ padding: 12, borderRadius: 10, background: "rgba(239,68,68,0.05)", border: "1px dashed rgba(239,68,68,0.2)" }}>
              <div style={{ fontSize: "0.6rem", textTransform: "uppercase", color: "#ef4444", marginBottom: 4, fontWeight: 700 }}>Range Low</div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.9rem", color: "#fff", fontWeight: 800 }}>{data.range_low?.toLocaleString("en")}</div>
            </div>
          </div>

          <div style={{ fontWeight: 800, fontSize: "0.85rem", marginBottom: 10 }}>Recent Events</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {(data.events || []).slice(-4).map((e, i) => (
              <div key={i} style={{ display: "flex", gap: 12, alignItems: "center", padding: "8px 12px", background: "rgba(255,255,255,0.03)", borderRadius: 8 }}>
                <span style={{ fontWeight: 800, color, fontSize: "0.75rem", width: 40 }}>{e.name}</span>
                <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>{e.description}</span>
              </div>
            ))}
          </div>

          {data.is_actionable && (
            <div style={{ marginTop: 16, padding: "10px 14px", borderRadius: 8, background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.3)", color: "#10b981", fontSize: "0.75rem", fontWeight: 700 }}>
              💡 Actionable Phase: Good R:R setups are highly probable here.
            </div>
          )}
        </>
      )}
    </div>
  );
}
