"use client";

import MainLayout from "@/components/layout/MainLayout";
import { KillzoneTimer } from "@/components/pro/KillzoneTimer";
import { PDZoneWidget } from "@/components/pro/PDZoneWidget";
import { LiquiditySweepPanel } from "@/components/pro/LiquiditySweepPanel";
import { OBStrengthPanel } from "@/components/pro/OBStrengthPanel";
import { PositionSizingCalculator } from "@/components/pro/PositionSizingCalculator";
import { ProChart } from "@/components/pro/ProChart";
import { FVGBreakerPanel } from "@/components/pro/FVGBreakerPanel";
import { SessionPairsWidget } from "@/components/pro/SessionPairsWidget";
import { useState } from "react";

type Tab = "killzone" | "pd-zones" | "sweep" | "ob-strength" | "fvg-breaker" | "position";

const TABS: { id: Tab; label: string; icon: string; desc: string; color: string }[] = [
  { id: "killzone",    label: "Killzone Timer",       icon: "🎯", desc: "ICT session tracker",                    color: "#10b981" },
  { id: "pd-zones",   label: "P/D Zones",             icon: "📊", desc: "Premium & Discount arrays",              color: "#3b82f6" },
  { id: "sweep",      label: "Liquidity Sweep",       icon: "🌊", desc: "Market maker sweep detector",            color: "#ef4444" },
  { id: "ob-strength",label: "OB Strength",           icon: "🧱", desc: "Order block quality scoring",            color: "#f59e0b" },
  { id: "fvg-breaker",label: "FVG + Breaker",         icon: "⬜", desc: "Fair Value Gap & Breaker Block (ICT)",  color: "#6366f1" },
  { id: "position",   label: "Position Sizing",       icon: "⚖️", desc: "Kelly criterion calculator",             color: "#a78bfa" },
];

export default function ProToolsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("killzone");
  const active = TABS.find(t => t.id === activeTab)!;

  return (
    <MainLayout>
      {/* ── Header ── */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 8 }}>
          <div style={{
            width: 42, height: 42, borderRadius: 12,
            background: "linear-gradient(135deg, #ef4444 0%, #f59e0b 100%)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: "1.2rem", boxShadow: "0 0 20px rgba(239,68,68,0.3)",
            border: "1px solid rgba(255,255,255,0.1)",
          }}>
            ⚡
          </div>
          <div>
            <h1 style={{
              fontFamily: "'Outfit', sans-serif", fontSize: "1.8rem", fontWeight: 900,
              letterSpacing: "-0.04em", margin: 0,
              background: "linear-gradient(135deg, #fff 30%, #94a3b8)",
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            }}>
              Pro Trading Tools
            </h1>
            <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", margin: 0, marginTop: 4 }}>
              <span style={{ color: "#ef4444", fontWeight: 700 }}>Sprint 1</span>
              {" "}·{" "}
              <span>Killzone · P/D Zones · Liquidity Sweep · OB Strength · FVG+Breaker · Position Sizing</span>
            </p>
          </div>
          {/* Guide shortcut */}
          <a href="/guide-pro" style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 7, padding: "8px 16px", borderRadius: 10, background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.3)", color: "#6366f1", fontSize: "0.75rem", fontWeight: 800, textDecoration: "none", whiteSpace: "nowrap", transition: "all 0.2s" }}>
            📚 Panduan Cara Pakai
          </a>
        </div>
      </div>

      {/* ── Tab Bar ── */}
      <div style={{
        display: "flex", gap: 6, padding: "6px", borderRadius: 14,
        background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)",
        marginBottom: 24, overflowX: "auto",
      }}>
        {TABS.map(tab => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: "flex", alignItems: "center", gap: 8, whiteSpace: "nowrap",
                padding: "10px 16px", borderRadius: 10, fontWeight: isActive ? 700 : 500,
                fontSize: "0.82rem", cursor: "pointer", border: "1px solid transparent",
                transition: "all 0.25s cubic-bezier(0.4,0,0.2,1)",
                background: isActive ? `${tab.color}15` : "transparent",
                borderColor: isActive ? `${tab.color}40` : "transparent",
                color: isActive ? tab.color : "var(--text-muted)",
                boxShadow: isActive ? `0 0 14px ${tab.color}15` : "none",
              }}
            >
              <span style={{ fontSize: "1rem" }}>{tab.icon}</span>
              <span>{tab.label}</span>
              {isActive && (
                <span style={{
                  width: 5, height: 5, borderRadius: "50%",
                  background: tab.color, boxShadow: `0 0 6px ${tab.color}`,
                }} />
              )}
            </button>
          );
        })}
      </div>

      {/* ── Active Tab Info Banner ── */}
      <div style={{
        display: "flex", alignItems: "center", gap: 10, padding: "10px 16px",
        borderRadius: 10, background: `${active.color}08`,
        border: `1px solid ${active.color}20`, marginBottom: 20,
      }}>
        <span style={{ fontSize: "1.1rem" }}>{active.icon}</span>
        <div>
          <div style={{ fontWeight: 700, fontSize: "0.82rem", color: active.color }}>{active.label}</div>
          <div style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>{active.desc}</div>
        </div>
      </div>

      {/* KILLZONE TAB */}
      {activeTab === "killzone" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Chart with session markers */}
          <ProChart mode="killzone" symbol="BTCUSDT" timeframe="1h" height={420} />

          {/* 2-col: Timer + Session Pairs */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1.4fr", gap: 20, alignItems: "start" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <KillzoneTimer />

              {/* Strategy info */}
              <div style={{ padding: 20, borderRadius: 14, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
                <div style={{ fontWeight: 800, fontSize: "0.85rem", marginBottom: 14 }}>🎯 ICT Killzone Strategy</div>
                {[
                  { session: "🌏 ASIA (00-07 UTC)",    rule: "Observe range. Mark Asia High (AH) & Low (AL) — these become liquidity targets." },
                  { session: "🇬🇧 LONDON (07-10 UTC)",  rule: "Sweeps Asia range (Judas Swing) then reverses to real direction." },
                  { session: "🗽 NY OPEN (12-15 UTC)", rule: "Most powerful. Confirms or reverses London. Best setup window." },
                  { session: "😴 DEAD ZONE (20-00)",   rule: "Low volume, unpredictable. No new entries." },
                ].map(({ session, rule }) => (
                  <div key={session} style={{ marginBottom: 10, padding: "9px 12px", borderRadius: 8, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)" }}>
                    <div style={{ fontSize: "0.7rem", fontWeight: 700, color: "#fff", marginBottom: 3 }}>{session}</div>
                    <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", lineHeight: 1.5 }}>{rule}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Session Pairs — live volume list */}
            <div style={{ padding: 20, borderRadius: 16, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
              <div style={{ fontWeight: 800, fontSize: "0.88rem", marginBottom: 14, display: "flex", alignItems: "center", gap: 8 }}>
                <span>📈 Active Pairs — Sesi Ini</span>
                <span style={{ fontSize: "0.6rem", padding: "2px 8px", borderRadius: 5, background: "rgba(16,185,129,0.12)", color: "#10b981", fontWeight: 700, border: "1px solid rgba(16,185,129,0.25)" }}>LIVE</span>
              </div>
              <SessionPairsWidget />
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════
          PD ZONES TAB
      ══════════════════════════════════════════════ */}
      {activeTab === "pd-zones" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Chart with PD zone overlays */}
          <ProChart mode="pd-zones" symbol="BTCUSDT" timeframe="1h" height={460} />

          <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 20 }}>
            <PDZoneWidget symbol="BTCUSDT" htf="1d" timeframe="1h" />

            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ padding: 24, borderRadius: 16, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
                <div style={{ fontWeight: 800, fontSize: "0.9rem", marginBottom: 16 }}>📖 Premium/Discount Theory (ICT)</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                  {[
                    { zone: "PREMIUM (>62%)", color: "#ef4444", rule: "SELL zone. Smart money distributes longs here. Only sell setups are valid.", icon: "🔴" },
                    { zone: "EQUILIBRIUM (38–62%)", color: "#f59e0b", rule: "WAIT zone. Market makers may push either direction. No clear institutional bias.", icon: "🟡" },
                    { zone: "DISCOUNT (<38%)", color: "#10b981", rule: "BUY zone. Smart money accumulates longs here. Only buy setups are valid.", icon: "🟢" },
                  ].map(({ zone, color, rule, icon }) => (
                    <div key={zone} style={{ padding: 14, borderRadius: 10, background: `${color}08`, border: `1px solid ${color}20` }}>
                      <div style={{ fontSize: "1.2rem", marginBottom: 6 }}>{icon}</div>
                      <div style={{ fontSize: "0.72rem", fontWeight: 700, color, marginBottom: 6 }}>{zone}</div>
                      <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", lineHeight: 1.5 }}>{rule}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ padding: 24, borderRadius: 16, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
                <div style={{ fontWeight: 800, fontSize: "0.9rem", marginBottom: 14 }}>★ OTE — Optimal Trade Entry</div>
                <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", lineHeight: 1.6, margin: 0 }}>
                  OTE (Optimal Trade Entry) adalah zona Fibonacci 0.62–0.79 dari swing terakhir.
                  Ini adalah zona di mana Smart Money paling sering entry dengan menggunakan
                  partial fill strategy. Price di OTE + dalam Discount zone = setup terbaik untuk BUY.
                  Price di OTE + dalam Premium zone = setup terbaik untuk SELL.
                </p>
                <div style={{ marginTop: 12, padding: "10px 14px", borderRadius: 8, background: "rgba(139,92,246,0.08)", border: "1px solid rgba(139,92,246,0.2)", fontSize: "0.72rem", color: "#a78bfa", fontWeight: 600 }}>
                  💡 Rule: BUY di Discount OTE + Killzone + Liquidity Sweep = A+ setup
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════
          SWEEP TAB
      ══════════════════════════════════════════════ */}
      {activeTab === "sweep" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Chart with sweep markers */}
          <ProChart mode="sweep" symbol="BTCUSDT" timeframe="1h" height={460} />
          <LiquiditySweepPanel symbol="BTCUSDT" timeframe="1h" autoLoad={false} />
        </div>
      )}

      {/* ══════════════════════════════════════════════
          OB STRENGTH TAB
      ══════════════════════════════════════════════ */}
      {activeTab === "ob-strength" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Chart with OB markers */}
          <ProChart mode="ob-strength" symbol="BTCUSDT" timeframe="1h" height={460} />
          <OBStrengthPanel />
        </div>
      )}

      {/* ══════════════════════════════════════════════
          FVG + BREAKER BLOCK TAB
      ══════════════════════════════════════════════ */}
      {activeTab === "fvg-breaker" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* FVG panel */}
          <FVGBreakerPanel />

          {/* Theory explanation */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div style={{ padding: 20, borderRadius: 14, background: "rgba(99,102,241,0.05)", border: "1px solid rgba(99,102,241,0.15)" }}>
              <div style={{ fontWeight: 800, fontSize: "0.88rem", marginBottom: 12, color: "#6366f1" }}>⬜ Fair Value Gap (FVG)</div>
              <p style={{ fontSize: "0.74rem", color: "var(--text-muted)", lineHeight: 1.7, margin: 0 }}>
                FVG terbentuk saat <strong style={{ color: "#fff" }}>3 candle berurutan</strong> menciptakan gap antara
                high candle[i-1] dan low candle[i+1]. Gap ini adalah <em>ketidakseimbangan</em> — Smart Money meninggalkan
                area ini kosong. Price cenderung <strong style={{ color: "#6366f1" }}>kembali ke FVG</strong> sebelum melanjutkan.
              </p>
              <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 6 }}>
                {[
                  { label: "CE Level (50%)", desc: "Consequent Encroachment — titik 50% gap. Entry paling presisi untuk Smart Money.", color: "#f59e0b" },
                  { label: "IFVG (Inversion)", desc: "FVG yang ditembus price sepenuhnya — berbalik peran jadi zone berlawanan.", color: "#a78bfa" },
                  { label: "Institutional FVG", desc: "Gap > 1.5x ATR — imbalance besar dari order institusi, magnet paling kuat.", color: "#6366f1" },
                ].map(({ label, desc, color }) => (
                  <div key={label} style={{ padding: "8px 10px", borderRadius: 8, background: `${color}08`, border: `1px solid ${color}20` }}>
                    <div style={{ fontSize: "0.7rem", fontWeight: 800, color, marginBottom: 2 }}>{label}</div>
                    <div style={{ fontSize: "0.63rem", color: "var(--text-muted)", lineHeight: 1.5 }}>{desc}</div>
                  </div>
                ))}
              </div>
            </div>
            <div style={{ padding: 20, borderRadius: 14, background: "rgba(245,158,11,0.05)", border: "1px solid rgba(245,158,11,0.15)" }}>
              <div style={{ fontWeight: 800, fontSize: "0.88rem", marginBottom: 12, color: "#f59e0b" }}>🧱 Breaker Block</div>
              <p style={{ fontSize: "0.74rem", color: "var(--text-muted)", lineHeight: 1.7, margin: 0 }}>
                Breaker adalah <strong style={{ color: "#fff" }}>Order Block yang gagal</strong> — saat OB ditembus dengan momentum
                kuat, area tersebut berbalik fungsi. Bullish OB yang dibreak ke bawah → <strong style={{ color: "#ef4444" }}>Bearish Breaker</strong>.
                Bearish OB yang dibreak ke atas → <strong style={{ color: "#10b981" }}>Bullish Breaker</strong>.
              </p>
              <div style={{ marginTop: 12, padding: "10px 14px", borderRadius: 8, background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.2)", fontSize: "0.72rem", color: "#f59e0b" }}>
                💡 ICT Rule: Pullback ke Breaker setelah breakout = <strong>entry searah breakout</strong>. Setup dengan RR tertinggi (sering 1:5+)
              </div>
              <div style={{ marginTop: 10, padding: "10px 14px", borderRadius: 8, background: "rgba(16,185,129,0.06)", border: "1px solid rgba(16,185,129,0.15)", fontSize: "0.7rem", color: "#10b981" }}>
                🏆 A+ Setup: Bullish FVG + Bullish Breaker + Discount Zone + London Killzone = Full ICT confluence
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════
          POSITION SIZING TAB
      ══════════════════════════════════════════════ */}
      {activeTab === "position" && (
        <div>
          <PositionSizingCalculator />

          {/* Educational */}
          <div style={{ marginTop: 20, padding: 24, borderRadius: 16, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
            <div style={{ fontWeight: 800, fontSize: "0.9rem", marginBottom: 14 }}>📚 Kelly Criterion & Risk of Ruin</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
              {[
                {
                  title: "Full Kelly",
                  formula: "f* = (b·p − q) / b",
                  desc: "Theoretical optimal bet fraction. Never use in practice — too volatile.",
                  color: "#ef4444",
                },
                {
                  title: "Quarter Kelly (Recommended)",
                  formula: "f*/4",
                  desc: "Use 25% of Kelly fraction. Reduces drawdown while keeping most of edge.",
                  color: "#10b981",
                },
                {
                  title: "Risk of Ruin",
                  formula: "R = ((1−p)/p)^(1/f)",
                  desc: "Probability of losing entire account. Keep below 5% for sustainable trading.",
                  color: "#3b82f6",
                },
              ].map(({ title, formula, desc, color }) => (
                <div key={title} style={{ padding: 16, borderRadius: 10, background: `${color}08`, border: `1px solid ${color}20` }}>
                  <div style={{ fontSize: "0.72rem", fontWeight: 800, color, marginBottom: 6 }}>{title}</div>
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.72rem", color: "#fff", background: "rgba(0,0,0,0.2)", padding: "4px 8px", borderRadius: 4, marginBottom: 8 }}>{formula}</div>
                  <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", lineHeight: 1.5 }}>{desc}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </MainLayout>
  );
}
