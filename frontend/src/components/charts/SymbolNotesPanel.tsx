"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { api, SymbolNoteRecord } from "@/lib/api";

const BIAS_OPTIONS = [
  { value: "BULLISH",  label: "▲ Bullish",  color: "#22c55e", bg: "rgba(34,197,94,0.12)",   border: "rgba(34,197,94,0.35)"   },
  { value: "BEARISH",  label: "▼ Bearish",  color: "#ef4444", bg: "rgba(239,68,68,0.12)",   border: "rgba(239,68,68,0.35)"   },
  { value: "NEUTRAL",  label: "➡ Neutral",  color: "#94a3b8", bg: "rgba(148,163,184,0.08)", border: "rgba(148,163,184,0.25)" },
  { value: "WATCH",    label: "👁 Watch",    color: "#f59e0b", bg: "rgba(245,158,11,0.12)",  border: "rgba(245,158,11,0.35)"  },
  { value: "AVOID",    label: "✕ Avoid",    color: "#8b5cf6", bg: "rgba(139,92,246,0.12)",  border: "rgba(139,92,246,0.35)"  },
];

interface KeyLevel {
  label: string;
  price: number;
}

interface Props {
  symbol: string;
  onClose: () => void;
}

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

export default function SymbolNotesPanel({ symbol, onClose }: Props) {
  const [content, setContent] = useState("");
  const [bias, setBias] = useState("NEUTRAL");
  const [keyLevels, setKeyLevels] = useState<KeyLevel[]>([]);
  const [levelLabel, setLevelLabel] = useState("");
  const [levelPrice, setLevelPrice] = useState("");
  const [saving, setSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const saveRef = useRef(false);

  // Load note on symbol change
  useEffect(() => {
    setLoading(true);
    setError(null);
    api.getNote(symbol)
      .then(res => {
        const n: SymbolNoteRecord = res.note;
        setContent(n.content || "");
        setBias(n.bias || "NEUTRAL");
        setKeyLevels(n.key_levels || []);
        if (n.updated_at) setLastSaved(new Date(n.updated_at));
        else setLastSaved(null);
      })
      .catch(() => setError("Failed to load notes"))
      .finally(() => setLoading(false));
  }, [symbol]);

  // Auto-save with debounce (600ms)
  const debouncedContent = useDebounce(content, 600);
  const debouncedBias = useDebounce(bias, 600);
  const debouncedLevels = useDebounce(keyLevels, 600);

  const save = useCallback(async (c: string, b: string, kl: KeyLevel[]) => {
    if (saveRef.current) return;
    saveRef.current = true;
    setSaving(true);
    try {
      await api.upsertNote(symbol, { content: c, bias: b, key_levels: kl });
      setLastSaved(new Date());
      setError(null);
    } catch {
      setError("Save failed — will retry");
    } finally {
      setSaving(false);
      saveRef.current = false;
    }
  }, [symbol]);

  // Trigger auto-save whenever debounced values change (skip first load)
  const initialLoad = useRef(true);
  useEffect(() => {
    if (loading) return;
    if (initialLoad.current) { initialLoad.current = false; return; }
    save(debouncedContent, debouncedBias, debouncedLevels);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedContent, debouncedBias, debouncedLevels]);

  // Reset initialLoad ref when symbol changes
  useEffect(() => { initialLoad.current = true; }, [symbol]);

  const addLevel = () => {
    const price = parseFloat(levelPrice);
    if (!levelLabel.trim() || isNaN(price)) return;
    setKeyLevels(prev => [...prev, { label: levelLabel.trim(), price }]);
    setLevelLabel("");
    setLevelPrice("");
  };

  const removeLevel = (idx: number) => setKeyLevels(prev => prev.filter((_, i) => i !== idx));

  const handleExport = () => {
    const blob = new Blob([JSON.stringify({ symbol, content, bias, key_levels: keyLevels }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = `note-${symbol}.json`; a.click();
    URL.revokeObjectURL(url);
  };

  const biasOption = BIAS_OPTIONS.find(b => b.value === bias) ?? BIAS_OPTIONS[2];

  return (
    <div style={panelStyle}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: "0.65rem", fontWeight: 800, color: "var(--text-muted)", letterSpacing: "0.1em" }}>📝 NOTES</span>
          <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--text-secondary)" }}>{symbol.replace("USDT","")}/USDT</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {saving && <span style={{ fontSize: "0.62rem", color: "var(--text-muted)" }}>saving…</span>}
          {!saving && lastSaved && (
            <span style={{ fontSize: "0.6rem", color: "var(--text-muted)" }}>
              saved {lastSaved.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })}
            </span>
          )}
          <button onClick={handleExport} title="Export as JSON" style={iconBtnStyle}>⬇</button>
          <button onClick={onClose} style={iconBtnStyle}>✕</button>
        </div>
      </div>

      {error && (
        <div style={{ fontSize: "0.7rem", color: "#f87171", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 6, padding: "4px 10px", marginBottom: 8 }}>
          ⚠️ {error}
        </div>
      )}

      {loading ? (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ width: 20, height: 20, border: "2px solid var(--border)", borderTopColor: "var(--accent-blue)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
        </div>
      ) : (
        <>
          {/* Bias selector */}
          <div style={{ marginBottom: 10 }}>
            <div style={{ fontSize: "0.62rem", color: "var(--text-muted)", fontWeight: 700, marginBottom: 5, letterSpacing: "0.07em" }}>MARKET BIAS</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {BIAS_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  onClick={() => setBias(opt.value)}
                  style={{
                    padding: "4px 9px",
                    borderRadius: 6,
                    border: `1px solid ${bias === opt.value ? opt.border : "var(--border)"}`,
                    background: bias === opt.value ? opt.bg : "transparent",
                    color: bias === opt.value ? opt.color : "var(--text-muted)",
                    fontSize: "0.68rem",
                    fontWeight: 700,
                    cursor: "pointer",
                    transition: "all 0.15s",
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Active bias pill */}
          <div style={{
            display: "flex", alignItems: "center", gap: 6, marginBottom: 10,
            padding: "6px 10px", borderRadius: 8,
            background: biasOption.bg, border: `1px solid ${biasOption.border}`,
          }}>
            <span style={{ fontSize: "0.75rem", fontWeight: 800, color: biasOption.color }}>{biasOption.label}</span>
            <span style={{ fontSize: "0.62rem", color: "var(--text-muted)", marginLeft: "auto" }}>{symbol.replace("USDT","")}</span>
          </div>

          {/* Textarea */}
          <div style={{ marginBottom: 10 }}>
            <div style={{ fontSize: "0.62rem", color: "var(--text-muted)", fontWeight: 700, marginBottom: 5, letterSpacing: "0.07em" }}>ANALISIS</div>
            <textarea
              value={content}
              onChange={e => setContent(e.target.value)}
              placeholder={`Tulis analisis ${symbol.replace("USDT","")} di sini…\n\nContoh:\n- Harga sedang di dalam FVG daily\n- Tunggu retest OB 4H di 62,500\n- Target: 68,000 (ATH zone)`}
              style={{
                width: "100%",
                minHeight: 140,
                background: "rgba(255,255,255,0.03)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: "10px 12px",
                color: "var(--text-primary)",
                fontSize: "0.78rem",
                lineHeight: 1.6,
                resize: "vertical",
                outline: "none",
                fontFamily: "inherit",
                boxSizing: "border-box",
              }}
              onFocus={e => e.target.style.borderColor = "rgba(59,130,246,0.5)"}
              onBlur={e => e.target.style.borderColor = "var(--border)"}
            />
          </div>

          {/* Key levels */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: "0.62rem", color: "var(--text-muted)", fontWeight: 700, marginBottom: 6, letterSpacing: "0.07em" }}>KEY LEVELS</div>

            {/* Level list */}
            <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 6, maxHeight: 160, overflowY: "auto" }}>
              {keyLevels.length === 0 && (
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textAlign: "center", padding: "10px 0" }}>
                  Belum ada level — tambah di bawah
                </div>
              )}
              {keyLevels.map((kl, idx) => {
                const isSupport = kl.label.toUpperCase().includes("S") || kl.label.toUpperCase().includes("SUPPORT");
                const isResist  = kl.label.toUpperCase().includes("R") || kl.label.toUpperCase().includes("RESIST") || kl.label.toUpperCase().includes("TP");
                const clr = isSupport ? "#22c55e" : isResist ? "#ef4444" : "#93c5fd";
                return (
                  <div key={idx} style={{
                    display: "flex", alignItems: "center", gap: 6,
                    padding: "4px 8px", borderRadius: 6,
                    background: "rgba(255,255,255,0.03)", border: "1px solid var(--border)",
                  }}>
                    <span style={{ fontSize: "0.68rem", fontWeight: 700, color: clr, minWidth: 30 }}>{kl.label}</span>
                    <span style={{ fontSize: "0.72rem", fontFamily: "'JetBrains Mono', monospace", color: "var(--text-primary)", flex: 1, fontWeight: 700 }}>
                      {kl.price.toLocaleString("en-US", { maximumFractionDigits: 4 })}
                    </span>
                    <button
                      onClick={() => removeLevel(idx)}
                      style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "0.8rem", padding: "0 2px", lineHeight: 1 }}
                    >×</button>
                  </div>
                );
              })}
            </div>

            {/* Add level form */}
            <div style={{ display: "flex", gap: 4 }}>
              <input
                value={levelLabel}
                onChange={e => setLevelLabel(e.target.value)}
                placeholder="Label (R1, S1, OB…)"
                style={levelInputStyle}
                onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); addLevel(); } }}
              />
              <input
                value={levelPrice}
                onChange={e => setLevelPrice(e.target.value)}
                placeholder="Price"
                type="number"
                step="any"
                style={{ ...levelInputStyle, width: 90 }}
                onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); addLevel(); } }}
              />
              <button onClick={addLevel} style={addBtnStyle}>+</button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

const panelStyle: React.CSSProperties = {
  width: 276,
  flexShrink: 0,
  display: "flex",
  flexDirection: "column",
  padding: "14px 12px",
  overflow: "hidden",
  background: "var(--card-bg)",
  border: "1px solid var(--border)",
  borderRadius: 12,
};

const iconBtnStyle: React.CSSProperties = {
  background: "none",
  border: "1px solid var(--border)",
  color: "var(--text-muted)",
  borderRadius: 6,
  padding: "2px 7px",
  cursor: "pointer",
  fontSize: "0.8rem",
  lineHeight: 1.4,
  transition: "all 0.15s",
};

const levelInputStyle: React.CSSProperties = {
  flex: 1,
  background: "rgba(255,255,255,0.04)",
  border: "1px solid var(--border)",
  borderRadius: 6,
  padding: "4px 8px",
  color: "var(--text-primary)",
  fontSize: "0.72rem",
  outline: "none",
};

const addBtnStyle: React.CSSProperties = {
  background: "rgba(59,130,246,0.15)",
  border: "1px solid rgba(59,130,246,0.3)",
  borderRadius: 6,
  padding: "4px 10px",
  color: "var(--accent-blue)",
  cursor: "pointer",
  fontWeight: 700,
  fontSize: "0.85rem",
};
