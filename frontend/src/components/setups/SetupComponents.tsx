"use client";

import { formatPrice } from "@/lib/utils";

// ─── Gauge ───────────────────────────────────────────────────────────────────
interface GaugeProps {
  value?: number | null;
  min?: number;
  max?: number;
  label: string;
  color: string;
}
export function Gauge({ value, min = 0, max = 100, label, color }: GaugeProps) {
  const pct = Math.min(100, Math.max(0, (((value ?? 0) - min) / (max - min)) * 100));
  return (
    <div style={{ flex: 1 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontSize: "0.6rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
          {label}
        </span>
        <span style={{ fontSize: "0.65rem", fontWeight: 800, color, fontFamily: "'JetBrains Mono', monospace" }}>
          {value?.toFixed(1) ?? "–"}
        </span>
      </div>
      <div style={{ height: 4, borderRadius: 99, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 99, transition: "width 0.6s ease" }} />
      </div>
    </div>
  );
}

// ─── BBPosition ───────────────────────────────────────────────────────────────
interface BBPositionProps {
  upper?: number | null;
  middle?: number | null;
  lower?: number | null;
  close?: number | null;
}
export function BBPosition({ upper, middle, lower, close }: BBPositionProps) {
  if (!upper || !lower || !close) return null;
  const range = upper - lower;
  const pct = range > 0 ? ((close - lower) / range) * 100 : 50;
  const zone =
    pct <= 25
      ? { label: "LOWER BAND", color: "#10b981" }
      : pct >= 75
      ? { label: "UPPER BAND", color: "#ef4444" }
      : { label: "MID BAND", color: "#f59e0b" };

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, height: 6, borderRadius: 99, background: "rgba(255,255,255,0.06)", position: "relative" }}>
        <div
          style={{
            position: "absolute",
            top: 0,
            left: `calc(${Math.min(98, Math.max(2, pct))}% - 4px)`,
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: zone.color,
            marginTop: -1,
            boxShadow: `0 0 6px ${zone.color}`,
          }}
        />
      </div>
      <span style={{ fontSize: "0.6rem", fontWeight: 800, color: zone.color, whiteSpace: "nowrap" }}>
        {zone.label}
      </span>
    </div>
  );
}

// ─── ScoreRing ────────────────────────────────────────────────────────────────
interface ScoreRingProps {
  score: number;
}
export function ScoreRing({ score }: ScoreRingProps) {
  const color =
    score >= 80 ? "#f59e0b" : score >= 65 ? "#10b981" : score >= 50 ? "#3b82f6" : "#ef4444";
  const grade = score >= 80 ? "A+" : score >= 65 ? "A" : score >= 50 ? "B" : "C";

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        width: 60,
        height: 60,
        borderRadius: "50%",
        border: `3px solid ${color}`,
        boxShadow: `0 0 16px ${color}30`,
        position: "relative",
        flexShrink: 0,
      }}
    >
      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "1rem", fontWeight: 900, color }}>
        {score}
      </span>
      <span style={{ fontSize: "0.5rem", fontWeight: 800, color: "var(--text-muted)", letterSpacing: "0.08em" }}>
        {grade}
      </span>
    </div>
  );
}

// ─── BBPanelDetail ────────────────────────────────────────────────────────────
interface BBPanelDetailProps {
  bb: {
    upper?: number;
    middle?: number;
    lower?: number;
    bandwidth_pct?: number;
  };
  entryLow?: number;
}
export function BBPanelDetail({ bb, entryLow }: BBPanelDetailProps) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: "0.6rem", fontWeight: 700, color: "var(--text-muted)", marginBottom: 6, display: "flex", justifyContent: "space-between" }}>
        <span>Bollinger Bands (20,2)</span>
        {bb.bandwidth_pct != null && (
          <span style={{ color: bb.bandwidth_pct < 5 ? "#f59e0b" : "var(--text-muted)" }}>
            {bb.bandwidth_pct < 5 ? "🔴 SQUEEZE" : `BW ${bb.bandwidth_pct}%`}
          </span>
        )}
      </div>
      <BBPosition upper={bb.upper} middle={bb.middle} lower={bb.lower} close={entryLow} />
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4, fontSize: "0.55rem", fontFamily: "'JetBrains Mono', monospace", color: "var(--text-muted)" }}>
        <span>L: {formatPrice(bb.lower)}</span>
        <span>M: {formatPrice(bb.middle)}</span>
        <span>U: {formatPrice(bb.upper)}</span>
      </div>
    </div>
  );
}
