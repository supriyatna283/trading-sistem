import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';

interface WalletModalProps {
  inspectWallet: any;
  setInspectWallet: (wallet: any) => void;
}

export const WalletModal: React.FC<WalletModalProps> = ({ inspectWallet, setInspectWallet }) => {
  if (!inspectWallet) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/70 backdrop-blur-sm">
        <motion.div
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ type: 'spring', damping: 25, stiffness: 200 }}
          className="w-full max-w-md bg-[#0d111a] border-l border-slate-800 h-full p-6 shadow-2xl flex flex-col justify-between space-y-6"
        >
          <div className="space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-base font-bold text-slate-100">{inspectWallet.name}</h3>
                <p className="text-xs text-slate-500 font-mono mt-0.5">{inspectWallet.address}</p>
              </div>
              <button
                onClick={() => setInspectWallet(null)}
                className="p-1.5 rounded-lg bg-slate-800/80 text-slate-400 hover:text-slate-200 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Wallet Summary KPI */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <p className="text-xs text-slate-400">Estimated On-Chain Balance</p>
              <p className="text-2xl font-black text-emerald-400">$248,510,000</p>
              <div className="flex items-center gap-2 text-xs text-slate-400 pt-1">
                <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">
                  Risk Score: Low (0.04)
                </span>
              </div>
            </div>

            {/* Asset Holdings Distribution */}
            <div className="space-y-3">
              <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">Top Token Holdings</h4>
              {[
                { token: 'ETH', amount: '45,200 ETH', val: '$135.6M', pct: 54 },
                { token: 'USDC', amount: '68,000,000 USDC', val: '$68.0M', pct: 27 },
                { token: 'SOL', amount: '250,000 SOL', val: '$35.0M', pct: 14 },
              ].map((item) => (
                <div
                  key={item.token}
                  className="p-3 rounded-lg bg-slate-900 border border-slate-800/80 flex items-center justify-between hover:bg-slate-800/50 transition-colors"
                >
                  <div>
                    <p className="font-bold text-slate-200 text-xs">{item.token}</p>
                    <p className="text-[10px] text-slate-400">{item.amount}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-mono text-xs font-bold text-slate-100">{item.val}</p>
                    <p className="text-[10px] text-cyan-400">{item.pct}% of portfolio</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <button
            onClick={() => setInspectWallet(null)}
            className="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs transition-colors"
          >
            Close Profile
          </button>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
