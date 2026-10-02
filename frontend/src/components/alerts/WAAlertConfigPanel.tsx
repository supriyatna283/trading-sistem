"use client";

import { useState, useCallback } from "react";
import { API_URL } from "@/lib/utils";

/* ─── Types ── */
interface AlertConfig {
  phone: string;
  enabled: boolean;
  killzone_start: boolean;
  fvg_hit: boolean;
  sweep_confirmed: boolean;
  composite_score: boolean;
  volume_spike: boolean;
  daily_brief: boolean;
  min_score: number;
  min_grade: string;
  symbols: string[];
  only_killzone: boolean;
  cooldown_hours: number;
  max_per_hour: number;
}

type AlertType = "COMPOSITE_SCORE" | "FVG_HIT" | "SWEEP_CONFIRMED" | "KILLZONE_START" | "VOLUME_SPIKE" | "DAILY_BRIEF" | "TEST";

const ALERT_TYPES: { id: AlertType; label: string; icon: string; desc: string }[] = [
  { id: "TEST",            label: "Test Connection",    icon: "✅", desc: "Verify WA is connected" },
  { id: "COMPOSITE_SCORE", label: "ICT Setup (A/A+)",   icon: "🎯", desc: "Full ICT confluence alert" },
  { id: "FVG_HIT",         label: "FVG Hit",            icon: "⬜", desc: "Price enters Fair Value Gap" },
  { id: "SWEEP_CONFIRMED", label: "Liquidity Sweep",    icon: "🌊", desc: "Sweep + displacement confirmed" },
  { id: "KILLZONE_START",  label: "Killzone Start",     icon: "🗽", desc: "Session start reminder" },
  { id: "VOLUME_SPIKE",    label: "Volume Spike",       icon: "📊", desc: "Abnormal volume detected" },
  { id: "DAILY_BRIEF",     label: "Daily Brief",        icon: "🌅", desc: "Morning market summary" },
];

const DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "AVAXUSDT"];

const GRADES = ["A+", "A", "B", "C"];

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div
      onClick={() => onChange(!checked)}
      style={{
        width: 40, height: 22, borderRadius: 99, cursor: "pointer",
        background: checked ? "#10b981" : "rgba(255,255,255,0.08)",
        border: `1px solid ${checked ? "#10b981" : "rgba(255,255,255,0.12)"}`,
        position: "relative", transition: "all 0.2s", flexShrink: 0,
      }}
    >
      <div style={{
        position: "absolute", top: 2,
        left: checked ? 20 : 2,
        width: 16, height: 16, borderRadius: "50%",
        background: "#fff", transition: "left 0.2s",
        boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
      }} />
    </div>
  );
}

/* ─── Main Component ── */
export function WAAlertConfigPanel() {
  const [phone, setPhone] = useState("");
  const [config, setConfig] = useState<AlertConfig>({
    phone: "",
    enabled: true,
    killzone_start: true,
    fvg_hit: true,
    sweep_confirmed: true,
    composite_score: true,
    volume_spike: false,
    daily_brief: true,
    min_score: 70,
    min_grade: "A",
    symbols: ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    only_killzone: true,
    cooldown_hours: 4,
    max_per_hour: 3,
  });
  const [activeTab, setActiveTab] = useState<"config" | "test" | "preview">("config");
  const [preview, setPreview] = useState("");
  const [previewType, setPreviewType] = useState<AlertType>("COMPOSITE_SCORE");
  const [loading, setLoading] = useState(false);
  const [testStatus, setTestStatus] = useState<{ ok: boolean; message: string } | null>(null);
  const [saved, setSaved] = useState(false);
  const [symbolInput, setSymbolInput] = useState("");

  const set = useCallback(<K extends keyof AlertConfig>(key: K, val: AlertConfig[K]) => {
    setConfig(prev => ({ ...prev, [key]: val }));
  }, []);

  const handleSave = async () => {
    if (!phone) return;
    setLoading(true);
    try {
      const r = await fetch(`${API_URL}/api/v1/alerts/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...config, phone }),
      });
      const data = await r.json();
      if (data.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
      }
    } catch {}
    setLoading(false);
  };

  const handleTest = async () => {
    if (!phone) { setTestStatus({ ok: false, message: "Masukkan nomor HP terlebih dahulu" }); return; }
    setLoading(true);
    setTestStatus(null);
    try {
      const r = await fetch(`${API_URL}/api/v1/alerts/test?phone=${phone}`, { method: "POST" });
      const data = await r.json();
      setTestStatus({ ok: data.ok, message: data.ok ? "✅ Test berhasil! Cek WA kamu." : `❌ ${data.detail || "Gagal kirim"}` });
      if (data.preview) setPreview(data.preview);
    } catch (e: any) {
      setTestStatus({ ok: false, message: `Error: ${e.message}` });
    }
    setLoading(false);
  };

  const handlePreview = async (type: AlertType) => {
    setLoading(true);
    setPreviewType(type);
    try {
      const r = await fetch(`${API_URL}/api/v1/alerts/preview/${type}?symbol=BTCUSDT&score=85&grade=A%2B&entry=67000&sl=66500&tp1=68500&tp2=70000&rr=3.0`);
      const data = await r.json();
      if (data.preview) setPreview(data.preview);
    } catch {}
    setLoading(false);
  };

  const addSymbol = () => {
    const sym = symbolInput.toUpperCase().trim();
    if (sym && !config.symbols.includes(sym)) {
      set("symbols", [...config.symbols, sym.endsWith("USDT") ? sym : sym + "USDT"]);
    }
    setSymbolInput("");
  };

  const removeSymbol = (sym: string) => {
    set("symbols", config.symbols.filter(s => s !== sym));
  };

  const tabStyle = (tab: string) => ({
    padding: "8px 18px", borderRadius: 8, fontSize: "0.78rem", fontWeight: 700,
    cursor: "pointer",
    background: activeTab === tab ? "rgba(16,185,129,0.12)" : "transparent",
    border: `1px solid ${activeTab === tab ? "rgba(16,185,129,0.35)" : "rgba(255,255,255,0.06)"}`,
    color: activeTab === tab ? "#10b981" : "var(--text-muted)",
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* ── Header ── */}
      <div style={{ padding: "20px 24px", borderRadius: 16, background: "linear-gradient(135deg, rgba(16,185,129,0.08), rgba(6,78,59,0.12))", border: "1px solid rgba(16,185,129,0.2)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
          <div style={{ fontSize: "1.8rem" }}>📱</div>
          <div>
            <div style={{ fontWeight: 900, fontSize: "1.1rem", color: "#10b981" }}>WhatsApp Alert System</div>
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: 2 }}>
              ICT-aware alerts — hanya A/A+ setup, no spam, full entry plan
            </div>
          </div>
          <div style={{ marginLeft: "auto", padding: "4px 12px", borderRadius: 6, background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.25)", fontSize: "0.6rem", fontWeight: 800, color: "#10b981" }}>
            INOVATIF
          </div>
        </div>

        {/* Innovation badges */}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
          {["🎯 ICT Grade Filter", "⏱️ Anti-spam cooldown", "🗽 Killzone-aware", "💰 Entry plan otomatis", "5 tipe alert"].map(b => (
            <span key={b} style={{ fontSize: "0.6rem", padding: "2px 8px", borderRadius: 4, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "var(--text-muted)" }}>
              {b}
            </span>
          ))}
        </div>
      </div>

      {/* ── Phone Number ── */}
      <div style={{ padding: "18px 20px", borderRadius: 14, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
        <div style={{ fontWeight: 800, fontSize: "0.82rem", marginBottom: 12 }}>📞 Nomor WhatsApp</div>
        <div style={{ display: "flex", gap: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1 }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontFamily: "monospace" }}>62</span>
            <input
              value={phone}
              onChange={e => setPhone(e.target.value.replace(/\D/g, ""))}
              placeholder="8123456789 (tanpa +62 / 0)"
              style={{
                flex: 1, padding: "10px 14px", borderRadius: 8, fontSize: "0.82rem",
                background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)",
                color: "#fff", outline: "none", fontFamily: "monospace",
              }}
            />
          </div>
          <button onClick={handleTest} disabled={loading} style={{
            padding: "10px 18px", borderRadius: 8, fontSize: "0.76rem", fontWeight: 800,
            cursor: "pointer", background: "rgba(16,185,129,0.12)",
            border: "1px solid rgba(16,185,129,0.3)", color: "#10b981",
          }}>
            {loading ? "⟳" : "Test WA"}
          </button>
        </div>
        {testStatus && (
          <div style={{ marginTop: 10, padding: "8px 12px", borderRadius: 8, background: testStatus.ok ? "rgba(16,185,129,0.08)" : "rgba(239,68,68,0.08)", border: `1px solid ${testStatus.ok ? "rgba(16,185,129,0.2)" : "rgba(239,68,68,0.2)"}`, fontSize: "0.72rem", color: testStatus.ok ? "#10b981" : "#ef4444" }}>
            {testStatus.message}
          </div>
        )}
      </div>

      {/* ── Tabs ── */}
      <div style={{ display: "flex", gap: 8 }}>
        <button style={tabStyle("config")} onClick={() => setActiveTab("config")}>⚙️ Konfigurasi</button>
        <button style={tabStyle("preview")} onClick={() => setActiveTab("preview")}>👁️ Preview Pesan</button>
        <button style={tabStyle("test")} onClick={() => setActiveTab("test")}>🔬 Test Alert</button>
      </div>

      {/* ══ CONFIG TAB ══ */}
      {activeTab === "config" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

          {/* Alert Types */}
          <div style={{ padding: "18px 20px", borderRadius: 14, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
            <div style={{ fontWeight: 800, fontSize: "0.82rem", marginBottom: 14 }}>🔔 Jenis Alert</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {ALERT_TYPES.filter(t => t.id !== "TEST").map(at => {
                const key = at.id.toLowerCase() as keyof AlertConfig;
                const val = config[key] as boolean;
                return (
                  <div key={at.id} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <Toggle checked={val} onChange={v => set(key, v)} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: "0.78rem", fontWeight: 700 }}>{at.icon} {at.label}</div>
                      <div style={{ fontSize: "0.62rem", color: "var(--text-muted)" }}>{at.desc}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Quality Filters */}
          <div style={{ padding: "18px 20px", borderRadius: 14, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
            <div style={{ fontWeight: 800, fontSize: "0.82rem", marginBottom: 14 }}>🎯 Filter Kualitas Setup</div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              {/* Min Score */}
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: 6 }}>
                  Min ICT Score: <span style={{ color: "#fff", fontWeight: 800 }}>{config.min_score}/100</span>
                </div>
                <input type="range" min={0} max={100} step={5} value={config.min_score}
                  onChange={e => set("min_score", Number(e.target.value))}
                  style={{ width: "100%", accentColor: "#10b981" }}
                />
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.55rem", color: "var(--text-muted)" }}>
                  <span>0 (semua)</span><span>70 (rec)</span><span>100 (A+ only)</span>
                </div>
              </div>

              {/* Min Grade */}
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: 6 }}>Min Grade</div>
                <div style={{ display: "flex", gap: 6 }}>
                  {GRADES.map(g => (
                    <button key={g} onClick={() => set("min_grade", g)} style={{
                      flex: 1, padding: "7px 4px", borderRadius: 8, fontSize: "0.7rem", fontWeight: 800,
                      cursor: "pointer",
                      background: config.min_grade === g ? "rgba(99,102,241,0.15)" : "rgba(255,255,255,0.03)",
                      border: `1px solid ${config.min_grade === g ? "rgba(99,102,241,0.4)" : "rgba(255,255,255,0.06)"}`,
                      color: config.min_grade === g ? "#6366f1" : "var(--text-muted)",
                    }}>
                      {g}
                    </button>
                  ))}
                </div>
              </div>

              {/* Cooldown */}
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: 6 }}>
                  Cooldown per pair: <span style={{ color: "#fff", fontWeight: 800 }}>{config.cooldown_hours}h</span>
                </div>
                <input type="range" min={1} max={24} step={1} value={config.cooldown_hours}
                  onChange={e => set("cooldown_hours", Number(e.target.value))}
                  style={{ width: "100%", accentColor: "#f59e0b" }}
                />
              </div>

              {/* Max per hour */}
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: 6 }}>
                  Max alert/jam: <span style={{ color: "#fff", fontWeight: 800 }}>{config.max_per_hour}</span>
                </div>
                <input type="range" min={1} max={10} step={1} value={config.max_per_hour}
                  onChange={e => set("max_per_hour", Number(e.target.value))}
                  style={{ width: "100%", accentColor: "#3b82f6" }}
                />
              </div>
            </div>

            {/* Only killzone */}
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 14, padding: "10px 12px", borderRadius: 8, background: "rgba(16,185,129,0.04)", border: "1px solid rgba(16,185,129,0.12)" }}>
              <Toggle checked={config.only_killzone} onChange={v => set("only_killzone", v)} />
              <div>
                <div style={{ fontSize: "0.76rem", fontWeight: 700 }}>🎯 Hanya saat Killzone aktif</div>
                <div style={{ fontSize: "0.62rem", color: "var(--text-muted)" }}>Recommended — alert hanya London & NY Open, skip sesi sepi</div>
              </div>
            </div>
          </div>

          {/* Symbols */}
          <div style={{ padding: "18px 20px", borderRadius: 14, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
            <div style={{ fontWeight: 800, fontSize: "0.82rem", marginBottom: 12 }}>📌 Pair yang Dipantau</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
              {config.symbols.map(sym => (
                <div key={sym} style={{ display: "flex", alignItems: "center", gap: 5, padding: "4px 10px", borderRadius: 6, background: "rgba(59,130,246,0.1)", border: "1px solid rgba(59,130,246,0.25)", fontSize: "0.68rem", fontFamily: "monospace" }}>
                  {sym.replace("USDT","")}
                  <button onClick={() => removeSymbol(sym)} style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "0.7rem", padding: 0, lineHeight: 1 }}>×</button>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                value={symbolInput}
                onChange={e => setSymbolInput(e.target.value.toUpperCase())}
                onKeyDown={e => e.key === "Enter" && addSymbol()}
                placeholder="SOLUSDT atau SOL"
                style={{
                  flex: 1, padding: "8px 12px", borderRadius: 8, fontSize: "0.76rem",
                  background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)",
                  color: "#fff", outline: "none", fontFamily: "monospace",
                }}
              />
              <button onClick={addSymbol} style={{ padding: "8px 14px", borderRadius: 8, fontSize: "0.7rem", fontWeight: 700, cursor: "pointer", background: "rgba(59,130,246,0.1)", border: "1px solid rgba(59,130,246,0.25)", color: "#3b82f6" }}>
                + Add
              </button>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginTop: 8 }}>
              {DEFAULT_SYMBOLS.filter(s => !config.symbols.includes(s)).map(s => (
                <button key={s} onClick={() => set("symbols", [...config.symbols, s])} style={{ padding: "3px 8px", borderRadius: 4, fontSize: "0.6rem", cursor: "pointer", background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)", color: "var(--text-muted)" }}>
                  + {s.replace("USDT","")}
                </button>
              ))}
            </div>
          </div>

          {/* Save */}
          <button onClick={handleSave} disabled={!phone || loading} style={{
            padding: "14px", borderRadius: 12, fontSize: "0.88rem", fontWeight: 900,
            cursor: "pointer",
            background: saved ? "rgba(16,185,129,0.15)" : "linear-gradient(135deg, #10b981, #059669)",
            border: `1px solid ${saved ? "rgba(16,185,129,0.4)" : "transparent"}`,
            color: saved ? "#10b981" : "#fff",
            transition: "all 0.3s",
          }}>
            {saved ? "✓ Tersimpan!" : loading ? "Menyimpan..." : "💾 Simpan Konfigurasi"}
          </button>
        </div>
      )}

      {/* ══ PREVIEW TAB ══ */}
      {activeTab === "preview" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {ALERT_TYPES.map(at => (
              <button key={at.id} onClick={() => handlePreview(at.id)} style={{
                padding: "8px 14px", borderRadius: 8, fontSize: "0.7rem", fontWeight: 700, cursor: "pointer",
                background: previewType === at.id ? "rgba(99,102,241,0.12)" : "rgba(255,255,255,0.03)",
                border: `1px solid ${previewType === at.id ? "rgba(99,102,241,0.35)" : "rgba(255,255,255,0.07)"}`,
                color: previewType === at.id ? "#6366f1" : "var(--text-muted)",
              }}>
                {at.icon} {at.label}
              </button>
            ))}
          </div>

          {preview ? (
            <div style={{ padding: "18px 20px", borderRadius: 14, background: "rgba(37,211,102,0.04)", border: "1px solid rgba(37,211,102,0.15)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                <div style={{ width: 32, height: 32, borderRadius: "50%", background: "#25d366", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1rem" }}>📱</div>
                <div>
                  <div style={{ fontSize: "0.72rem", fontWeight: 800, color: "#25d366" }}>TradingSistem Bot</div>
                  <div style={{ fontSize: "0.58rem", color: "var(--text-muted)" }}>WhatsApp Message Preview</div>
                </div>
              </div>
              <div style={{
                padding: "14px 16px", borderRadius: "0 12px 12px 12px",
                background: "rgba(37,211,102,0.06)", border: "1px solid rgba(37,211,102,0.12)",
                fontFamily: "monospace", fontSize: "0.72rem", lineHeight: 1.8,
                color: "#e2e8f0", whiteSpace: "pre-wrap", wordBreak: "break-word",
              }}>
                {preview}
              </div>
            </div>
          ) : (
            <div style={{ padding: "40px", textAlign: "center", color: "var(--text-muted)", fontSize: "0.78rem" }}>
              Pilih jenis alert di atas untuk preview pesan WA
            </div>
          )}
        </div>
      )}

      {/* ══ TEST TAB ══ */}
      {activeTab === "test" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ padding: "16px 20px", borderRadius: 12, background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.2)", fontSize: "0.72rem", color: "var(--text-muted)", lineHeight: 1.6 }}>
            💡 <strong style={{ color: "#f59e0b" }}>Cara konfigurasi WA API:</strong><br/>
            Set environment variable di backend:<br/>
            <code style={{ fontFamily: "monospace", fontSize: "0.68rem", color: "#fff" }}>
              WA_PROVIDER=fonnte (atau wablas/twilio/waha)<br/>
              WA_API_KEY=your_token_here<br/>
              WA_FROM=no_pengirim (jika diperlukan)
            </code>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {ALERT_TYPES.map(at => (
              <div key={at.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", borderRadius: 10, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
                <span style={{ fontSize: "1.1rem" }}>{at.icon}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "0.76rem", fontWeight: 700 }}>{at.label}</div>
                  <div style={{ fontSize: "0.6rem", color: "var(--text-muted)" }}>{at.desc}</div>
                </div>
                <button
                  onClick={async () => {
                    if (!phone) { alert("Masukkan nomor HP dulu!"); return; }
                    setLoading(true);
                    try {
                      const r = await fetch(`${API_URL}/api/v1/alerts/send`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                          phone, alert_type: at.id, symbol: "BTCUSDT",
                          score: 85, grade: "A+",
                          entry: 67000, sl: 66500, tp1: 68500, tp2: 70000, rr: 3.0,
                        }),
                      });
                      const d = await r.json();
                      if (d.preview) setPreview(d.preview);
                      setActiveTab("preview");
                      setTestStatus({ ok: d.ok, message: d.ok ? `✅ ${at.label} terkirim!` : `❌ ${d.detail}` });
                    } catch {}
                    setLoading(false);
                  }}
                  disabled={loading}
                  style={{ padding: "7px 14px", borderRadius: 7, fontSize: "0.65rem", fontWeight: 700, cursor: "pointer", background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.25)", color: "#10b981" }}
                >
                  Kirim Test
                </button>
              </div>
            ))}
          </div>

          {testStatus && (
            <div style={{ padding: "10px 14px", borderRadius: 10, background: testStatus.ok ? "rgba(16,185,129,0.08)" : "rgba(239,68,68,0.08)", border: `1px solid ${testStatus.ok ? "rgba(16,185,129,0.2)" : "rgba(239,68,68,0.2)"}`, fontSize: "0.76rem", color: testStatus.ok ? "#10b981" : "#ef4444", fontWeight: 700 }}>
              {testStatus.message}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
