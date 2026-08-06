"use client";

import MainLayout from "@/components/layout/MainLayout";
import TradingViewChart, { SetupOverlay } from "@/components/charts/TradingViewChart";
import AIAnalysisPanel from "@/components/charts/AIAnalysisPanel";
import { useState, useEffect, useCallback, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { API_URL, debounce } from "@/lib/utils";

const MTF_TIMEFRAMES = [
  { tf: "1d", label: "1D" },
  { tf: "4h", label: "4H" },
  { tf: "1h", label: "1H" },
  { tf: "15m", label: "15m" },
];

// Popular liquid pairs for quick access
const QUICK_PAIRS = [
  "BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT",
  "ADAUSDT","AVAXUSDT","LINKUSDT","DOTUSDT","HYPEUSDT","ARBUSDT",
  "OPUSDT","SUIUSDT","INJUSDT","APTUSDT","NEARUSDT","UNIUSDT",
];

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
      boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
    }}>
      {type === "error" ? "⚠️" : "✅"} {message}
      <button onClick={onClose} style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", fontSize: "1rem", padding: 0, marginLeft: 4 }}>✕</button>
    </div>
  );
}

import { Suspense } from "react";

function ChartsPageContent() {
  const searchParams = useSearchParams();
  const initSymbol = searchParams.get("symbol") || "BTCUSDT";
  const initTf = searchParams.get("tf") || "1h";
  const initAi = searchParams.get("ai") === "true";

  const [selectedSymbol, setSelectedSymbol] = useState(initSymbol);
  const [searchInput, setSearchInput] = useState("");
  const [allSymbols, setAllSymbols] = useState<string[]>([]);
  const [activeSetups, setActiveSetups] = useState<any[]>([]);
  const [selectedSetup, setSelectedSetup] = useState<SetupOverlay | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isMTFGrid, setIsMTFGrid] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showWatchlist, setShowWatchlist] = useState(true);
  const [showSetups, setShowSetups] = useState(true);
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [watchlistInput, setWatchlistInput] = useState("");
  const [mtfData, setMtfData] = useState<Record<string, any[]>>({});
  const [isMtfLoading, setIsMtfLoading] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "error" | "success" } | null>(null);
  const [setupDirFilter, setSetupDirFilter] = useState<"ALL" | "BUY" | "SELL">("ALL");
  const [setupTfFilter, setSetupTfFilter] = useState("ALL");
  const [refreshKey, setRefreshKey] = useState(0);
  const [showSearch, setShowSearch] = useState(false);
  const [activeTimeframe, setActiveTimeframe] = useState(initTf);
  const [showAIPanel, setShowAIPanel] = useState(initAi);
  const pageRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const mtfAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("chart-watchlist");
      if (saved) setWatchlist(JSON.parse(saved));
      else setWatchlist(["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]);
    } catch (_) {}
  }, []);

  const saveWatchlist = (list: string[]) => {
    setWatchlist(list);
    localStorage.setItem("chart-watchlist", JSON.stringify(list));
  };

  const addToWatchlist = (sym: string) => {
    const s = sym.trim().toUpperCase();
    if (!s || watchlist.includes(s)) return;
    saveWatchlist([...watchlist, s.endsWith("USDT") ? s : `${s}USDT`]);
  };

  const removeFromWatchlist = (sym: string) => saveWatchlist(watchlist.filter(s => s !== sym));

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [setupsRes, symbolsRes] = await Promise.all([
          api.getSetups("ACTIVE").catch(() => ({ setups: [] })),
          api.getSymbols().catch(() => ({ symbols: [] })),
        ]);
        setActiveSetups(Array.isArray(setupsRes?.setups) ? setupsRes.setups : []);
        const syms = Array.isArray(symbolsRes?.symbols) ? symbolsRes.symbols : [];
        setAllSymbols(syms.length > 0 ? syms.map((s: any) => s.symbol) : QUICK_PAIRS);
      } catch (err) {
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);


  const fetchMTFData = useCallback(async (sym: string) => {
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
      if (e.name !== "AbortError") console.error(e);
    } finally {
      setIsMtfLoading(false);
    }
  }, []);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const debouncedFetchMTF = useCallback(debounce((sym: string) => fetchMTFData(sym), 300), [fetchMTFData]);

  useEffect(() => {
    if (isMTFGrid) debouncedFetchMTF(selectedSymbol);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isMTFGrid, selectedSymbol]);

  // Keyboard shortcut: '/' to open search
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "/" && !["INPUT", "TEXTAREA"].includes((e.target as HTMLElement).tagName)) {
        e.preventDefault();
        setShowSearch(true);
        setTimeout(() => searchRef.current?.focus(), 50);
      }
      if (e.key === "Escape") setShowSearch(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchInput.trim()) {
      const formatted = searchInput.trim().toUpperCase();
      const finalSymbol = formatted.endsWith("USDT") ? formatted : `${formatted}USDT`;
      if (allSymbols.length > 0 && !allSymbols.includes(finalSymbol)) {
        setToast({ message: `"${finalSymbol}" not found in market list`, type: "error" });
      }
      setSelectedSymbol(finalSymbol);
      setSelectedSetup(null);
      setSearchInput("");
      setShowSearch(false);
    }
  };

  const handleRefresh = () => {
    setRefreshKey(k => k + 1);
    setToast({ message: "Chart refreshed", type: "success" });
  };

  const toggleFullscreen = useCallback(() => {
    if (!isFullscreen) pageRef.current?.requestFullscreen?.();
    else document.exitFullscreen?.();
  }, [isFullscreen]);

  useEffect(() => {
    const handler = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", handler);
    return () => document.removeEventListener("fullscreenchange", handler);
  }, []);

  const setupTimeframes = ["ALL", ...Array.from(new Set(activeSetups.map(s => s.timeframe).filter(Boolean)))];
  const filteredSetups = activeSetups.filter(s => {
    if (setupDirFilter !== "ALL" && s.direction !== setupDirFilter) return false;
    if (setupTfFilter !== "ALL" && s.timeframe !== setupTfFilter) return false;
    return true;
  });

  const selectSymbol = (sym: string) => {
    setSelectedSymbol(sym);
    setSelectedSetup(null);
  };

  // Sidebar widths
  const leftW = showWatchlist ? 180 : 0;
  const rightW = showSetups && !isMTFGrid ? 280 : 0;

  return (
    <MainLayout>
      <div ref={pageRef} id="charts-page-root">

        {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

        {/* ── Top Bar ── */}
        <div id="charts-topbar">
          {/* Left: Symbol + TF selector */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <button
              onClick={() => { setShowSearch(v => !v); setTimeout(() => searchRef.current?.focus(), 50); }}
              id="symbol-pill"
              title="Search symbol (press /)"
            >
              <span id="symbol-pill-name">{selectedSymbol.replace("USDT", "")}</span>
              <span id="symbol-pill-quote">/USDT</span>
              <span id="symbol-pill-caret">▾</span>
            </button>

            {/* TF selector */}
            <div style={{ display: "flex", gap: 3 }}>
              {["15m","1h","4h","1d"].map(tf => (
                <button
                  key={tf}
                  onClick={() => setActiveTimeframe(tf)}
                  className={`tf-btn${activeTimeframe === tf ? " tf-btn-active" : ""}`}
                >
                  {tf.toUpperCase()}
                </button>
              ))}
            </div>

            {/* MTF toggle */}
            <button
              onClick={() => setIsMTFGrid(!isMTFGrid)}
              className={`icon-btn${isMTFGrid ? " icon-btn-active-purple" : ""}`}
              title="Multi-Timeframe Grid"
            >
              <span style={{ fontSize: "0.75rem" }}>⊞</span> MTF
            </button>
          </div>

          {/* Right: actions */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            <button onClick={handleRefresh} className="icon-btn" title="Refresh">↺</button>
            <button
              onClick={() => setShowWatchlist(v => !v)}
              className={`icon-btn${showWatchlist ? " icon-btn-active" : ""}`}
              title="Watchlist"
            >
              ★
            </button>
            <button
              onClick={() => setShowSetups(v => !v)}
              className={`icon-btn${showSetups ? " icon-btn-active-green" : ""}`}
              title="Active Setups"
            >
              📋
            </button>
            <button
              onClick={toggleFullscreen}
              className={`icon-btn${isFullscreen ? " icon-btn-active-green" : ""}`}
              title="Fullscreen"
            >
              {isFullscreen ? "⊡" : "⛶"}
            </button>
            <button
              onClick={() => setShowAIPanel(v => !v)}
              className={`icon-btn${showAIPanel ? " icon-btn-active-purple" : ""}`}
              title="AI Analysis (auto-triggers on symbol/TF change)"
              id="ai-toggle-btn"
            >
              <span style={{ fontSize: "0.8rem" }}>🤖</span> AI
            </button>
          </div>
        </div>

        {/* ── Search Overlay ── */}
        {showSearch && (
          <div id="search-overlay" onClick={() => setShowSearch(false)}>
            <div id="search-box" onClick={e => e.stopPropagation()}>
              <form onSubmit={handleSearchSubmit} style={{ display: "flex", gap: 8 }}>
                <span style={{ color: "var(--text-muted)", fontSize: "1.1rem", alignSelf: "center" }}>🔍</span>
                <input
                  ref={searchRef}
                  type="text"
                  value={searchInput}
                  onChange={e => setSearchInput(e.target.value)}
                  placeholder="Search pair… (e.g. ETH, SOL, HYPE)"
                  list="symbol-list"
                  id="search-input"
                />
                <datalist id="symbol-list">
                  {allSymbols.map(s => <option key={s} value={s} />)}
                </datalist>
                <button type="submit" className="btn-primary" style={{ padding: "8px 18px", fontSize: "0.85rem" }}>Load</button>
              </form>
              {/* Quick pairs */}
              <div style={{ marginTop: 14 }}>
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 700, letterSpacing: "0.08em", marginBottom: 8 }}>QUICK ACCESS</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {QUICK_PAIRS.map(p => (
                    <button
                      key={p}
                      onClick={() => { selectSymbol(p); setShowSearch(false); }}
                      className={`quick-pair-btn${selectedSymbol === p ? " quick-pair-btn-active" : ""}`}
                    >
                      {p.replace("USDT", "")}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Main layout ── */}
        <div id="charts-body">

          {/* Watchlist sidebar */}
          {showWatchlist && !isMTFGrid && (
            <div id="watchlist-sidebar" className="glass-card">
              <div className="sidebar-title">WATCHLIST</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 2, flex: 1, overflowY: "auto" }}>
                {/* Quick pairs header */}
                <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", fontWeight: 600, marginBottom: 4, marginTop: 2 }}>MY LIST</div>
                {watchlist.map(sym => (
                  <div
                    key={sym}
                    onClick={() => selectSymbol(sym)}
                    className={`watchlist-item${selectedSymbol === sym ? " watchlist-item-active" : ""}`}
                  >
                    <div>
                      <span className="wl-base">{sym.replace("USDT", "")}</span>
                      <span className="wl-quote">/USDT</span>
                    </div>
                    <button
                      onClick={e => { e.stopPropagation(); removeFromWatchlist(sym); }}
                      className="wl-remove"
                    >×</button>
                  </div>
                ))}
                {/* Separator */}
                <div style={{ height: 1, background: "var(--border)", margin: "8px 0" }} />
                <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", fontWeight: 600, marginBottom: 4 }}>POPULAR</div>
                {QUICK_PAIRS.filter(p => !watchlist.includes(p)).slice(0, 10).map(sym => (
                  <div
                    key={sym}
                    onClick={() => selectSymbol(sym)}
                    className={`watchlist-item watchlist-item-muted${selectedSymbol === sym ? " watchlist-item-active" : ""}`}
                  >
                    <div>
                      <span className="wl-base">{sym.replace("USDT", "")}</span>
                      <span className="wl-quote">/USDT</span>
                    </div>
                    <button
                      onClick={e => { e.stopPropagation(); addToWatchlist(sym); }}
                      className="wl-add"
                      title="Add to watchlist"
                    >+</button>
                  </div>
                ))}
              </div>

              {/* Add custom */}
              <form
                onSubmit={e => { e.preventDefault(); addToWatchlist(watchlistInput); setWatchlistInput(""); }}
                style={{ display: "flex", gap: 4, marginTop: 8 }}
              >
                <input
                  value={watchlistInput}
                  onChange={e => setWatchlistInput(e.target.value)}
                  placeholder="Add symbol…"
                  className="wl-input"
                />
                <button type="submit" className="wl-add-btn">+</button>
              </form>
            </div>
          )}

          {/* Chart area */}
          <div id="chart-area">
            {isMTFGrid ? (
              <div style={{ position: "relative", height: "100%" }}>
                {isMtfLoading && (
                  <div style={{
                    position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
                    zIndex: 30, background: "rgba(10,14,23,0.7)", borderRadius: 12,
                  }}>
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
                      <div style={{ width: 28, height: 28, border: "2px solid var(--border)", borderTopColor: "var(--accent-blue)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
                      <span style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>Loading MTF…</span>
                    </div>
                  </div>
                )}
                <div id="mtf-grid">
                  {MTF_TIMEFRAMES.map(({ tf, label }) => (
                    <div key={`${tf}-${refreshKey}`} style={{ position: "relative", minHeight: 0 }}>
                      <div className="mtf-label">{label}</div>
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
              <TradingViewChart
                key={`${refreshKey}-${selectedSymbol}`}
                symbol={selectedSymbol}
                setup={selectedSetup}
                autoFetchSMC={true}
                timeframeInterval={activeTimeframe}
              />
            )}
          </div>

          {/* Right sidebar: Active Setups */}
          {showSetups && !isMTFGrid && (
            <div id="setups-sidebar" className="glass-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <div className="sidebar-title" style={{ marginBottom: 0 }}>ACTIVE SETUPS</div>
                <span className="badge badge-score" style={{ fontSize: "0.65rem" }}>
                  {filteredSetups.length}
                </span>
              </div>

              {/* Filters */}
              <div style={{ display: "flex", gap: 4, marginBottom: 10, flexWrap: "wrap" }}>
                {(["ALL", "BUY", "SELL"] as const).map(d => (
                  <button key={d} onClick={() => setSetupDirFilter(d)} className={`dir-filter-btn${setupDirFilter === d ? ` dir-filter-${d}` : ""}`}>
                    {d === "BUY" ? "▲ " : d === "SELL" ? "▼ " : ""}{d}
                  </button>
                ))}
                {setupTimeframes.length > 2 && (
                  <select
                    value={setupTfFilter}
                    onChange={e => setSetupTfFilter(e.target.value)}
                    className="tf-select"
                  >
                    {setupTimeframes.map(tf => <option key={tf} value={tf}>{tf}</option>)}
                  </select>
                )}
              </div>

              <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
                {isLoading ? (
                  <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <div className="animate-pulse-dot" style={{ width: 16, height: 16, borderRadius: "50%", background: "var(--accent-blue)" }} />
                  </div>
                ) : filteredSetups.length === 0 ? (
                  <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: "0.8rem", textAlign: "center", padding: 20 }}>
                    <div>
                      <div style={{ fontSize: "1.8rem", marginBottom: 8, opacity: 0.4 }}>📊</div>
                      No active setups.<br />Run scanner to find opportunities.
                    </div>
                  </div>
                ) : filteredSetups.map((setup: any, idx: number) => (
                  <div
                    key={setup.id || idx}
                    className={`setup-card${selectedSymbol === setup.symbol ? " setup-card-active" : ""}`}
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
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                      <span style={{ fontWeight: 800, fontSize: "0.88rem" }}>{setup.symbol.replace("USDT", "")}<span style={{ color: "var(--text-muted)", fontWeight: 400, fontSize: "0.72rem" }}>/USDT</span></span>
                      <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
                        <span className={`badge ${setup.direction === "BUY" ? "badge-buy" : "badge-sell"}`}>{setup.direction}</span>
                        <span style={{ fontSize: "0.62rem", padding: "2px 5px", borderRadius: 4, background: "rgba(255,255,255,0.05)", color: "var(--text-muted)" }}>{setup.timeframe}</span>
                      </div>
                    </div>
                    <div className="setup-grid">
                      <div>Entry<span className="setup-val">{(setup.entry_low ?? 0).toLocaleString("en-US", { maximumFractionDigits: 4 })}</span></div>
                      <div>SL<span className="setup-val setup-val-red">{(setup.stop_loss ?? 0).toLocaleString("en-US", { maximumFractionDigits: 4 })}</span></div>
                      <div>TP1<span className="setup-val setup-val-green">{(setup.take_profit_1 ?? 0).toLocaleString("en-US", { maximumFractionDigits: 4 })}</span></div>
                      <div>R:R<span className="setup-val setup-val-blue">1:{(setup.risk_reward ?? 0).toFixed(1)}</span></div>
                    </div>
                    <div style={{ marginTop: 6, display: "flex", justifyContent: "space-between", fontSize: "0.67rem", color: "var(--text-muted)" }}>
                      <span>{setup.setup_type}</span>
                      <span style={{ color: (setup.confluence_score ?? 0) >= 15 ? "#10b981" : "var(--text-muted)" }}>
                        ⚡ {setup.confluence_score ?? 0}/{setup.max_score ?? 36}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* AI Analysis Panel */}
          <AIAnalysisPanel
            symbol={selectedSymbol}
            timeframe={activeTimeframe}
            isOpen={showAIPanel}
            onClose={() => setShowAIPanel(false)}
          />
        </div>

        <style>{`
          @keyframes spin { to { transform: rotate(360deg); } }
          @keyframes fadeIn { from { opacity: 0; transform: scale(0.97); } to { opacity: 1; transform: scale(1); } }

          #charts-page-root {
            display: flex;
            flex-direction: column;
            height: calc(100vh - 68px);
            overflow: hidden;
            gap: 0;
          }

          /* ── Top Bar ── */
          #charts-topbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0 10px;
            flex-shrink: 0;
            gap: 8px;
          }

          #symbol-pill {
            display: flex;
            align-items: center;
            gap: 3px;
            background: rgba(255,255,255,0.05);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 7px 14px;
            cursor: pointer;
            transition: all 0.2s;
          }
          #symbol-pill:hover { background: rgba(255,255,255,0.08); border-color: rgba(255,255,255,0.2); }
          #symbol-pill-name { font-size: 0.95rem; font-weight: 800; color: var(--text-primary); letter-spacing: -0.02em; }
          #symbol-pill-quote { font-size: 0.78rem; color: var(--text-muted); margin-right: 4px; }
          #symbol-pill-caret { font-size: 0.7rem; color: var(--text-muted); }

          .tf-btn {
            padding: 5px 10px;
            border-radius: 7px;
            border: 1px solid var(--border);
            background: transparent;
            color: var(--text-muted);
            font-size: 0.75rem;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.15s;
          }
          .tf-btn:hover { color: var(--text-primary); border-color: rgba(255,255,255,0.2); }
          .tf-btn-active {
            background: rgba(59,130,246,0.15);
            border-color: rgba(59,130,246,0.4);
            color: var(--accent-blue);
          }

          .icon-btn {
            display: flex;
            align-items: center;
            gap: 5px;
            padding: 6px 12px;
            border-radius: 9px;
            border: 1px solid var(--border);
            background: rgba(255,255,255,0.03);
            color: var(--text-secondary);
            font-size: 0.8rem;
            cursor: pointer;
            transition: all 0.2s;
            white-space: nowrap;
          }
          .icon-btn:hover { color: var(--text-primary); border-color: rgba(255,255,255,0.15); background: rgba(255,255,255,0.06); }
          .icon-btn-active { background: rgba(59,130,246,0.12); border-color: rgba(59,130,246,0.35); color: var(--accent-blue); }
          .icon-btn-active-purple { background: rgba(139,92,246,0.12); border-color: rgba(139,92,246,0.35); color: #a78bfa; }
          .icon-btn-active-green { background: rgba(16,185,129,0.12); border-color: rgba(16,185,129,0.35); color: #10b981; }

          /* ── Search overlay ── */
          #search-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.6);
            backdrop-filter: blur(4px);
            z-index: 1000;
            display: flex;
            align-items: flex-start;
            justify-content: center;
            padding-top: 100px;
          }
          #search-box {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 20px;
            width: min(560px, 90vw);
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
            animation: fadeIn 0.15s ease;
          }
          #search-input {
            flex: 1;
            background: rgba(255,255,255,0.04);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 9px 14px;
            color: var(--text-primary);
            font-size: 0.9rem;
            outline: none;
            width: 100%;
          }
          #search-input:focus { border-color: rgba(59,130,246,0.5); }
          .quick-pair-btn {
            padding: 5px 11px;
            border-radius: 7px;
            border: 1px solid var(--border);
            background: rgba(255,255,255,0.03);
            color: var(--text-secondary);
            font-size: 0.78rem;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.15s;
          }
          .quick-pair-btn:hover { background: rgba(255,255,255,0.07); color: var(--text-primary); }
          .quick-pair-btn-active { background: rgba(59,130,246,0.15); border-color: rgba(59,130,246,0.4); color: var(--accent-blue); }

          /* ── Main body ── */
          #charts-body {
            display: flex;
            flex: 1;
            gap: 10px;
            min-height: 0;
            overflow: hidden;
          }

          /* Watchlist sidebar */
          #watchlist-sidebar {
            width: 178px;
            flex-shrink: 0;
            display: flex;
            flex-direction: column;
            padding: 14px 10px;
            overflow: hidden;
            gap: 0;
          }

          .sidebar-title {
            font-size: 0.65rem;
            font-weight: 800;
            color: var(--text-muted);
            letter-spacing: 0.1em;
            margin-bottom: 10px;
          }

          .watchlist-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 6px 8px;
            border-radius: 7px;
            cursor: pointer;
            transition: background 0.12s;
          }
          .watchlist-item:hover { background: rgba(255,255,255,0.04); }
          .watchlist-item-active { background: rgba(59,130,246,0.1) !important; }
          .watchlist-item-muted .wl-base { color: var(--text-muted); }
          .wl-base { font-size: 0.82rem; font-weight: 700; color: var(--text-primary); }
          .wl-quote { font-size: 0.65rem; color: var(--text-muted); }
          .wl-remove {
            background: none; border: none; color: var(--text-muted);
            cursor: pointer; font-size: 0.85rem; padding: 0 2px; line-height: 1;
            opacity: 0; transition: opacity 0.1s;
          }
          .watchlist-item:hover .wl-remove { opacity: 1; }
          .wl-add {
            background: none; border: none; color: var(--text-muted);
            cursor: pointer; font-size: 0.85rem; padding: 0 2px; line-height: 1;
            opacity: 0; transition: opacity 0.1s;
          }
          .watchlist-item:hover .wl-add { opacity: 1; }
          .wl-input {
            flex: 1;
            background: rgba(255,255,255,0.04);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 4px 8px;
            color: var(--text-primary);
            font-size: 0.75rem;
            outline: none;
          }
          .wl-add-btn {
            background: rgba(59,130,246,0.15);
            border: 1px solid rgba(59,130,246,0.3);
            border-radius: 6px;
            padding: 4px 9px;
            color: var(--accent-blue);
            cursor: pointer;
            font-size: 0.85rem;
            font-weight: 700;
          }

          /* Chart area */
          #chart-area {
            flex: 1;
            min-width: 0;
            min-height: 0;
            display: flex;
            flex-direction: column;
          }

          /* MTF grid */
          #mtf-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-template-rows: 1fr 1fr;
            gap: 8px;
            height: 100%;
          }
          .mtf-label {
            position: absolute;
            top: 40px;
            left: 12px;
            z-index: 5;
            pointer-events: none;
            font-size: 1.6rem;
            font-weight: 900;
            opacity: 0.1;
            color: #fff;
            letter-spacing: -0.05em;
          }

          /* Setups sidebar */
          #setups-sidebar {
            width: 276px;
            flex-shrink: 0;
            display: flex;
            flex-direction: column;
            padding: 14px 12px;
            overflow: hidden;
          }

          .setup-card {
            background: rgba(255,255,255,0.02);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 12px;
            cursor: pointer;
            transition: all 0.18s;
          }
          .setup-card:hover { background: rgba(255,255,255,0.04); border-color: rgba(255,255,255,0.12); }
          .setup-card-active { background: rgba(59,130,246,0.08) !important; border-color: rgba(59,130,246,0.35) !important; }

          .setup-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 4px;
            font-size: 0.7rem;
            color: var(--text-muted);
          }
          .setup-val { display: block; font-size: 0.75rem; font-weight: 700; color: var(--text-primary); font-family: 'JetBrains Mono', monospace; }
          .setup-val-red { color: var(--accent-red) !important; }
          .setup-val-green { color: var(--accent-green) !important; }
          .setup-val-blue { color: var(--accent-blue) !important; }

          .dir-filter-btn {
            padding: 3px 8px; border-radius: 6px; font-size: 0.68rem; font-weight: 700; cursor: pointer;
            border: 1px solid var(--border); background: transparent; color: var(--text-muted); transition: all 0.15s;
          }
          .dir-filter-ALL { background: rgba(255,255,255,0.07); color: #fff; border-color: rgba(255,255,255,0.2); }
          .dir-filter-BUY { background: rgba(34,197,94,0.12); color: #22c55e; border-color: rgba(34,197,94,0.35); }
          .dir-filter-SELL { background: rgba(239,68,68,0.12); color: #ef4444; border-color: rgba(239,68,68,0.35); }

          .tf-select {
            padding: 3px 7px; border-radius: 6px; font-size: 0.68rem;
            background: rgba(255,255,255,0.04); border: 1px solid var(--border);
            color: var(--text-secondary); outline: none; cursor: pointer;
          }

          @media (max-width: 1100px) {
            #watchlist-sidebar { width: 150px; }
            #setups-sidebar { width: 240px; }
          }
          @media (max-width: 768px) {
            #charts-page-root { height: auto; overflow: visible; }
            #charts-topbar { flex-direction: column; align-items: flex-start; gap: 14px; }
            #charts-body { flex-direction: column; }
            #watchlist-sidebar, #setups-sidebar { width: 100%; height: auto; max-height: 200px; }
            #chart-area { min-height: 400px; }
          }
        `}</style>
      </div>
    </MainLayout>
  );
}

export default function ChartsPage() {
  return (
    <Suspense fallback={<div style={{ padding: "40px", textAlign: "center", color: "var(--text-muted)" }}>Loading charts...</div>}>
      <ChartsPageContent />
    </Suspense>
  );
}
