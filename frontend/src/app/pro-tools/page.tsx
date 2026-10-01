"use client";

import MainLayout from "@/components/layout/MainLayout";
import { KillzoneTimer } from "@/components/pro/KillzoneTimer";
import { PDZoneWidget } from "@/components/pro/PDZoneWidget";
import { LiquiditySweepPanel } from "@/components/pro/LiquiditySweepPanel";
import { OBStrengthPanel } from "@/components/pro/OBStrengthPanel";
import { PositionSizingCalculator } from "@/components/pro/PositionSizingCalculator";
import { useState } from "react";

type Tab = "killzone" | "pd-zones" | "sweep" | "ob-strength" | "position";

const TABS: { id: Tab; label: string; icon: string; desc: string; color: string }[] = [
  { id: "killzone",   label: "Killzone Timer",      icon: "🎯", desc: "ICT session tracker",          color: "#10b981" },
  { id: "pd-zones",   label: "P/D Zones",           icon: "📊", desc: "Premium & Discount arrays",    color: "#3b82f6" },
  { id: "sweep",      label: "Liquidity Sweep",     icon: "🌊", desc: "Market maker sweep detector",  color: "#ef4444" },
  { id: "ob-strength",label: "OB Strength",         icon: "🧱", desc: "Order block quality scoring",  color: "#f59e0b" },
  { id: "position",   label: "Position Sizing",     icon: "⚖️", desc: "Kelly criterion calculator",   color: "#a78bfa" },
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
              <span>Killzone · P/D Zones · Liquidity Sweep · OB Strength · Position Sizing</span>
            </p>
          </div>
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

      {/* ── Tab Content ── */}
      {activeTab === "killzone" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          {/* Main killzone timer */}
          <div style={{ gridColumn: "1 / -1" }}>
            <KillzoneTimer />
          </div>

          {/* Educational info */}
          <div style={{ padding: 24, borderRadius: 16, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
            <div style={{ fontWeight: 800, fontSize: "0.9rem", marginBottom: 16 }}>🎯 ICT Killzone Strategy</div>
            {[
              { session: "🌏 ASIA (00-07 UTC)",    rule: "Observe range forming. Mark Asia High (AH) and Asia Low (AL). These are liquidity magnets." },
              { session: "🇬🇧 LONDON (07-10 UTC)",  rule: "High volume. Market often sweeps Asia High OR Low (JUDAS swing) before real move." },
              { session: "🗽 NY OPEN (12-15 UTC)", rule: "Most powerful killzone. Confirms or reverses London direction. Look for displacement after sweep." },
              { session: "😴 DEAD ZONE (21-00)",   rule: "Avoid trading. Low liquidity = unpredictable whipsaw. Rest & review setups." },
            ].map(({ session, rule }) => (
              <div key={session} style={{ marginBottom: 12, padding: "10px 12px", borderRadius: 8, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)" }}>
                <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "#fff", marginBottom: 3 }}>{session}</div>
                <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", lineHeight: 1.5 }}>{rule}</div>
              </div>
            ))}
          </div>

          <div style={{ padding: 24, borderRadius: 16, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
            <div style={{ fontWeight: 800, fontSize: "0.9rem", marginBottom: 16 }}>📋 Killzone Checklist</div>
            {[
              { check: "Wait for killzone to start",                  done: true },
              { check: "Mark Asia High and Asia Low",                 done: true },
              { check: "Identify HTF PD zone (buy in discount)",      done: false },
              { check: "Wait for liquidity sweep of equal high/low",  done: false },
              { check: "Confirm displacement candle after sweep",     done: false },
              { check: "Calculate position size (1% risk max)",       done: false },
              { check: "Enter at FVG or OB with OTE Fibonacci",      done: false },
            ].map(({ check, done }, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                <div style={{
                  width: 16, height: 16, borderRadius: 4, flexShrink: 0,
                  background: done ? "rgba(16,185,129,0.2)" : "rgba(255,255,255,0.04)",
                  border: `1px solid ${done ? "#10b981" : "rgba(255,255,255,0.08)"}`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: "0.6rem", color: "#10b981",
                }}>
                  {done ? "✓" : ""}
                </div>
                <span style={{ fontSize: "0.72rem", color: done ? "#10b981" : "var(--text-muted)" }}>{check}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === "pd-zones" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 20 }}>
          {/* PD Widget */}
          <PDZoneWidget symbol="BTCUSDT" htf="1d" timeframe="1h" />

          {/* Explanation */}
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
      )}

      {activeTab === "sweep" && (
        <LiquiditySweepPanel symbol="BTCUSDT" timeframe="1h" autoLoad={false} />
      )}

      {activeTab === "ob-strength" && (
        <OBStrengthPanel />
      )}

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
