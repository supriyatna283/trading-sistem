import React from 'react';
import { Filter, Search, X } from 'lucide-react';
import { CHAINS } from './constants';

interface WhaleFilterBarProps {
  selectedChain: string;
  setSelectedChain: (chain: string) => void;
  minUsdFilter: number;
  setMinUsdFilter: (minUsd: number) => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  actionFilter: string;
  setActionFilter: (action: string) => void;
}

export const WhaleFilterBar: React.FC<WhaleFilterBarProps> = ({
  selectedChain,
  setSelectedChain,
  minUsdFilter,
  setMinUsdFilter,
  searchQuery,
  setSearchQuery,
  actionFilter,
  setActionFilter,
}) => {
  return (
    <div className="p-5 rounded-2xl bg-slate-900/40 backdrop-blur-xl border border-slate-700/50 shadow-[0_8px_30px_rgba(0,0,0,0.12)] space-y-4 relative z-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Chain Selector Pills */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0 scrollbar-hide">
          <span className="text-xs font-bold text-slate-400 uppercase tracking-widest mr-2 flex items-center gap-1.5 shrink-0">
            <Filter className="w-4 h-4 text-cyan-400" /> Chains:
          </span>
          {CHAINS.map((chain) => (
            <button
              key={chain.id}
              onClick={() => setSelectedChain(chain.id)}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all border shrink-0 ${
                selectedChain === chain.id
                  ? 'bg-gradient-to-r from-cyan-500 to-blue-500 text-white border-transparent shadow-[0_0_15px_rgba(6,182,212,0.4)]'
                  : 'bg-slate-800/50 text-slate-400 border-slate-700 hover:bg-slate-700 hover:text-white hover:border-slate-600'
              }`}
            >
              {chain.name}
            </button>
          ))}
        </div>

        {/* Threshold Filter Buttons */}
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs font-bold text-slate-400 uppercase tracking-widest mr-2">
            Min Size:
          </span>
          {[
            { label: 'All ($10k+)', val: 10000 },
            { label: '$100k+', val: 100000 },
            { label: '$1M+ 🐋', val: 1000000 },
            { label: '$10M+ 🚀', val: 10000000 }
          ].map((opt) => (
            <button
              key={opt.val}
              onClick={() => setMinUsdFilter(opt.val)}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all border ${
                minUsdFilter === opt.val
                  ? 'bg-gradient-to-r from-indigo-500 to-purple-500 text-white border-transparent shadow-[0_0_15px_rgba(99,102,241,0.4)]'
                  : 'bg-slate-800/50 text-slate-400 border-slate-700 hover:bg-slate-700 hover:text-white'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="pt-4 border-t border-slate-700/50 flex flex-wrap items-center justify-between gap-4">
        {/* Search Input */}
        <div className="relative flex-1 min-w-[280px]">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search token symbol, entity, wallet or transaction hash..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-950/50 border border-slate-700 rounded-xl pl-10 pr-4 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500/50 transition-all shadow-inner"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Action Type Dropdown / Selector */}
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-400 font-bold tracking-widest uppercase">Action:</span>
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="bg-slate-950/50 border border-slate-700 rounded-xl px-3 py-2 text-sm font-semibold text-slate-200 focus:outline-none focus:border-cyan-500 transition-all cursor-pointer"
          >
            <option value="ALL">All Actions</option>
            <option value="TRANSFER">Transfers Only</option>
            <option value="BUY">Buys / Swaps</option>
            <option value="SELL">Sells</option>
            <option value="STAKE">Staking</option>
            <option value="BRIDGE">Bridge Cross-chain</option>
          </select>

          <button
            onClick={() => {
              setSelectedChain('ALL');
              setMinUsdFilter(10000);
              setSearchQuery('');
              setActionFilter('ALL');
            }}
            className="px-4 py-2 rounded-xl bg-slate-800 border border-slate-700 text-slate-300 hover:text-white hover:bg-slate-700 hover:border-slate-600 transition-all text-xs font-bold"
          >
            Reset Filters
          </button>
        </div>
      </div>
    </div>
  );
};
