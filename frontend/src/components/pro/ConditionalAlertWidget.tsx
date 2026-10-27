"use client";

import { useState, useEffect, useCallback } from "react";
import { API_URL, apiHeaders } from "@/lib/utils";

export function ConditionalAlertWidget({ symbol }: { symbol: string }) {
  const [phone, setPhone] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [watchedSymbols, setWatchedSymbols] = useState<string[]>([symbol]);
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const [settings, setSettings] = useState({
    killzone_start: true,
    fvg_hit: true,
    sweep_confirmed: true,
    composite_score: true,
    min_score: 70,
    min_grade: "A",
    only_killzone: true
  });

  const loadConfigForPhone = useCallback(async (targetPhone: string) => {
    const cleaned = targetPhone.trim();
    if (!cleaned || cleaned.length < 6) return;
    try {
      const res = await fetch(`${API_URL}/api/v1/alerts/config/${encodeURIComponent(cleaned)}`);
      if (!res.ok) return;
      const json = await res.json();
      if (json?.found && json?.config) {
        const cfg = json.config;
        setEnabled(Boolean(cfg.enabled ?? true));
        if (Array.isArray(cfg.symbols) && cfg.symbols.length > 0) {
          setWatchedSymbols(Array.from(new Set([...cfg.symbols, symbol])));
        }
        setSettings(s => ({
          ...s,
          killzone_start: Boolean(cfg.killzone_start ?? s.killzone_start),
          fvg_hit: Boolean(cfg.fvg_hit ?? s.fvg_hit),
          sweep_confirmed: Boolean(cfg.sweep_confirmed ?? s.sweep_confirmed),
          composite_score: Boolean(cfg.composite_score ?? s.composite_score),
          min_score: Number(cfg.min_score ?? s.min_score),
          min_grade: String(cfg.min_grade ?? s.min_grade),
          only_killzone: Boolean(cfg.only_killzone ?? s.only_killzone),
        }));
      }
    } catch {
      // Ignore network error on initial load
    }
  }, [symbol]);

  // Load from localStorage and fetch existing backend config on mount
  useEffect(() => {
    const savedPhone = localStorage.getItem("wa_alert_phone");
    const savedSyms = localStorage.getItem("wa_alert_symbols");
    if (savedSyms) {
      try {
        const parsed = JSON.parse(savedSyms);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setWatchedSymbols(Array.from(new Set([...parsed, symbol])));
        }
      } catch {}
    }
    if (savedPhone) {
      setPhone(savedPhone);
      loadConfigForPhone(savedPhone);
    }
  }, [loadConfigForPhone, symbol]);

  // Ensure current symbol is included in watchedSymbols when global symbol changes
  useEffect(() => {
    setWatchedSymbols(prev => prev.includes(symbol) ? prev : [...prev, symbol]);
  }, [symbol]);

  const toggleWatchedSymbol = (sym: string) => {
    setWatchedSymbols(prev =>
      prev.includes(sym)
        ? (prev.length > 1 ? prev.filter(s => s !== sym) : prev)
        : [...prev, sym]
    );
  };

  const handleSave = async () => {
    if (!phone) {
      setError("Please enter WhatsApp number");
      return;
    }
    setLoading(true);
    setError("");
    setSaved(false);

    try {
      const finalSymbols = watchedSymbols.length > 0 ? watchedSymbols : [symbol];
      localStorage.setItem("wa_alert_phone", phone);
      localStorage.setItem("wa_alert_symbols", JSON.stringify(finalSymbols));
      
      const payload = {
        phone,
        enabled,
        symbols: finalSymbols,
        ...settings
      };

      const res = await fetch(`${API_URL}/api/v1/alerts/config`, {
        method: "POST",
        headers: apiHeaders(),
        body: JSON.stringify(payload)
      });
      
      if (!res.ok) throw new Error("Failed to save alert settings");
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: 20, borderRadius: 16, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", marginBottom: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: "1.2rem" }}>🔔</span>
          <div>
            <div style={{ fontWeight: 800, fontSize: "0.9rem", color: "#fff" }}>Conditional WA Alerts</div>
            <div style={{ fontSize: "0.6rem", color: "var(--text-muted)" }}>Receive alerts when technical conditions are met</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <label style={{ fontSize: "0.7rem", color: "#fff", display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
            <input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />
            Enable Alerts
          </label>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ fontSize: "0.65rem", textTransform: "uppercase", color: "var(--text-muted)", fontWeight: 800 }}>Conditions (Triggers)</div>
          
          <label style={{ fontSize: "0.75rem", display: "flex", alignItems: "center", gap: 8, color: settings.fvg_hit ? "#10b981" : "var(--text-muted)", cursor: "pointer" }}>
            <input type="checkbox" checked={settings.fvg_hit} onChange={e => setSettings(s => ({ ...s, fvg_hit: e.target.checked }))} />
            Fresh FVG Hit (Pullback)
          </label>
          
          <label style={{ fontSize: "0.75rem", display: "flex", alignItems: "center", gap: 8, color: settings.sweep_confirmed ? "#10b981" : "var(--text-muted)", cursor: "pointer" }}>
            <input type="checkbox" checked={settings.sweep_confirmed} onChange={e => setSettings(s => ({ ...s, sweep_confirmed: e.target.checked }))} />
            Liquidity Sweep Confirmed
          </label>

          <label style={{ fontSize: "0.75rem", display: "flex", alignItems: "center", gap: 8, color: settings.killzone_start ? "#3b82f6" : "var(--text-muted)", cursor: "pointer" }}>
            <input type="checkbox" checked={settings.killzone_start} onChange={e => setSettings(s => ({ ...s, killzone_start: e.target.checked }))} />
            Killzone Session Start
          </label>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ fontSize: "0.65rem", textTransform: "uppercase", color: "var(--text-muted)", fontWeight: 800 }}>Filters (Quality)</div>
          
          <label style={{ fontSize: "0.75rem", display: "flex", alignItems: "center", gap: 8, color: settings.only_killzone ? "#f59e0b" : "var(--text-muted)", cursor: "pointer" }}>
            <input type="checkbox" checked={settings.only_killzone} onChange={e => setSettings(s => ({ ...s, only_killzone: e.target.checked }))} />
            Only during active Killzones
          </label>

          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <span style={{ fontSize: "0.75rem", color: "#fff" }}>Min Grade:</span>
            <select value={settings.min_grade} onChange={e => setSettings(s => ({ ...s, min_grade: e.target.value }))} style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", color: "#fff", padding: "4px 8px", borderRadius: 6, outline: "none", fontSize: "0.75rem" }}>
              <option value="A+">A+ Only</option>
              <option value="A">A and above</option>
              <option value="B">B and above</option>
            </select>
          </div>
          
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <span style={{ fontSize: "0.75rem", color: "#fff" }}>Min Score:</span>
            <input type="number" min="0" max="100" value={settings.min_score} onChange={e => setSettings(s => ({ ...s, min_score: parseInt(e.target.value) || 0 }))} style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", color: "#fff", padding: "4px 8px", borderRadius: 6, outline: "none", fontSize: "0.75rem", width: 60 }} />
          </div>
        </div>
      </div>

      <div style={{ marginBottom: 14 }}>
        <div style={{ fontSize: "0.62rem", textTransform: "uppercase", color: "var(--text-muted)", fontWeight: 800, marginBottom: 6 }}>
          Watched Pairs ({watchedSymbols.length})
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {Array.from(new Set(["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", symbol, ...watchedSymbols])).map(sym => {
            const active = watchedSymbols.includes(sym);
            return (
              <button
                key={sym}
                type="button"
                onClick={() => toggleWatchedSymbol(sym)}
                style={{
                  padding: "4px 10px",
                  borderRadius: 6,
                  fontSize: "0.68rem",
                  fontWeight: 700,
                  cursor: "pointer",
                  fontFamily: "monospace",
                  background: active ? "rgba(16,185,129,0.15)" : "rgba(255,255,255,0.03)",
                  border: `1px solid ${active ? "rgba(16,185,129,0.4)" : "rgba(255,255,255,0.08)"}`,
                  color: active ? "#10b981" : "var(--text-muted)",
                }}
              >
                {active ? "✓ " : "+ "}{sym}
              </button>
            );
          })}
        </div>
      </div>

      <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 20, paddingTop: 16, borderTop: "1px solid rgba(255,255,255,0.05)" }}>
        <input 
          type="text" 
          placeholder="WhatsApp Number (e.g. 62812...)" 
          value={phone} 
          onChange={e => setPhone(e.target.value)} 
          style={{ flex: 1, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.1)", padding: "10px 14px", borderRadius: 10, color: "#fff", outline: "none", fontSize: "0.8rem" }}
        />
        <button onClick={handleSave} disabled={loading} style={{ background: "rgba(16,185,129,0.15)", border: "1px solid rgba(16,185,129,0.3)", color: "#10b981", padding: "10px 20px", borderRadius: 10, fontWeight: 800, cursor: "pointer", transition: "all 0.2s" }}>
          {loading ? "Saving..." : saved ? "✅ Saved!" : "Save Settings"}
        </button>
      </div>
      {error && <div style={{ color: "#ef4444", fontSize: "0.7rem", marginTop: 8 }}>{error}</div>}
    </div>
  );
}
