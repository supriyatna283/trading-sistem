import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, ArrowUpRight, ArrowDownRight, RefreshCw, Eye, Zap, ArrowRight, Check, Copy } from 'lucide-react';
import { formatUsd, CHAINS, ACTION_COLORS, ENTITY_BADGES } from './constants';

interface LiveStreamTableProps {
  transactions: any[];
  setInspectTx: (tx: any) => void;
  setInspectWallet: (wallet: any) => void;
  loadMoreHistory?: () => void;
  isLoadingMore?: boolean;
}

export const LiveStreamTable: React.FC<LiveStreamTableProps> = React.memo(({
  transactions,
  setInspectTx,
  setInspectWallet,
  loadMoreHistory,
  isLoadingMore
}) => {
  const [expandedTxId, setExpandedTxId] = useState<string | null>(null);
  const [copiedText, setCopiedText] = useState<string | null>(null);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(text);
    setTimeout(() => setCopiedText(null), 2000);
  };

  return (
    <div className="rounded-2xl border border-slate-700/50 bg-slate-900/40 backdrop-blur-xl shadow-[0_8px_30px_rgba(0,0,0,0.12)] overflow-hidden relative z-10">
      <div className="px-6 py-4 border-b border-slate-700/50 flex items-center justify-between bg-gradient-to-r from-slate-800/40 to-slate-900/40">
        <div className="flex items-center gap-3">
          <div className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-cyan-500 shadow-[0_0_8px_rgba(6,182,212,0.8)]"></span>
          </div>
          <h3 className="text-base font-black text-white tracking-wide">
            Real-time Transaction Stream
          </h3>
          <span className="text-xs font-medium text-cyan-400 bg-cyan-500/10 px-2.5 py-0.5 rounded-full border border-cyan-500/20">
            {transactions.length} whale movements
          </span>
        </div>
        <span className="text-xs font-semibold text-slate-400 tracking-wider">Click any row for route visualization</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-700/50 bg-slate-900/60 text-[11px] font-black text-slate-300 uppercase tracking-widest">
              <th className="py-3 px-4">Time</th>
              <th className="py-3 px-4">Chain</th>
              <th className="py-3 px-4">Action</th>
              <th className="py-3 px-4 text-right">Value (USD)</th>
              <th className="py-3 px-4">Token Amount</th>
              <th className="py-3 px-4">From Entity</th>
              <th className="py-3 px-4">To Entity</th>
              <th className="py-3 px-4 text-center">Inspect</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50 text-xs font-medium relative">
            <AnimatePresence initial={false}>
              {transactions.length === 0 ? (
                <motion.tr 
                  initial={{ opacity: 0 }} 
                  animate={{ opacity: 1 }} 
                  exit={{ opacity: 0 }}
                >
                  <td colSpan={8} className="py-12 text-center text-slate-500">
                    <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-slate-600" />
                    No whale transactions match your active filters.
                  </td>
                </motion.tr>
              ) : (
                transactions.map((tx) => {
                  const isExpanded = expandedTxId === tx.id;
                  const fromBadge = ENTITY_BADGES[tx.fromEntityType] || ENTITY_BADGES.unknown;
                  const toBadge = ENTITY_BADGES[tx.toEntityType] || ENTITY_BADGES.unknown;

                  return (
                    <React.Fragment key={tx.id}>
                      <motion.tr
                        layout="position"
                        initial={tx.isNew ? { backgroundColor: 'rgba(6, 182, 212, 0.2)' } : { backgroundColor: 'transparent' }}
                        animate={{ backgroundColor: 'transparent' }}
                        transition={{ duration: 2, ease: "easeOut" }}
                        onClick={() => setExpandedTxId(isExpanded ? null : tx.id)}
                        className={`group cursor-pointer transition-colors ${
                          isExpanded ? 'bg-slate-800/60' : 'hover:bg-slate-800/30'
                        }`}
                      >
                        {/* Time */}
                        <td className="py-3 px-4 font-mono text-slate-400 whitespace-nowrap">
                          {tx.time}
                        </td>

                        {/* Chain */}
                        <td className="py-3 px-4 whitespace-nowrap">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-extrabold border ${
                              CHAINS.find((c) => c.id === tx.chain)?.color || 'bg-slate-800 text-slate-300'
                            }`}
                          >
                            {tx.chain}
                          </span>
                        </td>

                        {/* Action */}
                        <td className="py-4 px-4 whitespace-nowrap">
                          <span
                            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-black tracking-wider uppercase border ${
                              ACTION_COLORS[tx.action] || 'bg-slate-800 text-slate-300'
                            }`}
                          >
                            {tx.action === 'BUY' && <ArrowDownRight className="w-3.5 h-3.5 text-emerald-400" />}
                            {tx.action === 'SELL' && <ArrowUpRight className="w-3.5 h-3.5 text-rose-400" />}
                            {tx.action === 'TRANSFER' && <RefreshCw className="w-3.5 h-3.5 text-cyan-400" />}
                            {tx.action}
                          </span>
                        </td>

                        {/* Value USD */}
                        <td className="py-3 px-4 text-right whitespace-nowrap font-mono font-bold text-slate-100 text-sm">
                          {formatUsd(tx.usdValue)}
                          {tx.impact === 'MEGA' && (
                            <span className="ml-1.5 inline-block text-[10px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-sans">
                              MEGA
                            </span>
                          )}
                        </td>

                        {/* Token Amount */}
                        <td className="py-3 px-4 whitespace-nowrap font-mono">
                          <span className="text-slate-200 font-bold">{tx.amount}</span>{' '}
                          <span className="text-cyan-400 text-xs font-semibold">{tx.token}</span>
                        </td>

                        {/* From Entity */}
                        <td className="py-3 px-4 whitespace-nowrap">
                          <div className="flex items-center gap-1.5">
                            <span
                              onClick={(e) => {
                                e.stopPropagation();
                                setInspectWallet({ name: tx.fromEntity, type: tx.fromEntityType, address: tx.from });
                              }}
                              className="font-bold text-slate-200 hover:text-cyan-300 hover:underline"
                            >
                              {tx.fromEntity}
                            </span>
                            <span className={`px-1.5 py-0.2 rounded text-[9px] font-semibold border ${fromBadge.bg}`}>
                              {fromBadge.label}
                            </span>
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono">{tx.from}</span>
                        </td>

                        {/* To Entity */}
                        <td className="py-3 px-4 whitespace-nowrap">
                          <div className="flex items-center gap-1.5">
                            <span
                              onClick={(e) => {
                                e.stopPropagation();
                                setInspectWallet({ name: tx.toEntity, type: tx.toEntityType, address: tx.to });
                              }}
                              className="font-bold text-slate-200 hover:text-cyan-300 hover:underline"
                            >
                              {tx.toEntity}
                            </span>
                            <span className={`px-1.5 py-0.2 rounded text-[9px] font-semibold border ${toBadge.bg}`}>
                              {toBadge.label}
                            </span>
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono">{tx.to}</span>
                        </td>

                        {/* Action Buttons */}
                        <td className="py-3 px-4 text-center whitespace-nowrap">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setInspectTx(tx);
                            }}
                            className="p-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-cyan-300 transition-colors"
                            title="Detailed Route Inspection"
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </motion.tr>

                      {/* Expanded Visual Flow Row */}
                      <AnimatePresence>
                        {isExpanded && (
                          <motion.tr 
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            className="bg-slate-900/60 border-b border-slate-700/50 overflow-hidden"
                          >
                            <td colSpan={8} className="p-0">
                              <div className="p-5 m-3 rounded-2xl bg-gradient-to-b from-slate-900 to-slate-950 border border-slate-700/50 shadow-inner space-y-4">
                                <div className="flex items-center justify-between text-xs text-slate-400">
                                  <span className="font-semibold text-slate-300 flex items-center gap-1">
                                    <Zap className="w-3.5 h-3.5 text-amber-400" /> Transaction Route Visualizer
                                  </span>
                                  <div className="flex items-center gap-3">
                                    <span>Est. Gas: <strong className="text-slate-200">{tx.gasFee}</strong></span>
                                    <span>Tx Hash: <code className="text-cyan-400">{tx.hash}</code></span>
                                    <button
                                      onClick={() => copyToClipboard(tx.hash)}
                                      className="text-slate-400 hover:text-slate-200"
                                    >
                                      {copiedText === tx.hash ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                                    </button>
                                  </div>
                                </div>

                                {/* Route Path Flow Diagram */}
                                <div className="flex items-center justify-between gap-4 py-3 px-6 rounded-lg bg-slate-900 border border-slate-800/80">
                                  <div className="text-center w-1/4">
                                    <p className="text-[10px] text-slate-500 uppercase tracking-wider">Origin</p>
                                    <p className="font-bold text-slate-200 text-sm truncate">{tx.fromEntity}</p>
                                    <p className="text-[10px] text-slate-400 font-mono truncate">{tx.from}</p>
                                  </div>

                                  <div className="flex-1 flex flex-col items-center">
                                    <span className="text-xs font-bold text-cyan-400 mb-1">
                                      {tx.amount} {tx.token} ({formatUsd(tx.usdValue)})
                                    </span>
                                    <div className="w-full flex items-center relative">
                                      <div className="h-0.5 flex-1 bg-gradient-to-r from-cyan-500 to-indigo-500"></div>
                                      <motion.div 
                                        animate={{ x: [0, 10, 0] }} 
                                        transition={{ repeat: Infinity, duration: 1.5 }}
                                        className="p-1 rounded-full bg-indigo-600 text-slate-100 shadow-md z-10 mx-2"
                                      >
                                        <ArrowRight className="w-4 h-4" />
                                      </motion.div>
                                      <div className="h-0.5 flex-1 bg-gradient-to-r from-indigo-500 to-emerald-500"></div>
                                    </div>
                                    <span className="text-[10px] text-slate-400 mt-1">
                                      Action: {tx.action} via {tx.chain} Network
                                    </span>
                                  </div>

                                  <div className="text-center w-1/4">
                                    <p className="text-[10px] text-slate-500 uppercase tracking-wider">Destination</p>
                                    <p className="font-bold text-slate-200 text-sm truncate">{tx.toEntity}</p>
                                    <p className="text-[10px] text-slate-400 font-mono truncate">{tx.to}</p>
                                  </div>
                                </div>
                              </div>
                            </td>
                          </motion.tr>
                        )}
                      </AnimatePresence>
                    </React.Fragment>
                  );
                })
              )}
            </AnimatePresence>
          </tbody>
        </table>
        
        {loadMoreHistory && transactions.length > 0 && (
          <div className="p-4 border-t border-slate-700/50 flex justify-center">
            <button 
              onClick={loadMoreHistory}
              disabled={isLoadingMore}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm font-semibold transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              {isLoadingMore ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Loading...
                </>
              ) : (
                'Load More History'
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
});
