"use client";
import { useState, useEffect, useCallback } from "react";
import MainLayout from "@/components/layout/MainLayout";
import { api } from "@/lib/api";

const BLOCK_CATEGORY_COLORS: Record<string, string> = {
  structure:  "#8b5cf6",
  smc:        "#f59e0b",
  volume:     "#06b6d4",
  indicator:  "#10b981",
};

const SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"];
const TIMEFRAMES = ["5m", "15m", "1h", "4h", "1d"];

const REC_COLORS: Record<string, string> = {
  STRONG_BUY: "#10b981", BUY: "#34d399",
  STRONG_SELL: "#ef4444", SELL: "#f87171",
  NEUTRAL: "#6b7280",
};

export default function StrategyPage() {
  const [availableBlocks, setAvailableBlocks] = useState<any[]>([]);
  const [strategies, setStrategies] = useState<any[]>([]);
  const [activeConfig, setActiveConfig] = useState<any>({
    name: "My Strategy", description: "", min_score: 5, blocks: []
  });
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [entryTf, setEntryTf] = useState("1h");
  const [evaluation, setEvaluation] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [tab, setTab] = useState<"builder" | "saved">("builder");

  const loadBlocks = useCallback(async () => {
    try {
      const res = await api.getStrategyBlocks();
      const blocks = res.blocks || [];
      setAvailableBlocks(blocks);
      // Init with all blocks enabled
      setActiveConfig((prev: any) => ({
        ...prev,
        blocks: blocks.map((b: any) => ({
          id: b.id, enabled: true, weight: 1, params: {},
        })),
      }));
    } catch (e) { console.error(e); }
  }, []);

  const loadStrategies = useCallback(async () => {
    try {
      const res = await api.getStrategies();
      setStrategies(res.strategies || []);
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => {
    loadBlocks();
    loadStrategies();
  }, [loadBlocks, loadStrategies]);

  const toggleBlock = (blockId: string) => {
    setActiveConfig((prev: any) => ({
      ...prev,
      blocks: prev.blocks.map((b: any) =>
        b.id === blockId ? { ...b, enabled: !b.enabled } : b
      ),
    }));
    setEvaluation(null);
  };

  const setBlockWeight = (blockId: string, weight: number) => {
    setActiveConfig((prev: any) => ({
      ...prev,
      blocks: prev.blocks.map((b: any) =>
        b.id === blockId ? { ...b, weight } : b
      ),
    }));
    setEvaluation(null);
  };

  const evaluate = async () => {
    setLoading(true);
    try {
      const res = await api.evaluateStrategy({ strategy: activeConfig, symbol, entry_tf: entryTf });
      setEvaluation(res.evaluation);
    } catch (e: any) { console.error(e); }
    finally { setLoading(false); }
  };

  const saveStrategy = async () => {
    setSaving(true);
    try {
      await api.saveStrategy(activeConfig);
      await loadStrategies();
      setTab("saved");
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  const loadStrategy = (s: any) => {
    setActiveConfig({ name: s.name, description: s.description, min_score: s.min_score, blocks: s.blocks });
    setTab("builder");
  };

  const deleteStrategy = async (id: number) => {
    try { await api.deleteStrategy(id); await loadStrategies(); } catch (e) { console.error(e); }
  };

  const activeBlockIds = new Set(activeConfig.blocks.filter((b: any) => b.enabled).map((b: any) => b.id));
  const maxScore = activeConfig.blocks.filter((b: any) => b.enabled).reduce((s: number, b: any) => s + (b.weight || 1), 0);

  return (
    <MainLayout>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 800, margin: 0, letterSpacing: "-0.03em" }}>
            Custom Strategy Builder
          </h1>
          <p style={{ color: "var(--text-secondary)", margin: "4px 0 0", fontSize: "0.85rem" }}>
            Compose your strategy from indicator blocks and test it live
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {(["builder", "saved"] as const).map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              padding: "8px 18px", borderRadius: 10, cursor: "pointer", fontWeight: 600, fontSize: "0.83rem",
              border: `1px solid ${tab === t ? "var(--accent)" : "var(--border)"}`,
              background: tab === t ? "rgba(139,92,246,0.15)" : "transparent",
              color: tab === t ? "var(--accent)" : "var(--text-secondary)", transition: "all 0.2s",
            }}>
              {t === "builder" ? "🔧 Builder" : `📦 Saved (${strategies.length})`}
            </button>
          ))}
        </div>
      </div>

      {tab === "saved" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 14 }}>
          {strategies.map((s: any) => (
            <div key={s.id} style={{ background: "var(--card-bg)", border: "1px solid var(--border)", borderRadius: 14, padding: "18px 20px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: "0.95rem" }}>{s.name}</div>
                  {s.description && <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: 3 }}>{s.description}</div>}
                </div>
                {s.is_default && (
                  <span style={{ fontSize: "0.7rem", padding: "2px 8px", borderRadius: 6, background: "rgba(139,92,246,0.15)", color: "#a78bfa", fontWeight: 700 }}>
                    DEFAULT
                  </span>
                )}
              </div>
              <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: 14 }}>
                Min Score: <strong>{s.min_score}</strong> · Blocks: <strong>{s.blocks?.filter((b: any) => b.enabled !== false).length}</strong>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button onClick={() => loadStrategy(s)} className="btn-primary" style={{ flex: 1, padding: "8px 0", fontSize: "0.82rem" }}>
                  Load
                </button>
                {!s.is_default && (
                  <button onClick={() => deleteStrategy(s.id)} style={{
                    padding: "8px 14px", borderRadius: 8, border: "1px solid rgba(239,68,68,0.4)",
                    background: "rgba(239,68,68,0.1)", color: "#ef4444", cursor: "pointer", fontSize: "0.82rem",
                  }}>
                    🗑
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "builder" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: 20, alignItems: "start" }}>
          {/* Left: Blocks */}
          <div>
            {/* Strategy Name */}
            <div style={{ background: "var(--card-bg)", border: "1px solid var(--border)", borderRadius: 14, padding: "18px 20px", marginBottom: 16 }}>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                <div style={{ flex: 1, minWidth: 180 }}>
                  <label style={{ fontSize: "0.75rem", color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.06em", display: "block", marginBottom: 6 }}>Strategy Name</label>
                  <input value={activeConfig.name} onChange={e => setActiveConfig((p: any) => ({ ...p, name: e.target.value }))}
                    style={{ width: "100%", padding: "8px 12px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text-primary)", fontSize: "0.9rem", boxSizing: "border-box" }} />
                </div>
                <div>
                  <label style={{ fontSize: "0.75rem", color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.06em", display: "block", marginBottom: 6 }}>Min Score</label>
                  <input type="number" min={1} max={maxScore} value={activeConfig.min_score}
                    onChange={e => setActiveConfig((p: any) => ({ ...p, min_score: parseInt(e.target.value) }))}
                    style={{ width: 80, padding: "8px 12px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text-primary)", fontSize: "0.9rem" }} />
                </div>
              </div>
            </div>

            {/* Indicator Blocks */}
            <div style={{ background: "var(--card-bg)", border: "1px solid var(--border)", borderRadius: 14, padding: "18px 20px" }}>
              <div style={{ fontWeight: 700, marginBottom: 16 }}>
                Indicator Blocks <span style={{ color: "var(--text-secondary)", fontWeight: 400, fontSize: "0.83rem" }}>— toggle on/off, adjust weight</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {availableBlocks.map((block: any) => {
                  const cfg = activeConfig.blocks.find((b: any) => b.id === block.id) || { enabled: false, weight: 1 };
                  const catColor = BLOCK_CATEGORY_COLORS[block.category] || "#6b7280";
                  return (
                    <div key={block.id} style={{
                      border: `1px solid ${cfg.enabled ? catColor + "55" : "var(--border)"}`,
                      borderLeft: `4px solid ${cfg.enabled ? catColor : "var(--border)"}`,
                      borderRadius: 10, padding: "13px 15px", background: cfg.enabled ? catColor + "0a" : "transparent",
                      display: "flex", alignItems: "center", gap: 14, transition: "all 0.2s",
                    }}>
                      {/* Toggle */}
                      <div onClick={() => toggleBlock(block.id)} style={{
                        width: 40, height: 22, borderRadius: 11, cursor: "pointer", position: "relative", flexShrink: 0,
                        background: cfg.enabled ? catColor : "var(--border)", transition: "background 0.2s",
                      }}>
                        <div style={{
                          position: "absolute", top: 3, left: cfg.enabled ? 20 : 3, width: 16, height: 16,
                          borderRadius: "50%", background: "#fff", transition: "left 0.2s", boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
                        }} />
                      </div>
                      {/* Info */}
                      <div style={{ flex: 1, opacity: cfg.enabled ? 1 : 0.45 }}>
                        <div style={{ fontWeight: 600, fontSize: "0.88rem" }}>{block.name}</div>
                        <div style={{ fontSize: "0.76rem", color: "var(--text-secondary)", marginTop: 2 }}>{block.description}</div>
                      </div>
                      {/* Category */}
                      <span style={{ fontSize: "0.7rem", padding: "2px 8px", borderRadius: 6, background: catColor + "22", color: catColor, fontWeight: 700, whiteSpace: "nowrap" }}>
                        {block.category}
                      </span>
                      {/* Weight */}
                      <div style={{ display: "flex", alignItems: "center", gap: 6, opacity: cfg.enabled ? 1 : 0.3 }}>
                        <span style={{ fontSize: "0.72rem", color: "var(--text-secondary)" }}>Wt</span>
                        {[1, 2, 3].map(w => (
                          <button key={w} onClick={() => cfg.enabled && setBlockWeight(block.id, w)}
                            disabled={!cfg.enabled}
                            style={{
                              width: 24, height: 24, borderRadius: 6, border: `1px solid ${cfg.weight === w && cfg.enabled ? catColor : "var(--border)"}`,
                              background: cfg.weight === w && cfg.enabled ? catColor + "33" : "transparent",
                              color: cfg.weight === w && cfg.enabled ? catColor : "var(--text-secondary)",
                              cursor: cfg.enabled ? "pointer" : "default", fontSize: "0.75rem", fontWeight: 700,
                              display: "flex", alignItems: "center", justifyContent: "center", padding: 0,
                            }}>
                            {w}
                          </button>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Right: Test Panel */}
          <div style={{ position: "sticky", top: 20 }}>
            <div style={{ background: "var(--card-bg)", border: "1px solid var(--border)", borderRadius: 14, padding: "20px" }}>
              <div style={{ fontWeight: 700, marginBottom: 16 }}>🧪 Live Test</div>

              <div style={{ marginBottom: 12 }}>
                <label style={{ fontSize: "0.75rem", color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.06em", display: "block", marginBottom: 6 }}>Symbol</label>
                <select value={symbol} onChange={e => setSymbol(e.target.value)}
                  style={{ width: "100%", padding: "8px 12px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text-primary)", fontSize: "0.9rem" }}>
                  {SYMBOLS.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>

              <div style={{ marginBottom: 16 }}>
                <label style={{ fontSize: "0.75rem", color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.06em", display: "block", marginBottom: 6 }}>Entry Timeframe</label>
                <div style={{ display: "flex", gap: 6 }}>
                  {TIMEFRAMES.map(tf => (
                    <button key={tf} onClick={() => setEntryTf(tf)} style={{
                      flex: 1, padding: "7px 4px", borderRadius: 7, border: `1px solid ${entryTf === tf ? "var(--accent)" : "var(--border)"}`,
                      background: entryTf === tf ? "rgba(139,92,246,0.15)" : "transparent",
                      color: entryTf === tf ? "var(--accent)" : "var(--text-secondary)",
                      cursor: "pointer", fontWeight: 600, fontSize: "0.78rem", transition: "all 0.2s",
                    }}>
                      {tf}
                    </button>
                  ))}
                </div>
              </div>

              {/* Score Preview */}
              <div style={{ background: "var(--bg)", borderRadius: 10, padding: "12px 14px", marginBottom: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.82rem", color: "var(--text-secondary)", marginBottom: 6 }}>
                  <span>Active Blocks</span><span style={{ color: "var(--text-primary)", fontWeight: 700 }}>{activeBlockIds.size} / {availableBlocks.length}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.82rem", color: "var(--text-secondary)", marginBottom: 6 }}>
                  <span>Max Possible Score</span><span style={{ color: "var(--text-primary)", fontWeight: 700 }}>{maxScore}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                  <span>Minimum Required</span><span style={{ color: "var(--accent)", fontWeight: 700 }}>{activeConfig.min_score}</span>
                </div>
              </div>

              <button className="btn-primary" onClick={evaluate} disabled={loading}
                style={{ width: "100%", marginBottom: 10, opacity: loading ? 0.7 : 1, padding: "12px 0" }}>
                {loading ? "Evaluating…" : "▶ Run Evaluation"}
              </button>
              <button onClick={saveStrategy} disabled={saving} style={{
                width: "100%", padding: "11px 0", borderRadius: 10, border: "1px solid var(--border)",
                background: "transparent", color: "var(--text-secondary)", cursor: "pointer", fontWeight: 600, fontSize: "0.85rem",
                opacity: saving ? 0.7 : 1,
              }}>
                {saving ? "Saving…" : "💾 Save Strategy"}
              </button>
            </div>

            {/* Results */}
            {evaluation && (
              <div style={{ background: "var(--card-bg)", border: `1px solid ${REC_COLORS[evaluation.recommendation] || "var(--border)"}55`, borderRadius: 14, padding: "20px", marginTop: 14 }}>
                <div style={{ textAlign: "center", marginBottom: 16 }}>
                  <div style={{ fontSize: "2rem", fontWeight: 900, color: REC_COLORS[evaluation.recommendation] || "#6b7280" }}>
                    {evaluation.total_score}/{evaluation.max_score}
                  </div>
                  <div style={{ fontWeight: 700, fontSize: "1rem", color: REC_COLORS[evaluation.recommendation], marginTop: 4 }}>
                    {evaluation.recommendation.replace("_", " ")}
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: 4 }}>
                    {evaluation.passed ? "✅ Strategy conditions met" : "❌ Below minimum score"}
                  </div>
                </div>

                {/* Progress Bar */}
                <div style={{ height: 6, borderRadius: 3, background: "var(--border)", marginBottom: 16, overflow: "hidden" }}>
                  <div style={{
                    height: "100%", borderRadius: 3, transition: "width 0.5s ease",
                    width: `${evaluation.max_score > 0 ? (evaluation.total_score / evaluation.max_score) * 100 : 0}%`,
                    background: REC_COLORS[evaluation.recommendation] || "#6b7280",
                  }} />
                </div>

                {/* Block Results */}
                <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                  {evaluation.block_results?.map((b: any) => (
                    <div key={b.id} style={{ display: "flex", alignItems: "flex-start", gap: 10, fontSize: "0.8rem" }}>
                      <span style={{ flexShrink: 0, marginTop: 1 }}>{b.passed ? "✅" : "❌"}</span>
                      <div>
                        <div style={{ fontWeight: 600, color: b.passed ? "var(--text-primary)" : "var(--text-secondary)" }}>
                          {b.name} <span style={{ opacity: 0.6 }}>({b.score}/{b.weight})</span>
                        </div>
                        <div style={{ color: "var(--text-secondary)", fontSize: "0.74rem", marginTop: 1 }}>{b.reason}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </MainLayout>
  );
}
