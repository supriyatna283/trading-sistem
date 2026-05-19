"use client";

import MainLayout from "@/components/layout/MainLayout";
import { useState } from "react";
import { api } from "@/lib/api";

export default function BacktestPage() {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState("");
  
  const [form, setForm] = useState({
    symbol: "BTCUSDT",
    timeframe: "1h",
    days: 30,
    initial_capital: 10000,
    risk_per_trade_pct: 1.0
  });

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResults(null);
    
    try {
      const res = await api.runBacktest({
        symbol: form.symbol,
        timeframe: form.timeframe,
        days: parseInt(form.days.toString()),
        initial_capital: parseFloat(form.initial_capital.toString()),
        risk_per_trade_pct: parseFloat(form.risk_per_trade_pct.toString())
      });
      setResults(res);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Failed to run backtest");
    } finally {
      setLoading(false);
    }
  };

  return (
    <MainLayout>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: "1.5rem", fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>Strategy Simulator</h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "4px 0 0" }}>Test the Confluence Engine against historical market data</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Form */}
        <div className="glass-card flex flex-col h-fit">
          <h2 className="text-sm font-bold uppercase text-muted-foreground mb-4">Simulation Parameters</h2>
          <form onSubmit={handleRun} className="flex flex-col gap-4">
            <div>
              <label className="block text-xs uppercase text-muted-foreground mb-1 font-semibold">Asset Pair</label>
              <input 
                type="text" 
                value={form.symbol} 
                onChange={e => setForm({...form, symbol: e.target.value.toUpperCase()})}
                className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary transition-colors"
              />
            </div>
            
            <div className="grid grid-cols-2 gap-4">
               <div>
                  <label className="block text-xs uppercase text-muted-foreground mb-1 font-semibold">Timeframe</label>
                  <select 
                    value={form.timeframe} 
                    onChange={e => setForm({...form, timeframe: e.target.value})}
                    className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary transition-colors"
                  >
                    <option value="15m">15m</option>
                    <option value="1h">1H</option>
                    <option value="4h">4H</option>
                    <option value="1d">1D</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs uppercase text-muted-foreground mb-1 font-semibold">History (Days)</label>
                  <input 
                    type="number" 
                    max={90}
                    min={1}
                    value={form.days} 
                    onChange={e => setForm({...form, days: e.target.value as any})}
                    className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary transition-colors"
                  />
                </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
               <div>
                  <label className="block text-xs uppercase text-muted-foreground mb-1 font-semibold">Start Capital ($)</label>
                  <input 
                    type="number" 
                    value={form.initial_capital} 
                    onChange={e => setForm({...form, initial_capital: e.target.value as any})}
                    className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary transition-colors"
                  />
                </div>
                <div>
                  <label className="block text-xs uppercase text-muted-foreground mb-1 font-semibold">Risk / Trade (%)</label>
                  <input 
                    type="number" 
                    step="0.1"
                    value={form.risk_per_trade_pct} 
                    onChange={e => setForm({...form, risk_per_trade_pct: e.target.value as any})}
                    className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary transition-colors"
                  />
                </div>
            </div>

            <button 
              type="submit" 
              disabled={loading}
              className="mt-4 bg-primary hover:bg-primary/90 text-white font-bold py-3 px-4 rounded-lg flex items-center justify-center transition-all"
            >
              {loading ? (
                <><span className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full mr-2"></span> Running Simulation...</>
              ) : "▶ Run Backtest"}
            </button>
            {error && <div className="text-red-500 text-xs mt-2 text-center">{error}</div>}
          </form>
        </div>

        {/* Right Column: Results */}
        <div className="lg:col-span-2">
          {loading ? (
             <div className="glass-card h-full flex flex-col items-center justify-center p-12 text-muted-foreground">
                <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full mb-4"></div>
                <div>Fetching historical data from Binance and simulating trades...</div>
                <div className="text-xs mt-2 opacity-60">This may take a few seconds depending on the date range.</div>
             </div>
          ) : (results && results.summary) ? (
            <div className="flex flex-col gap-6">
              {/* Top Stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                 <div className="glass-card p-4 text-center">
                    <div className="text-[10px] uppercase font-bold text-muted-foreground mb-1">Total Return</div>
                    <div className={`text-xl font-black font-mono ${(results.summary.total_return_pct ?? 0) >= 0 ? "text-green-500" : "text-red-500"}`}>
                        {(results.summary.total_return_pct ?? 0) >= 0 ? "+" : ""}{(results.summary.total_return_pct ?? 0).toFixed(2)}%
                    </div>
                 </div>
                 <div className="glass-card p-4 text-center">
                    <div className="text-[10px] uppercase font-bold text-muted-foreground mb-1">Final Equity</div>
                    <div className="text-xl font-black font-mono text-white">
                        ${(results.summary.final_equity ?? 0).toFixed(2)}
                    </div>
                 </div>
                 <div className="glass-card p-4 text-center">
                    <div className="text-[10px] uppercase font-bold text-muted-foreground mb-1">Win Rate</div>
                    <div className="text-xl font-black font-mono text-blue-400">
                        {(results.summary.win_rate ?? 0).toFixed(1)}%
                    </div>
                 </div>
                 <div className="glass-card p-4 text-center">
                    <div className="text-[10px] uppercase font-bold text-muted-foreground mb-1">Max Drawdown</div>
                    <div className="text-xl font-black font-mono text-red-400">
                        -{(results.summary.max_drawdown_pct ?? 0).toFixed(2)}%
                    </div>
                 </div>
              </div>
 
               {/* Trade History */}
               <div className="glass-card overflow-hidden">
                  <h2 className="text-sm font-bold uppercase text-muted-foreground mb-4 px-2">Trade History ({(results.summary.total_trades ?? 0)} trades)</h2>
                 
                 {results.trades.length === 0 ? (
                    <div className="text-center text-muted-foreground text-sm py-8">No trades taken during this period.</div>
                 ) : (
                    <div className="overflow-x-auto">
                        <table className="data-table text-xs">
                          <thead>
                             <tr>
                               <th>Entry Time</th>
                               <th>Side</th>
                               <th>Price</th>
                               <th>Grade</th>
                               <th>Score</th>
                               <th>R:R</th>
                               <th>Result</th>
                               <th>PnL</th>
                             </tr>
                          </thead>
                          <tbody>
                             {results.trades.map((t: any, i: number) => (
                                <tr key={i}>
                                   <td className="text-muted-foreground">{new Date(t.entry_time).toLocaleString()}</td>
                                   <td><span className={`badge ${t.direction === "BUY" ? "badge-buy" : "badge-sell"}`}>{t.direction === "BUY" ? "LONG" : "SHORT"}</span></td>
                                   <td className="font-mono">{t.entry_price > 10 ? t.entry_price.toFixed(2) : t.entry_price.toFixed(5)}</td>
                                   <td>
                                      <span style={{ 
                                        fontSize: "0.65rem", fontWeight: 800, padding: "2px 6px", borderRadius: 4,
                                        color: t.signal_grade === "A+" ? "#f59e0b" : "#10b981",
                                        background: t.signal_grade === "A+" ? "rgba(245,158,11,0.1)" : "rgba(16,185,129,0.1)"
                                      }}>
                                        {t.signal_grade || "VALID"}
                                      </span>
                                   </td>
                                   <td>
                                      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                                        <div style={{ width: 30, height: 4, background: "rgba(255,255,255,0.05)", borderRadius: 2 }}>
                                          <div style={{ width: `${t.signal_score || 0}%`, height: "100%", background: "#3b82f6", borderRadius: 2 }} />
                                        </div>
                                        <span style={{ fontFamily: "monospace" }}>{t.signal_score || 0}</span>
                                      </div>
                                   </td>
                                   <td className="text-blue-400">1:{t.risk_reward.toFixed(1)}</td>
                                   <td><span className={`badge ${t.result === "WIN" ? "badge-bullish" : t.result === "LOSS" ? "badge-bearish" : "badge-sideways"}`}>{t.result}</span></td>
                                   <td className={`font-mono font-bold ${t.pnl >= 0 ? "text-green-500" : "text-red-500"}`}>
                                      {t.pnl >= 0 ? "+" : ""}${t.pnl.toFixed(2)}
                                   </td>
                                </tr>
                             ))}
                          </tbody>
                        </table>
                    </div>
                 )}
              </div>
            </div>
          ) : (
            <div className="glass-card h-full flex flex-col items-center justify-center p-12 text-muted-foreground text-center">
              <div className="text-4xl mb-4">⏱️</div>
              <h3 className="font-bold text-lg mb-2 text-white">Simulator Ready</h3>
              <p className="text-sm">Configure your parameters on the left and click run to backtest the Confluence Engine algorithm over historical Binance data.</p>
            </div>
          )}
        </div>
      </div>
    </MainLayout>
  );
}
