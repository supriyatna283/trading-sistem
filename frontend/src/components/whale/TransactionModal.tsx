import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Zap, Copy, ExternalLink } from 'lucide-react';
import { formatUsd, getBlockExplorerUrl } from './constants';

interface TransactionModalProps {
  inspectTx: any;
  setInspectTx: (tx: any) => void;
}

export const TransactionModal: React.FC<TransactionModalProps> = ({ inspectTx, setInspectTx }) => {
  const [copied, setCopied] = useState(false);

  if (!inspectTx) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(inspectTx.hash);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          className="bg-[#0f1420] border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl relative space-y-5"
        >
          <button
            onClick={() => setInspectTx(null)}
            className="absolute top-4 right-4 p-1.5 rounded-lg bg-slate-800/80 text-slate-400 hover:text-slate-200"
          >
            <X className="w-4 h-4" />
          </button>

          <div className="flex items-center gap-3">
            <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
              <Zap className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-100">Transaction Deep Dive</h3>
              <p className="text-xs text-slate-400">Verified On-Chain Multi-Chain Event</p>
            </div>
          </div>

          <div className="space-y-3 p-4 rounded-xl bg-slate-950 border border-slate-800/80 text-xs font-mono">
            <div className="flex justify-between py-1 border-b border-slate-800">
              <span className="text-slate-500">Amount & Asset:</span>
              <span className="text-cyan-300 font-bold">
                {inspectTx.amount} {inspectTx.token}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800">
              <span className="text-slate-500">USD Value:</span>
              <span className="text-slate-100 font-bold">{formatUsd(inspectTx.usdValue)}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800">
              <span className="text-slate-500">Origin Entity:</span>
              <span className="text-slate-200 font-bold">{inspectTx.fromEntity}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800">
              <span className="text-slate-500">Destination Entity:</span>
              <span className="text-slate-200 font-bold">{inspectTx.toEntity}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800">
              <span className="text-slate-500">Est. Gas Fee:</span>
              <span className="text-slate-300">{inspectTx.gasFee}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500">Transaction Hash:</span>
              <span className="text-cyan-400 truncate max-w-[180px]">{inspectTx.hash}</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleCopy}
              className="flex-1 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs flex items-center justify-center gap-2 transition-colors"
            >
              <Copy className="w-4 h-4" /> {copied ? 'Copied!' : 'Copy Hash'}
            </button>
            <a
              href={getBlockExplorerUrl(inspectTx.chain, inspectTx.hash)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/20 transition-all"
            >
              <ExternalLink className="w-4 h-4" /> Block Explorer
            </a>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
