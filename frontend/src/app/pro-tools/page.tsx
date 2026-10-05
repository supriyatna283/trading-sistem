"use client";

import MainLayout from "@/components/layout/MainLayout";
import { KillzoneTimer } from "@/components/pro/KillzoneTimer";
import { PDZoneWidget } from "@/components/pro/PDZoneWidget";
import { LiquiditySweepPanel } from "@/components/pro/LiquiditySweepPanel";
import { OBStrengthPanel } from "@/components/pro/OBStrengthPanel";
import { PositionSizingCalculator } from "@/components/pro/PositionSizingCalculator";
import { FVGBreakerPanel } from "@/components/pro/FVGBreakerPanel";
import { SessionPairsWidget } from "@/components/pro/SessionPairsWidget";
import { ICTConfluenceDashboard } from "@/components/pro/ICTConfluenceDashboard";
import { MultiTimeframeView } from "@/components/pro/MultiTimeframeView";
import { useState, useCallback } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://ucilkecil387-trading-api.hf.space";

// ── Symbols ──────────────────────────────────────────────────────────────────
const SYMBOLS = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT","ADAUSDT","MATICUSDT"];
const TIMEFRAMES = ["5m","15m","1h","4h","1d"];
const HTF_MAP: Record<string, string> = { "5m":"15m","15m":"1h","1h":"4h","4h":"1d","1d":"1d" };

// ── Tabs ─────────────────────────────────────────────────────────────────────
type Tab = "confluence"|"mtf"|"killzone"|"pd-zones"|"sweep"|"ob-strength"|"fvg-breaker"|"position";

const TABS: { id: Tab; label: string; icon: string; desc: string; color: string; badge?: string }[] = [
  { id:"confluence",  label:"ICT Confluence", icon:"🧠", desc:"All signals in one view",           color:"#10b981", badge:"NEW" },
  { id:"mtf",         label:"Multi-TF",        icon:"📊", desc:"4H + 1H + 15M alignment",          color:"#3b82f6", badge:"NEW" },
  { id:"killzone",    label:"Killzone",        icon:"🎯", desc:"ICT session tracker",               color:"#f59e0b" },
  { id:"pd-zones",    label:"P/D Zones",       icon:"📈", desc:"Premium & Discount arrays",         color:"#6366f1" },
  { id:"sweep",       label:"Sweep",           icon:"🌊", desc:"Liquidity sweep detector",          color:"#ef4444" },
  { id:"ob-strength", label:"OB Strength",     icon:"🧱", desc:"Order block quality scoring",       color:"#f59e0b" },
  { id:"fvg-breaker", label:"FVG+Breaker",     icon:"⬜", desc:"Fair Value Gap & Breaker Block",    color:"#6366f1" },
  { id:"position",    label:"Position",        icon:"⚖️", desc:"Kelly criterion calculator",        color:"#a78bfa" },
];

// ── WA Alert Toast ────────────────────────────────────────────────────────────
function WAToast({ msg, onClose }: { msg: string; onClose: () => void }) {
  return (
    <div style={{ position:"fixed", bottom:24, right:24, zIndex:9999, padding:"14px 20px", borderRadius:14, background:"rgba(16,40,30,0.98)", border:"1px solid rgba(16,185,129,0.3)", boxShadow:"0 8px 32px rgba(0,0,0,0.5)", maxWidth:320, backdropFilter:"blur(12px)" }}>
      <div style={{ display:"flex", alignItems:"center", gap:10 }}>
        <span style={{ fontSize:"1.2rem" }}>📱</span>
        <div style={{ flex:1 }}>
          <div style={{ fontWeight:800, fontSize:"0.78rem", color:"#10b981", marginBottom:2 }}>WA Alert Sent!</div>
          <div style={{ fontSize:"0.62rem", color:"rgba(255,255,255,0.6)" }}>{msg}</div>
        </div>
        <button onClick={onClose} style={{ background:"none", border:"none", color:"rgba(255,255,255,0.4)", cursor:"pointer", fontSize:"1rem" }}>✕</button>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function ProToolsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("confluence");
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [timeframe, setTimeframe] = useState("1h");
  const [toast, setToast] = useState<string | null>(null);
  const [sendingWA, setSendingWA] = useState(false);

  const active = TABS.find(t => t.id === activeTab)!;
  const htf = HTF_MAP[timeframe] || "4h";

  const handleSetWAAlert = useCallback(async (data: any) => {
    setSendingWA(true);
    try {
      const msg = `🚨 *ICT Alert — ${data.symbol}*\n\n` +
        `📊 Grade: *${data.grade}* | Score: ${data.score}/100\n` +
        `📈 Bias: *${data.bias || data.signals?.join(", ")}*\n` +
        (data.entry ? `\n🎯 Entry: ${data.entry.entry?.toLocaleString("en", { maximumFractionDigits: 2 })}\n` +
          `🛑 SL: ${data.entry.stop_loss?.toLocaleString("en", { maximumFractionDigits: 2 })}\n` +
          `✅ TP1: ${data.entry.tp1?.toLocaleString("en", { maximumFractionDigits: 2 })}\n` +
          `✅ TP2: ${data.entry.tp2?.toLocaleString("en", { maximumFractionDigits: 2 })}\n` +
          `📐 R:R = 1:${data.entry.rr_tp2}` : "") +
        `\n\n_Sent from Pro Tools ICT Dashboard_`;

      const res = await fetch("/api/send-wa", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg }),
      });
      const json = await res.json();
      if (json.ok) {
        setToast(`Alert untuk ${data.symbol} (Grade ${data.grade}) berhasil dikirim!`);
        setTimeout(() => setToast(null), 5000);
      } else {
        setToast(`Gagal kirim: ${json.detail || "unknown error"}`);
        setTimeout(() => setToast(null), 5000);
      }
    } catch (e: any) {
      setToast(`Error: ${e.message}`);
      setTimeout(() => setToast(null), 4000);
    } finally {
      setSendingWA(false);
    }
  }, []);

  return (
    <MainLayout>
      {/* ── WA Toast ── */}
      {toast && <WAToast msg={toast} onClose={() => setToast(null)} />}

      {/* ── Header ── */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display:"flex", alignItems:"center", gap:14, marginBottom:16, flexWrap:"wrap" }}>
          <div style={{ width:42, height:42, borderRadius:12, background:"linear-gradient(135deg,#ef4444,#f59e0b)", display:"flex", alignItems:"center", justifyContent:"center", fontSize:"1.2rem", boxShadow:"0 0 20px rgba(239,68,68,0.3)", border:"1px solid rgba(255,255,255,0.1)" }}>
            ⚡
          </div>
          <div style={{ flex:1 }}>
            <h1 style={{ fontFamily:"'Outfit',sans-serif", fontSize:"1.6rem", fontWeight:900, letterSpacing:"-0.04em", margin:0, background:"linear-gradient(135deg,#fff 30%,#94a3b8)", WebkitBackgroundClip:"text", WebkitTextFillColor:"transparent" }}>
              Pro Trading Tools
            </h1>
            <p style={{ color:"var(--text-muted)", fontSize:"0.7rem", margin:0, marginTop:2 }}>
              <span style={{ color:"#ef4444", fontWeight:700 }}>ICT Framework</span>
              {" "}·{" "}
              <span>Confluence · MTF · FVG · OB · Sweep · P/D Zones · WA Alerts</span>
            </p>
          </div>
          <a href="/guide-pro" style={{ display:"flex", alignItems:"center", gap:6, padding:"8px 14px", borderRadius:10, background:"rgba(99,102,241,0.1)", border:"1px solid rgba(99,102,241,0.25)", color:"#6366f1", fontSize:"0.72rem", fontWeight:800, textDecoration:"none" }}>
            📚 Guide
          </a>
        </div>

        {/* ── GLOBAL SYMBOL + TF SELECTOR ── */}
        <div style={{ padding:"14px 18px", borderRadius:14, background:"rgba(255,255,255,0.03)", border:"1px solid rgba(255,255,255,0.08)", display:"flex", alignItems:"center", gap:12, flexWrap:"wrap" }}>
          <span style={{ fontSize:"0.7rem", fontWeight:700, color:"var(--text-muted)", whiteSpace:"nowrap" }}>🎯 Global Symbol:</span>

          {/* Symbol quick-pick */}
          <div style={{ display:"flex", gap:6, flexWrap:"wrap" }}>
            {SYMBOLS.map(s => (
              <button key={s} onClick={() => setSymbol(s)}
                style={{ padding:"5px 10px", borderRadius:7, fontSize:"0.68rem", fontWeight:symbol===s?900:500, cursor:"pointer", transition:"all .15s",
                  background: symbol===s ? "rgba(16,185,129,0.15)" : "rgba(255,255,255,0.04)",
                  border: symbol===s ? "1px solid rgba(16,185,129,0.4)" : "1px solid rgba(255,255,255,0.08)",
                  color: symbol===s ? "#10b981" : "var(--text-muted)",
                }}>
                {s.replace("USDT","")}
              </button>
            ))}
            <input value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())} placeholder="OTHER..."
              style={{ width:90, padding:"5px 10px", borderRadius:7, background:"rgba(255,255,255,0.05)", border:"1px solid rgba(255,255,255,0.1)", color:"#fff", fontSize:"0.68rem", fontFamily:"monospace" }} />
          </div>

          <div style={{ width:1, height:28, background:"rgba(255,255,255,0.08)", margin:"0 4px" }} />

          {/* TF quick-pick */}
          <span style={{ fontSize:"0.7rem", fontWeight:700, color:"var(--text-muted)", whiteSpace:"nowrap" }}>📅 TF:</span>
          <div style={{ display:"flex", gap:5 }}>
            {TIMEFRAMES.map(t => (
              <button key={t} onClick={() => setTimeframe(t)}
                style={{ padding:"5px 10px", borderRadius:7, fontSize:"0.68rem", fontWeight:timeframe===t?900:500, cursor:"pointer", transition:"all .15s",
                  background: timeframe===t ? "rgba(59,130,246,0.15)" : "rgba(255,255,255,0.04)",
                  border: timeframe===t ? "1px solid rgba(59,130,246,0.4)" : "1px solid rgba(255,255,255,0.08)",
                  color: timeframe===t ? "#3b82f6" : "var(--text-muted)",
                }}>
                {t}
              </button>
            ))}
          </div>

          <div style={{ marginLeft:"auto", fontSize:"0.62rem", color:"rgba(16,185,129,0.7)", padding:"4px 10px", borderRadius:6, background:"rgba(16,185,129,0.06)", border:"1px solid rgba(16,185,129,0.15)" }}>
            HTF: <strong style={{ color:"#10b981" }}>{htf}</strong>
          </div>
        </div>
      </div>

      {/* ── Tab Bar ── */}
      <div style={{ display:"flex", gap:5, padding:"5px", borderRadius:14, background:"rgba(255,255,255,0.02)", border:"1px solid rgba(255,255,255,0.05)", marginBottom:22, overflowX:"auto" }}>
        {TABS.map(tab => {
          const isActive = activeTab === tab.id;
          return (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              style={{ display:"flex", alignItems:"center", gap:7, whiteSpace:"nowrap", padding:"9px 14px", borderRadius:10, fontWeight:isActive?800:500, fontSize:"0.78rem", cursor:"pointer", border:"1px solid transparent", transition:"all 0.2s",
                background: isActive ? `${tab.color}15` : "transparent",
                borderColor: isActive ? `${tab.color}40` : "transparent",
                color: isActive ? tab.color : "var(--text-muted)",
                boxShadow: isActive ? `0 0 14px ${tab.color}15` : "none",
                position: "relative",
              }}>
              <span style={{ fontSize:"0.95rem" }}>{tab.icon}</span>
              <span>{tab.label}</span>
              {tab.badge && (
                <span style={{ padding:"1px 5px", borderRadius:4, fontSize:"0.48rem", fontWeight:900, background:`${tab.color}25`, color:tab.color, border:`1px solid ${tab.color}50` }}>
                  {tab.badge}
                </span>
              )}
              {isActive && <span style={{ width:4, height:4, borderRadius:"50%", background:tab.color, boxShadow:`0 0 6px ${tab.color}` }} />}
            </button>
          );
        })}
      </div>

      {/* ── Active Tab Info ── */}
      <div style={{ display:"flex", alignItems:"center", gap:10, padding:"8px 14px", borderRadius:10, background:`${active.color}08`, border:`1px solid ${active.color}20`, marginBottom:20 }}>
        <span style={{ fontSize:"1rem" }}>{active.icon}</span>
        <div>
          <div style={{ fontWeight:700, fontSize:"0.8rem", color:active.color }}>{active.label}</div>
          <div style={{ fontSize:"0.62rem", color:"var(--text-muted)" }}>{active.desc} · {symbol} · {timeframe}</div>
        </div>
        {sendingWA && (
          <div style={{ marginLeft:"auto", fontSize:"0.65rem", color:"#10b981" }}>📱 Sending WA...</div>
        )}
      </div>

      {/* ══════════════════════════════════════════════
          CONFLUENCE TAB (NEW)
      ══════════════════════════════════════════════ */}
      {activeTab === "confluence" && (
        <ICTConfluenceDashboard
          symbol={symbol}
          timeframe={timeframe}
          htfTimeframe={htf}
          autoRefresh={true}
          refreshInterval={30}
          onSetWAAlert={handleSetWAAlert}
        />
      )}

      {/* ══════════════════════════════════════════════
          MULTI-TIMEFRAME TAB (NEW)
      ══════════════════════════════════════════════ */}
      {activeTab === "mtf" && (
        <MultiTimeframeView symbol={symbol} />
      )}

      {/* ══════════════════════════════════════════════
          KILLZONE TAB
      ══════════════════════════════════════════════ */}
      {activeTab === "killzone" && (
        <div style={{ display:"flex", flexDirection:"column", gap:20 }}>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1.4fr", gap:20, alignItems:"start" }}>
            <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
              <KillzoneTimer />
              <div style={{ padding:20, borderRadius:14, background:"rgba(255,255,255,0.02)", border:"1px solid var(--border)" }}>
                <div style={{ fontWeight:800, fontSize:"0.85rem", marginBottom:14 }}>🎯 ICT Killzone Rules</div>
                {[
                  { session:"🌏 ASIA (00-07 UTC)", rule:"Observe range. Mark Asia High (AH) & Low (AL) — these become liquidity targets." },
                  { session:"🇬🇧 LONDON (07-10 UTC)", rule:"Sweeps Asia range (Judas Swing) then reverses to real direction." },
                  { session:"🗽 NY OPEN (12-15 UTC)", rule:"Most powerful. Confirms or reverses London. Best setup window." },
                  { session:"😴 DEAD ZONE (20-00)", rule:"Low volume. No new entries." },
                ].map(({ session, rule }) => (
                  <div key={session} style={{ marginBottom:8, padding:"9px 12px", borderRadius:8, background:"rgba(255,255,255,0.02)", border:"1px solid rgba(255,255,255,0.05)" }}>
                    <div style={{ fontSize:"0.7rem", fontWeight:700, color:"#fff", marginBottom:2 }}>{session}</div>
                    <div style={{ fontSize:"0.62rem", color:"var(--text-muted)", lineHeight:1.5 }}>{rule}</div>
                  </div>
                ))}
              </div>
            </div>
            <div style={{ padding:20, borderRadius:16, background:"rgba(255,255,255,0.02)", border:"1px solid var(--border)" }}>
              <div style={{ fontWeight:800, fontSize:"0.88rem", marginBottom:14, display:"flex", alignItems:"center", gap:8 }}>
                <span>📈 Active Pairs — {symbol}</span>
                <span style={{ fontSize:"0.6rem", padding:"2px 8px", borderRadius:5, background:"rgba(16,185,129,0.12)", color:"#10b981", fontWeight:700, border:"1px solid rgba(16,185,129,0.25)" }}>LIVE</span>
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
        <div style={{ display:"flex", flexDirection:"column", gap:20 }}>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 2fr", gap:20 }}>
            <PDZoneWidget symbol={symbol} htf={htf} timeframe={timeframe} />
            <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
              <div style={{ padding:24, borderRadius:16, background:"rgba(255,255,255,0.02)", border:"1px solid var(--border)" }}>
                <div style={{ fontWeight:800, fontSize:"0.9rem", marginBottom:16 }}>📖 Premium/Discount Theory (ICT)</div>
                <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:12 }}>
                  {[
                    { zone:"PREMIUM (>62%)", color:"#ef4444", rule:"SELL zone. Smart money distributes here. Only short setups valid.", icon:"🔴" },
                    { zone:"EQUILIBRIUM (38–62%)", color:"#f59e0b", rule:"WAIT zone. Market makers push either direction. No clear bias.", icon:"🟡" },
                    { zone:"DISCOUNT (<38%)", color:"#10b981", rule:"BUY zone. Smart money accumulates here. Only long setups valid.", icon:"🟢" },
                  ].map(({ zone, color, rule, icon }) => (
                    <div key={zone} style={{ padding:14, borderRadius:10, background:`${color}08`, border:`1px solid ${color}20` }}>
                      <div style={{ fontSize:"1.1rem", marginBottom:6 }}>{icon}</div>
                      <div style={{ fontSize:"0.7rem", fontWeight:700, color, marginBottom:6 }}>{zone}</div>
                      <div style={{ fontSize:"0.62rem", color:"var(--text-muted)", lineHeight:1.5 }}>{rule}</div>
                    </div>
                  ))}
                </div>
              </div>
              <div style={{ padding:20, borderRadius:14, background:"rgba(99,102,241,0.05)", border:"1px solid rgba(99,102,241,0.15)" }}>
                <div style={{ fontWeight:800, fontSize:"0.85rem", marginBottom:8, color:"#a78bfa" }}>★ OTE — Optimal Trade Entry</div>
                <p style={{ fontSize:"0.72rem", color:"var(--text-muted)", lineHeight:1.7, margin:0 }}>
                  Fibonacci 0.62–0.79 dari swing terakhir. Zona entry Smart Money terbaik.
                  Price di OTE + Discount = A+ BUY. Price di OTE + Premium = A+ SELL.
                </p>
                <div style={{ marginTop:10, padding:"8px 12px", borderRadius:8, background:"rgba(139,92,246,0.08)", border:"1px solid rgba(139,92,246,0.2)", fontSize:"0.7rem", color:"#a78bfa", fontWeight:600 }}>
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
        <LiquiditySweepPanel symbol={symbol} timeframe={timeframe} autoLoad={true} />
      )}

      {/* ══════════════════════════════════════════════
          OB STRENGTH TAB
      ══════════════════════════════════════════════ */}
      {activeTab === "ob-strength" && (
        <OBStrengthPanel symbol={symbol} timeframe={timeframe} htfTimeframe={htf} autoLoad={true} onSetWAAlert={handleSetWAAlert} />
      )}

      {/* ══════════════════════════════════════════════
          FVG + BREAKER TAB
      ══════════════════════════════════════════════ */}
      {activeTab === "fvg-breaker" && (
        <div style={{ display:"flex", flexDirection:"column", gap:20 }}>
          <FVGBreakerPanel symbol={symbol} timeframe={timeframe} autoLoad={true} onSetWAAlert={handleSetWAAlert} />
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16 }}>
            <div style={{ padding:20, borderRadius:14, background:"rgba(99,102,241,0.05)", border:"1px solid rgba(99,102,241,0.15)" }}>
              <div style={{ fontWeight:800, fontSize:"0.85rem", marginBottom:10, color:"#6366f1" }}>⬜ Fair Value Gap (FVG)</div>
              <p style={{ fontSize:"0.72rem", color:"var(--text-muted)", lineHeight:1.7, margin:0 }}>
                Gap antara 3 candle berurutan = ketidakseimbangan. Price cenderung kembali ke FVG sebelum melanjutkan.
              </p>
              <div style={{ marginTop:10, display:"flex", flexDirection:"column", gap:5 }}>
                {[
                  { label:"CE Level (50%)", desc:"Consequent Encroachment — titik entry paling presisi.", color:"#f59e0b" },
                  { label:"IFVG (Inversion)", desc:"FVG yang ditembus → berbalik peran jadi zone berlawanan.", color:"#a78bfa" },
                  { label:"Institutional FVG", desc:"Gap >1.5x ATR — imbalance besar, magnet paling kuat.", color:"#6366f1" },
                ].map(({ label, desc, color }) => (
                  <div key={label} style={{ padding:"7px 10px", borderRadius:7, background:`${color}08`, border:`1px solid ${color}20` }}>
                    <div style={{ fontSize:"0.68rem", fontWeight:800, color, marginBottom:2 }}>{label}</div>
                    <div style={{ fontSize:"0.6rem", color:"var(--text-muted)" }}>{desc}</div>
                  </div>
                ))}
              </div>
            </div>
            <div style={{ padding:20, borderRadius:14, background:"rgba(245,158,11,0.05)", border:"1px solid rgba(245,158,11,0.15)" }}>
              <div style={{ fontWeight:800, fontSize:"0.85rem", marginBottom:10, color:"#f59e0b" }}>🧱 Breaker Block</div>
              <p style={{ fontSize:"0.72rem", color:"var(--text-muted)", lineHeight:1.7, margin:0 }}>
                Order Block yang gagal → berbalik fungsi. Bullish OB dibreak ke bawah = Bearish Breaker.
              </p>
              <div style={{ marginTop:10, padding:"8px 12px", borderRadius:8, background:"rgba(245,158,11,0.08)", border:"1px solid rgba(245,158,11,0.2)", fontSize:"0.7rem", color:"#f59e0b" }}>
                💡 Pullback ke Breaker setelah breakout = entry searah breakout. RR sering 1:5+
              </div>
              <div style={{ marginTop:8, padding:"8px 12px", borderRadius:8, background:"rgba(16,185,129,0.06)", border:"1px solid rgba(16,185,129,0.15)", fontSize:"0.68rem", color:"#10b981" }}>
                🏆 A+ Setup: Bullish FVG + Bullish Breaker + Discount Zone + London Killzone
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
          <div style={{ marginTop:20, padding:24, borderRadius:16, background:"rgba(255,255,255,0.02)", border:"1px solid var(--border)" }}>
            <div style={{ fontWeight:800, fontSize:"0.9rem", marginBottom:14 }}>📚 Kelly Criterion & Risk of Ruin</div>
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:16 }}>
              {[
                { title:"Full Kelly", formula:"f* = (b·p − q) / b", desc:"Theoretical optimal. Never use in practice — too volatile.", color:"#ef4444" },
                { title:"Quarter Kelly ✅", formula:"f*/4", desc:"Use 25% of Kelly fraction. Reduces drawdown while keeping edge.", color:"#10b981" },
                { title:"Risk of Ruin", formula:"R = ((1−p)/p)^(1/f)", desc:"Probability of losing entire account. Keep below 5%.", color:"#3b82f6" },
              ].map(({ title, formula, desc, color }) => (
                <div key={title} style={{ padding:16, borderRadius:10, background:`${color}08`, border:`1px solid ${color}20` }}>
                  <div style={{ fontSize:"0.72rem", fontWeight:800, color, marginBottom:6 }}>{title}</div>
                  <div style={{ fontFamily:"monospace", fontSize:"0.7rem", color:"#fff", background:"rgba(0,0,0,0.2)", padding:"4px 8px", borderRadius:4, marginBottom:8 }}>{formula}</div>
                  <div style={{ fontSize:"0.62rem", color:"var(--text-muted)", lineHeight:1.5 }}>{desc}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </MainLayout>
  );
}