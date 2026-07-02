"use client";

import MainLayout from "@/components/layout/MainLayout";
import TradingViewChart, { SetupOverlay } from "@/components/charts/TradingViewChart";
import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import { API_URL, debounce } from "@/lib/utils";

const MTF_TIMEFRAMES = [
  { tf: "1d", label: "1D" },
  { tf: "4h", label: "4H" },
  { tf: "1h", label: "1H" },
  { tf: "15m", label: "15m" },
];

// Toast notification
function Toast({ message, type, onClose }: { message: string; type: "error" | "success"; onClose: () => void }) {
  useEffect(() => {
    const t = setTimeout(onClose, 3500);
    return () => clearTimeout(t);
  }, [onClose]);

  return (
    <div style={{
      position: "fixed", bottom: 24, right: 24, zIndex: 9999,
      padding: "12px 20px", borderRadius: 12,
      background: type === "error" ? "rgba(239,68,68,0.15)" : "rgba(16,185,129,0.15)",
      border: `1px solid ${type === "error" ? "rgba(239,68,68,0.4)" : "rgba(16,185,129,0.4)"}`,
      color: type === "error" ? "#f87171" : "#10b981",
      fontSize: "0.85rem", fontWeight: 700, backdropFilter: "blur(8px)",
      display: "flex", alignItems: "center", gap: 10,
      animation: "slideUp 0.2s ease",
      boxShadow: "0 8px 32px rgba(0,0,0,0.3)",
    }}>
      {type === "error" ? "⚠️" : "✅"} {message}
      <button onClick={onClose} style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", fontSize: "1rem", padding: 0, marginLeft: 4 }}>✕</button>
    </div>
  );
}

export default function ChartsPage() {
  const [selectedSymbol, setSelectedSymbol] = useState("BTCUSDT");
  const [searchInput, setSearchInput] = useState("");
  const [allSymbols, setAllSymbols] = useState<string[]>([]);
  const [activeSetups, setActiveSetups] = useState<any[]>([]);
  const [selectedSetup, setSelectedSetup] = useState<SetupOverlay | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isMTFGrid, setIsMTFGrid] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showWatchlist, setShowWatchlist] = useState(true);
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [watchlistInput, setWatchlistInput] = useState("");
  const [mtfData, setMtfData] = useState<Record<string, any[]>>({});
  const [isMtfLoading, setIsMtfLoading] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "error" | "success" } | null>(null);
  const [setupDirFilter, setSetupDirFilter] = useState<"ALL" | "BUY" | "SELL">("ALL");
  const [setupTfFilter, setSetupTfFilter] = useState("ALL");
  const pageRef = useRef<HTMLDivElement>(null);
  const mtfAbortRef = useRef<AbortController | null>(null);

  // ── Load Watchlist from localStorage ──
  useEffect(() => {
    try {
      const saved = localStorage.getItem("chart-watchlist");
      if (saved) {
        setWatchlist(JSON.parse(saved));
      } else {
        setWatchlist(["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]);
      }
    } catch (_) {}
  }, []);

  const saveWatchlist = (list: string[]) => {
    setWatchlist(list);
    localStorage.setItem("chart-watchlist", JSON.stringify(list));
  };

  const addToWatchlist = (sym: string) => {
    const s = sym.trim().toUpperCase();
    if (!s || watchlist.includes(s)) return;
    const newList = [...watchlist, s.endsWith("USDT") ? s : `${s}USDT`];
    saveWatchlist(newList);
  };

  const removeFromWatchlist = (sym: string) => {
    saveWatchlist(watchlist.filter(s => s !== sym));
  };

  // ── Initialize Data ──
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [setupsRes, symbolsRes] = await Promise.all([
          api.getSetups("ACTIVE").catch(() => ({ setups: [] })),
          api.getSymbols().catch(() => ({ symbols: [] })),
        ]);

        const setupsArr = Array.isArray(setupsRes?.setups) ? setupsRes.setups : [];
        const symbolsArr = Array.isArray(symbolsRes?.symbols) ? symbolsRes.symbols : [];

        setActiveSetups(setupsArr);

        if (symbolsArr.length > 0) {
          setAllSymbols(symbolsArr.map((s: any) => s.symbol));
        } else {
          setAllSymbols(["BTCUSDT", "ETHUSDT"]);
        }
      } catch (err) {
        console.error("Error fetching charts data:", err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  // ── MTF Grid: fetch all 4 timeframes with abort support ──
  const fetchMTFData = useCallback(async (sym: string) => {
    // Cancel previous pending fetch
    if (mtfAbortRef.current) mtfAbortRef.current.abort();
    const controller = new AbortController();
    mtfAbortRef.current = controller;

    setIsMtfLoading(true);
    setMtfData({});
    try {
      const results = await Promise.all(
        MTF_TIMEFRAMES.map(({ tf }) =>
          fetch(`${API_URL}/api/v1/market/candles/${sym}?timeframe=${tf}&limit=200`, { signal: controller.signal })
            .then(r => r.json())
            .then(j => ({ tf, candles: j.candles ?? [] }))
            .catch(() => ({ tf, candles: [] }))
        )
      );
      const dataMap: Record<string, any[]> = {};
      results.forEach(({ tf, candles }) => { dataMap[tf] = candles; });
      setMtfData(dataMap);
    } catch (e: any) {
      if (e.name !== "AbortError") console.error("MTF fetch error:", e);
    } finally {
      setIsMtfLoading(false);
    }
  }, []);

  // Debounced MTF fetch (300ms)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const debouncedFetchMTF = useCallback(
    debounce((sym: string) => fetchMTFData(sym), 300),
    [fetchMTFData]
  );

  // Fetch MTF data when grid activated or symbol changes
  useEffect(() => {
    if (isMTFGrid) debouncedFetchMTF(selectedSymbol);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isMTFGrid, selectedSymbol]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchInput.trim()) {
      const formatted = searchInput.trim().toUpperCase();
      const finalSymbol = formatted.endsWith("USDT") ? formatted : `${formatted}USDT`;

      // Validate: check if symbol exists in allSymbols (if loaded)
      if (allSymbols.length > 0 && !allSymbols.includes(finalSymbol)) {
        setToast({ message: `Symbol "${finalSymbol}" not found in market list`, type: "error" });
      }

      setSelectedSymbol(finalSymbol);
      setSelectedSetup(null);
      setSearchInput("");
    }
  };

  // Manual refresh data (re-sets selectedSymbol to trigger chart rebuild)
  const handleRefresh = () => {
    const current = selectedSymbol;
    setSelectedSymbol("");
    setTimeout(() => setSelectedSymbol(current), 50);
    setToast({ message: "Chart data refreshed", type: "success" });
  };

  // ── Fullscreen ──
  const toggleFullscreen = useCallback(() => {
    if (!isFullscreen) {
      pageRef.current?.requestFullscreen?.();
    } else {
      document.exitFullscreen?.();
    }
  }, [isFullscreen]);

  useEffect(() => {
    const handler = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", handler);
    return () => document.removeEventListener("fullscreenchange", handler);
  }, []);

  // ── Unique timeframes from active setups (for filter) ──
  const setupTimeframes = ["ALL", ...Array.from(new Set(activeSetups.map(s => s.timeframe).filter(Boolean)))];

  const filteredSetups = activeSetups.filter(s => {
    if (setupDirFilter !== "ALL" && s.direction !== setupDirFilter) return false;
    if (setupTfFilter !== "ALL" && s.timeframe !== setupTfFilter) return false;
    return true;
  });

  return (
    <MainLayout>
      <div ref={pageRef} className="charts-page-root">

        {/* Toast */}
        {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

        {/* ── Top Header ── */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div>
            <h1 style={{ fontSize: "1.5rem", fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>Advanced Charts</h1>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "4px 0 0" }}>
              Real-time market analysis with Smart Money Concepts
            </p>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            {/* Search */}
            <form onSubmit={handleSearchSubmit} style={{ display: "flex", gap: 8 }}>
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search pair (e.g. ETH)..."
                list="symbol-list"
                style={{
                  background: "rgba(255,255,255,0.03)",
                  border: "1px solid var(--border)",
                  borderRadius: 10,
                  padding: "8px 14px",
                  color: "var(--text-primary)",
                  fontSize: "0.85rem",
                  outline: "none",
                  width: 200,
                }}
              />
              <datalist id="symbol-list">
                {allSymbols.map(s => <option key={s} value={s} />)}
              </datalist>
              <button type="submit" className="btn-primary" style={{ padding: "8px 16px", fontSize: "0.85rem" }}>Load</button>
            </form>

            {/* Refresh */}
            <button
              onClick={handleRefresh}
              title="Refresh chart data"
              style={{
                background: "rgba(255,255,255,0.03)",
                border: "1px solid var(--border)",
                borderRadius: 10, padding: "8px 12px",
                color: "var(--text-secondary)",
                fontSize: "1rem", cursor: "pointer", transition: "all 0.2s",
              }}
              onMouseEnter={e => (e.currentTarget.style.color = "#60a5fa")}
              onMouseLeave={e => (e.currentTarget.style.color = "var(--text-secondary)")}
            >
              ↺
            </button>

            {/* Watchlist toggle */}
            <button
              onClick={() => setShowWatchlist(v => !v)}
              title="Toggle Watchlist"
              style={{
                background: showWatchlist ? "rgba(59,130,246,0.15)" : "rgba(255,255,255,0.03)",
                border: `1px solid ${showWatchlist ? "rgba(59,130,246,0.4)" : "var(--border)"}`,
                borderRadius: 10, padding: "8px 12px",
                color: showWatchlist ? "var(--accent-blue)" : "var(--text-secondary)",
                fontSize: "1rem", cursor: "pointer", transition: "all 0.2s",
              }}
            >
              ★
            </button>

            {/* MTF Grid toggle */}
            <button
              onClick={() => setIsMTFGrid(!isMTFGrid)}
              style={{
                background: isMTFGrid
                  ? "linear-gradient(135deg, rgba(139,92,246,0.25), rgba(59,130,246,0.25))"
                  : "rgba(255,255,255,0.03)",
                border: `1px solid ${isMTFGrid ? "rgba(139,92,246,0.5)" : "var(--border)"}`,
                borderRadius: 10, padding: "8px 14px",
                color: isMTFGrid ? "#a78bfa" : "var(--text-secondary)",
                fontSize: "0.85rem", fontWeight: 700, cursor: "pointer",
                transition: "all 0.25s ease", whiteSpace: "nowrap",
                display: "flex", alignItems: "center", gap: 6,
              }}
            >
              <span style={{ fontSize: "1.1rem", lineHeight: 1 }}>⊞</span>
              4-Grid MTF
            </button>

            {/* Fullscreen */}
            <button
              onClick={toggleFullscreen}
              title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
              style={{
                background: isFullscreen ? "rgba(16,185,129,0.15)" : "rgba(255,255,255,0.03)",
                border: `1px solid ${isFullscreen ? "rgba(16,185,129,0.4)" : "var(--border)"}`,
                borderRadius: 10, padding: "8px 12px",
                color: isFullscreen ? "#10b981" : "var(--text-secondary)",
                fontSize: "0.9rem", cursor: "pointer", transition: "all 0.2s",
              }}
            >
              {isFullscreen ? "⊡" : "⛶"}
            </button>
          </div>
        </div>

        {/* ── Main content area ── */}
        <div className={`charts-main-grid ${
          isMTFGrid ? "charts-grid-mtf" :
          showWatchlist ? "charts-grid-full" : "charts-grid-no-watchlist"
        }`}>

          {/* ── Watchlist Sidebar (left, only in single mode) ── */}
          {!isMTFGrid && showWatchlist && (
            <div className="glass-card" style={{ padding: "16px", display: "flex", flexDirection: "column", gap: 8, overflowY: "auto" }}>
              <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4 }}>
                Watchlist
              </div>
              {watchlist.map(sym => (
                <div
                  key={sym}
                  onClick={() => { setSelectedSymbol(sym); setSelectedSetup(null); }}
                  style={{
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    padding: "8px 10px", borderRadius: 8, cursor: "pointer",
                    background: selectedSymbol === sym ? "rgba(59,130,246,0.12)" : "rgba(255,255,255,0.02)",
                    border: `1px solid ${selectedSymbol === sym ? "rgba(59,130,246,0.3)" : "transparent"}`,
                    transition: "all 0.15s",
                  }}
                >
                  <span style={{ fontSize: "0.82rem", fontWeight: 700, color: selectedSymbol === sym ? "var(--accent-blue)" : "var(--text-primary)" }}>
                    {sym.replace("USDT", "")}<span style={{ color: "var(--text-muted)", fontWeight: 400 }}>/USDT</span>
                  </span>
                  <button
                    onClick={(e) => { e.stopPropagation(); removeFromWatchlist(sym); }}
                    style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "0.75rem", padding: "0 2px", lineHeight: 1 }}
                  >×</button>
                </div>
              ))}
              {/* Add to watchlist */}
              <form
                onSubmit={(e) => { e.preventDefault(); addToWatchlist(watchlistInput); setWatchlistInput(""); }}
                style={{ display: "flex", gap: 4, marginTop: 4 }}
              >
                <input
                  value={watchlistInput}
                  onChange={e => setWatchlistInput(e.target.value)}
                  placeholder="Add symbol..."
                  style={{
                    flex: 1, background: "rgba(255,255,255,0.03)",
                    border: "1px solid var(--border)", borderRadius: 6,
                    padding: "4px 8px", color: "var(--text-primary)", fontSize: "0.78rem", outline: "none",
                  }}
                />
                <button type="submit" style={{
                  background: "rgba(59,130,246,0.15)", border: "1px solid rgba(59,130,246,0.3)",
                  borderRadius: 6, padding: "4px 8px", color: "var(--accent-blue)", cursor: "pointer", fontSize: "0.8rem",
                }}>+</button>
              </form>
            </div>
          )}

          {/* ── Chart Area ── */}
          {isMTFGrid ? (
            /* MTF 2×2 Grid */
            <div style={{ position: "relative", minHeight: 600 }}>
              {isMtfLoading && (
                <div style={{
                  position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
                  zIndex: 30, background: "rgba(10,14,23,0.7)", borderRadius: 12,
                }}>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
                    <div style={{ width: 28, height: 28, border: "2px solid var(--border)", borderTopColor: "var(--accent-blue)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
                    <span style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>Loading MTF data…</span>
                  </div>
                </div>
              )}
              <div style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gridTemplateRows: "1fr 1fr",
                gap: 8,
                height: "100%",
              }}>
                {MTF_TIMEFRAMES.map(({ tf, label }) => (
                  <div key={tf} style={{ position: "relative", minHeight: 280 }}>
                    {/* Prominent TF label overlay */}
                    <div style={{
                      position: "absolute", top: 38, left: 10, zIndex: 5,
                      pointerEvents: "none",
                      fontSize: "1.4rem", fontWeight: 900, opacity: 0.12,
                      color: "#fff", fontFamily: "'Inter', sans-serif",
                      letterSpacing: "-0.04em",
                    }}>
                      {label}
                    </div>
                    <TradingViewChart
                      symbol={selectedSymbol}
                      data={mtfData[tf]}
                      setup={selectedSetup}
                      autoFetchSMC={false}
                      timeframeInterval={tf}
                      compactToolbar
                    />
                  </div>
                ))}
              </div>
            </div>
          ) : (
            /* Single Chart */
            <div style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
              <div style={{ flex: 1, minHeight: 500 }}>
                <TradingViewChart symbol={selectedSymbol} setup={selectedSetup} autoFetchSMC={true} />
              </div>
            </div>
          )}

          {/* ── Right Sidebar: Active Setups (single mode only) ── */}
          {!isMTFGrid && (
            <div className="glass-card" style={{ padding: "20px", display: "flex", flexDirection: "column", overflowY: "auto" }}>
              <div style={{ fontSize: "0.85rem", fontWeight: 700, marginBottom: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span>Active Setups</span>
                <span className="badge badge-score">{activeSetups.length} active</span>
              </div>

              {/* Setup filters */}
              <div style={{ display: "flex", gap: 4, marginBottom: 12, flexWrap: "wrap" }}>
                {(["ALL", "BUY", "SELL"] as const).map(d => (
                  <button key={d} onClick={() => setSetupDirFilter(d)} style={{
                    padding: "3px 9px", borderRadius: 6, fontSize: "0.68rem", fontWeight: 700, cursor: "pointer",
                    border: setupDirFilter === d ? `1px solid ${d === "BUY" ? "#22c55e40" : d === "SELL" ? "#ef444440" : "rgba(255,255,255,0.2)"}` : "1px solid var(--border)",
                    background: setupDirFilter === d ? (d === "BUY" ? "rgba(34,197,94,0.1)" : d === "SELL" ? "rgba(239,68,68,0.1)" : "rgba(255,255,255,0.06)") : "transparent",
                    color: setupDirFilter === d ? (d === "BUY" ? "#22c55e" : d === "SELL" ? "#ef4444" : "#fff") : "var(--text-muted)",
                  }}>
                    {d === "BUY" ? "▲" : d === "SELL" ? "▼" : ""} {d}
                  </button>
                ))}
                {setupTimeframes.length > 2 && (
                  <select
                    value={setupTfFilter}
                    onChange={e => setSetupTfFilter(e.target.value)}
                    style={{ padding: "3px 8px", borderRadius: 6, fontSize: "0.68rem", background: "rgba(255,255,255,0.04)", border: "1px solid var(--border)", color: "var(--text-secondary)", outline: "none", cursor: "pointer" }}
                  >
                    {setupTimeframes.map(tf => <option key={tf} value={tf}>{tf}</option>)}
                  </select>
                )}
              </div>

              {isLoading ? (
                <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <div className="animate-pulse-dot" style={{ width: 16, height: 16, borderRadius: "50%", background: "var(--accent-blue)" }} />
                </div>
              ) : filteredSetups.length === 0 ? (
                <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: "0.85rem", textAlign: "center" }}>
                  No active setups currently.<br />Run scanner to find opportunities.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {filteredSetups.map((setup: any, idx: number) => (
                    <div
                      key={setup.id || idx}
                      style={{
                        background: selectedSymbol === setup.symbol ? "rgba(59,130,246,0.1)" : "rgba(255,255,255,0.02)",
                        border: `1px solid ${selectedSymbol === setup.symbol ? "var(--accent-blue)" : "var(--border)"}`,
                        borderRadius: 12, padding: "14px", cursor: "pointer", transition: "all 0.2s",
                      }}
                      onClick={() => {
                        setSelectedSymbol(setup.symbol);
                        setSelectedSetup({
                          direction: setup.direction,
                          entry_low: setup.entry_low,
                          entry_high: setup.entry_high,
                          stop_loss: setup.stop_loss,
                          take_profit_1: setup.take_profit_1,
                          take_profit_2: setup.take_profit_2,
                          take_profit_3: setup.take_profit_3,
                        });
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                        <span style={{ fontWeight: 700, fontSize: "0.9rem" }}>{setup.symbol}</span>
                        <div style={{ display: "flex", gap: 4 }}>
                          <span className={`badge ${setup.direction === "BUY" ? "badge-buy" : "badge-sell"}`}>{setup.direction}</span>
                          <span style={{ fontSize: "0.65rem", padding: "2px 6px", borderRadius: 4, background: "rgba(255,255,255,0.05)", color: "var(--text-muted)" }}>{setup.timeframe}</span>
                        </div>
                      </div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", fontFamily: "'JetBrains Mono', monospace", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px" }}>
                        <div>Entry: <span style={{ color: "var(--text-primary)" }}>{(setup.entry_low ?? 0).toLocaleString("en-US", { maximumFractionDigits: 2 })} – {(setup.entry_high ?? 0).toLocaleString("en-US", { maximumFractionDigits: 2 })}</span></div>
                        <div>SL: <span style={{ color: "var(--accent-red)" }}>{(setup.stop_loss ?? 0).toLocaleString("en-US", { maximumFractionDigits: 2 })}</span></div>
                        <div>TP: <span style={{ color: "var(--accent-green)" }}>{(setup.take_profit_1 ?? 0).toLocaleString("en-US", { maximumFractionDigits: 2 })}</span></div>
                        <div>R:R: <span style={{ color: "var(--accent-blue)" }}>1:{(setup.risk_reward ?? 0).toFixed(1)}</span></div>
                      </div>
                      <div style={{ marginTop: 8, fontSize: "0.7rem", color: "var(--text-muted)", display: "flex", justifyContent: "space-between" }}>
                        <span>{setup.setup_type}</span>
                        <span style={{ color: (setup.signal_score ?? setup.confluence_score ?? 0) >= 65 ? "#10b981" : "var(--text-muted)" }}>
                          Score: {setup.signal_score ?? setup.confluence_score ?? 0}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Responsive styles */}
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes slideUp { from { opacity: 0; transform: translate(-50%, -45%); } to { opacity: 1; transform: translate(-50%, -50%); } }
        .charts-page-root {
          display: flex;
          flex-direction: column;
          height: calc(100vh - 80px);
          gap: 0;
        }
        .charts-main-grid {
          display: grid;
          gap: 16px;
          flex: 1;
          min-height: 0;
        }
        .charts-grid-mtf {
          grid-template-columns: 1fr;
        }
        .charts-grid-full {
          grid-template-columns: 200px 1fr 320px;
        }
        .charts-grid-no-watchlist {
          grid-template-columns: 1fr 320px;
        }
        @media (max-width: 1100px) {
          .charts-grid-full { grid-template-columns: 160px 1fr 260px; }
          .charts-grid-no-watchlist { grid-template-columns: 1fr 260px; }
        }
        @media (max-width: 768px) {
          .charts-page-root { height: auto; min-height: calc(100vh - 80px); }
          .charts-grid-full,
          .charts-grid-no-watchlist { grid-template-columns: 1fr; grid-template-rows: auto; }
        }
      `}</style>
    </MainLayout>
  );
}
