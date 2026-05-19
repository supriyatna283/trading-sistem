"use client";

import MainLayout from "@/components/layout/MainLayout";
import TradingViewChart, { SetupOverlay } from "@/components/charts/TradingViewChart";
import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const MTF_TIMEFRAMES = [
  { tf: "1d", label: "1D" },
  { tf: "4h", label: "4H" },
  { tf: "1h", label: "1H" },
  { tf: "15m", label: "15m" },
];

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
  const pageRef = useRef<HTMLDivElement>(null);

  // ── Load Watchlist from localStorage ──
  useEffect(() => {
    try {
      const saved = localStorage.getItem("chart-watchlist");
      if (saved) {
        setWatchlist(JSON.parse(saved));
      } else {
        // Default minimalist watchlist if none saved
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
          // Fallback if API fails
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

  // ── MTF Grid: fetch all 4 timeframes in parallel at parent, pass as data prop ──
  const fetchMTFData = useCallback(async (sym: string) => {
    setIsMtfLoading(true);
    setMtfData({});
    try {
      const results = await Promise.all(
        MTF_TIMEFRAMES.map(({ tf }) =>
          fetch(`${API_URL}/api/v1/market/candles/${sym}?timeframe=${tf}&limit=200`)
            .then(r => r.json())
            .then(j => ({ tf, candles: j.candles ?? [] }))
            .catch(() => ({ tf, candles: [] }))
        )
      );
      const dataMap: Record<string, any[]> = {};
      results.forEach(({ tf, candles }) => { dataMap[tf] = candles; });
      setMtfData(dataMap);
    } catch (e) {
      console.error("MTF fetch error:", e);
    } finally {
      setIsMtfLoading(false);
    }
  }, []);

  // Fetch MTF data when grid activated or symbol changes
  useEffect(() => {
    if (isMTFGrid) fetchMTFData(selectedSymbol);
  }, [isMTFGrid, selectedSymbol, fetchMTFData]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchInput.trim()) {
      const formatted = searchInput.trim().toUpperCase();
      const finalSymbol = formatted.endsWith("USDT") ? formatted : `${formatted}USDT`;
      setSelectedSymbol(finalSymbol);
      setSelectedSetup(null);
      setSearchInput("");
    }
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

  return (
    <MainLayout>
      <div ref={pageRef} className="charts-page-root">

        {/* ── Top Header ── */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div>
            <h1 style={{ fontSize: "1.5rem", fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>Advanced Charts</h1>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "4px 0 0" }}>
              Real-time market analysis with Smart Money Concepts
            </p>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
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
            /* MTF 2×2 Grid — data fetched once at parent level */
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
                {MTF_TIMEFRAMES.map(({ tf }) => (
                  <div key={tf} style={{ position: "relative", minHeight: 280 }}>
                    <TradingViewChart
                      symbol={selectedSymbol}
                      data={mtfData[tf]}
                      setup={selectedSetup}
                      autoFetchSMC={false}
                      timeframeInterval={tf}
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
              <div style={{ fontSize: "0.85rem", fontWeight: 700, marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span>Active Setups</span>
                <span className="badge badge-score">{activeSetups.length} active</span>
              </div>

              {isLoading ? (
                <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <div className="animate-pulse-dot" style={{ width: 16, height: 16, borderRadius: "50%", background: "var(--accent-blue)" }} />
                </div>
              ) : activeSetups.length === 0 ? (
                <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: "0.85rem", textAlign: "center" }}>
                  No active setups currently.<br />Run scanner to find opportunities.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {activeSetups.map((setup: any, idx: number) => (
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
                        <span className={`badge ${setup.direction === "BUY" ? "badge-buy" : "badge-sell"}`}>{setup.direction}</span>
                      </div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", fontFamily: "'JetBrains Mono', monospace", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px" }}>
                        <div>Entry: <span style={{ color: "var(--text-primary)" }}>{formatPrice(setup.entry_low)} – {formatPrice(setup.entry_high)}</span></div>
                        <div>SL: <span style={{ color: "var(--accent-red)" }}>{formatPrice(setup.stop_loss)}</span></div>
                        <div>TP: <span style={{ color: "var(--accent-green)" }}>{formatPrice(setup.take_profit_1)}</span></div>
                        <div>R:R: <span style={{ color: "var(--accent-blue)" }}>1:{(setup.risk_reward ?? 0).toFixed(1)}</span></div>
                      </div>
                      <div style={{ marginTop: 8, fontSize: "0.7rem", color: "var(--text-muted)" }}>
                        {setup.setup_type} · TF: {setup.timeframe}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Responsive styles for charts layout */}
      <style dangerouslySetInnerHTML={{ __html: `
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
        /* Tablet: collapse watchlist, shrink sidebar */
        @media (max-width: 1100px) {
          .charts-grid-full {
            grid-template-columns: 160px 1fr 260px;
          }
          .charts-grid-no-watchlist {
            grid-template-columns: 1fr 260px;
          }
        }
        /* Mobile / small screen: stack vertically, hide sidebar panels */
        @media (max-width: 768px) {
          .charts-page-root {
            height: auto;
            min-height: calc(100vh - 80px);
          }
          .charts-grid-full,
          .charts-grid-no-watchlist {
            grid-template-columns: 1fr;
            grid-template-rows: auto;
          }
        }
      ` }} />
    </MainLayout>
  );
}

function formatPrice(val: number) {
  if (!val && val !== 0) return "-";
  return val > 10
    ? val.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : val.toFixed(4);
}
