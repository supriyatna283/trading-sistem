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
    <div className="p-4 rounded-2xl bg-[#0f1420] border border-slate-800/80 shadow-xl space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Chain Selector Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 scrollbar-hide">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider mr-1 flex items-center gap-1 shrink-0">
            <Filter className="w-3.5 h-3.5 text-cyan-400" /> Chains:
          </span>
          {CHAINS.map((chain) => (
            <button
              key={chain.id}
              onClick={() => setSelectedChain(chain.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all border shrink-0 ${
                selectedChain === chain.id
                  ? 'bg-cyan-500 text-slate-950 border-cyan-400 shadow-lg shadow-cyan-500/20'
                  : 'bg-slate-900/80 text-slate-400 border-slate-800 hover:bg-slate-800 hover:text-slate-200'
              }`}
            >
              {chain.name}
            </button>
          ))}
        </div>

        {/* Threshold Filter Buttons */}
        <div className="flex items-center gap-1.5 shrink-0">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider mr-1">
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
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all border ${
                minUsdFilter === opt.val
                  ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40'
                  : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:text-slate-200'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="pt-2 border-t border-slate-800/60 flex flex-wrap items-center justify-between gap-3">
        {/* Search Input */}
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search token symbol, entity, wallet or transaction hash..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-950/80 border border-slate-800 rounded-xl pl-9 pr-4 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/20 transition-all"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Action Type Dropdown / Selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400 font-medium">Action:</span>
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-cyan-500/50"
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
            className="px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 text-xs font-semibold"
          >
            Reset
          </button>
        </div>
      </div>
    </div>
  );
};
