'use client';

import React, { useState } from 'react';
import MainLayout from '@/components/layout/MainLayout';
import { DollarSign, TrendingUp, TrendingDown, Activity, Clock, Search } from 'lucide-react';
import Link from 'next/link';

const FOREX_PAIRS = [
  { symbol: 'EUR/USD', price: 1.0934, change: 0.12, spread: 0.8, status: 'Active' },
  { symbol: 'GBP/USD', price: 1.2645, change: -0.05, spread: 1.2, status: 'Active' },
  { symbol: 'USD/JPY', price: 150.23, change: 0.45, spread: 0.9, status: 'Active' },
  { symbol: 'AUD/USD', price: 0.6521, change: -0.15, spread: 1.1, status: 'Active' },
  { symbol: 'USD/CAD', price: 1.3576, change: 0.08, spread: 1.4, status: 'Active' },
  { symbol: 'USD/CHF', price: 0.8854, change: -0.22, spread: 1.3, status: 'Active' },
];

export default function ForexPage() {
  const [scanLoading, setScanLoading] = useState(false);

  const runScan = () => {
    setScanLoading(true);
    setTimeout(() => setScanLoading(false), 2000);
  };

  return (
    <MainLayout>
      <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500 pb-12">
        {/* Header */}
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-green-500/20 text-green-400 rounded-xl border border-green-500/30 shadow-[0_0_15px_rgba(34,197,94,0.3)]">
                <DollarSign className="w-7 h-7" />
              </div>
              <h1 style={{ fontFamily: "'Outfit',sans-serif", fontSize: "2.2rem", fontWeight: 900, letterSpacing: "-0.04em", margin: 0,
                background: "linear-gradient(135deg, #fff 30%, #4ade80)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                Forex Trading Desk
              </h1>
            </div>
            <p className="text-gray-400 max-w-2xl text-sm md:text-base mt-2 font-medium">
              Institutional-grade forex market intelligence. Real-time spreads, volume analysis, and AI-driven signal detection for major currency pairs.
            </p>
          </div>
          
          <div className="flex items-center gap-3">
             <div className="flex items-center gap-2 text-xs font-bold text-green-400 bg-green-500/10 px-4 py-2.5 rounded-xl border border-green-500/20 shadow-lg shadow-green-500/5">
                <span className="relative flex h-2.5 w-2.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500"></span>
                </span>
                London / NY Overlap
              </div>
          </div>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="glass-card p-6 border border-white/5 relative overflow-hidden group hover:border-green-500/30 transition-colors bg-[#080c14]/60 backdrop-blur-md rounded-2xl">
            <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity translate-x-4 -translate-y-4">
              <Activity size={80} className="text-green-500" />
            </div>
            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">Daily Volume (FX)</h3>
            <div className="text-3xl font-black text-white mb-1">$6.6T</div>
            <div className="text-xs text-green-400 font-bold flex items-center gap-1 bg-green-500/10 w-fit px-2 py-1 rounded-md">
              <TrendingUp size={14} /> +2.4% vs prev session
            </div>
          </div>
          <div className="glass-card p-6 border border-white/5 relative overflow-hidden group hover:border-blue-500/30 transition-colors bg-[#080c14]/60 backdrop-blur-md rounded-2xl">
             <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity translate-x-4 -translate-y-4">
              <Clock size={80} className="text-blue-500" />
            </div>
            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">Active Session</h3>
            <div className="text-3xl font-black text-white mb-1">NY / LON</div>
            <div className="text-xs text-blue-400 font-bold flex items-center gap-1 bg-blue-500/10 w-fit px-2 py-1 rounded-md">
               High Volatility Expected
            </div>
          </div>
           <div className="glass-card p-6 border border-white/5 relative overflow-hidden group hover:border-purple-500/30 transition-colors bg-[#080c14]/60 backdrop-blur-md rounded-2xl">
             <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">A+ Setups Found</h3>
            <div className="text-3xl font-black text-white mb-1">4</div>
            <div className="text-xs text-purple-400 font-bold flex items-center gap-1 bg-purple-500/10 w-fit px-2 py-1 rounded-md">
               Across 28 major/minor pairs
            </div>
          </div>
           <div className="glass-card p-6 border border-white/5 relative overflow-hidden group hover:border-orange-500/30 transition-colors bg-[#080c14]/60 backdrop-blur-md rounded-2xl">
             <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">Avg Spread (Majors)</h3>
            <div className="text-3xl font-black text-white mb-1">0.8<span className="text-lg text-gray-500 ml-1">pips</span></div>
            <div className="text-xs text-orange-400 font-bold flex items-center gap-1 bg-orange-500/10 w-fit px-2 py-1 rounded-md">
               Optimal trading conditions
            </div>
          </div>
        </div>

        {/* Forex Scanner Table */}
        <div className="glass-card p-1 border border-white/10 rounded-2xl bg-gradient-to-b from-white/5 to-transparent">
          <div className="bg-[#0b0f19] rounded-[15px] p-6">
             <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 sm:gap-0 mb-6">
               <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div style={{ width: 4, height: 24, borderRadius: 99, background: "linear-gradient(180deg,#22c55e,#3b82f6)" }} />
                  <div>
                    <div style={{ fontWeight: 800, fontSize: "1.15rem", letterSpacing: "-0.01em" }}>Major Pairs Watchlist</div>
                    <div className="text-xs text-gray-500 font-semibold mt-0.5">Real-time quote and signal processing</div>
                  </div>
                </div>
                <button className="btn-primary group" style={{ padding: "10px 24px", fontSize: "0.85rem", display: "flex", alignItems: "center", gap: 8, fontWeight: 700, borderRadius: "12px", background: "linear-gradient(135deg, #10b981, #059669)", border: "none", boxShadow: "0 4px 14px rgba(16, 185, 129, 0.3)" }}
                  onClick={runScan} disabled={scanLoading}>
                  {scanLoading ? <><span className="animate-spin" style={{ display: "inline-block" }}>⟳</span> Scanning Network...</> : <><Search size={16} className="group-hover:scale-110 transition-transform"/> Scan Markets</>}
                </button>
             </div>
             
             <div className="overflow-x-auto">
               <table className="data-table min-w-full">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wider text-gray-500 border-b border-white/5">
                      <th className="pb-4 pl-4 font-bold">Currency Pair</th>
                      <th className="pb-4 font-bold">Bid/Ask Price</th>
                      <th className="pb-4 font-bold">24h Change</th>
                      <th className="pb-4 font-bold">Spread (pips)</th>
                      <th className="pb-4 font-bold">AI Signal</th>
                      <th className="pb-4 pr-4 text-right font-bold">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {FOREX_PAIRS.map((pair, idx) => (
                      <tr key={idx} className="group hover:bg-white/[0.02] transition-colors border-b border-white/5 last:border-0">
                        <td className="py-4 pl-4">
                          <div className="flex items-center gap-3">
                             <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-gray-800 to-gray-900 flex items-center justify-center border border-white/10 text-[0.65rem] font-black text-gray-300 shadow-inner">
                               {pair.symbol.split('/')[0]}
                             </div>
                             <div>
                               <div className="font-bold text-[0.95rem] tracking-tight">{pair.symbol}</div>
                               <div className="text-[0.65rem] text-gray-500 font-bold uppercase tracking-wider">{pair.status}</div>
                             </div>
                          </div>
                        </td>
                        <td className="py-4 font-mono font-bold text-[0.95rem] text-gray-200">
                          {pair.price.toFixed(4)}
                        </td>
                        <td className="py-4">
                           <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold font-mono shadow-sm ${pair.change >= 0 ? 'bg-green-500/10 text-green-400 border border-green-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
                             {pair.change >= 0 ? <TrendingUp size={14}/> : <TrendingDown size={14}/>}
                             {pair.change > 0 ? '+' : ''}{pair.change}%
                           </span>
                        </td>
                        <td className="py-4 font-mono text-gray-400 font-semibold text-sm">
                          {pair.spread}
                        </td>
                        <td className="py-4">
                          {idx === 0 || idx === 3 ? (
                            <span className="bg-green-500/15 text-green-400 border border-green-500/30 px-3 py-1.5 rounded-lg text-xs font-bold tracking-widest flex items-center gap-1.5 w-fit">
                              <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse"></div>
                              BUY
                            </span>
                          ) : idx === 1 ? (
                             <span className="bg-red-500/15 text-red-400 border border-red-500/30 px-3 py-1.5 rounded-lg text-xs font-bold tracking-widest flex items-center gap-1.5 w-fit">
                               <div className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse"></div>
                              SELL
                            </span>
                          ) : (
                             <span className="bg-gray-500/15 text-gray-400 border border-gray-500/30 px-3 py-1.5 rounded-lg text-xs font-bold tracking-widest flex items-center gap-1.5 w-fit">
                               <div className="w-1.5 h-1.5 rounded-full bg-gray-400"></div>
                              NEUTRAL
                            </span>
                          )}
                        </td>
                        <td className="py-4 pr-4 text-right">
                           <Link href={`/charts?symbol=${pair.symbol.replace('/', '')}&tf=1h`} className="inline-flex items-center gap-2 text-blue-400 hover:text-blue-300 hover:bg-blue-500/10 px-3 py-1.5 rounded-lg text-sm font-bold opacity-0 group-hover:opacity-100 transition-all">
                              Trade <Activity size={14} />
                           </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
               </table>
             </div>
          </div>
        </div>

      </div>
    </MainLayout>
  );
}
