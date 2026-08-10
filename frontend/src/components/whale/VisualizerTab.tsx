import React from 'react';
import { BarChart2 } from 'lucide-react';
import { formatUsd } from './constants';

interface VisualizerTabProps {
  transactions: any[];
  setInspectTx: (tx: any) => void;
}

export const VisualizerTab: React.FC<VisualizerTabProps> = ({ transactions, setInspectTx }) => {
  return (
    <div className="p-6 rounded-2xl border border-slate-800/80 bg-[#0d111a] shadow-2xl space-y-4">
      <div>
        <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
          <BarChart2 className="w-5 h-5 text-cyan-400" />
          Whale Flow Scatter Visualizer
        </h3>
        <p className="text-xs text-slate-400">
          Bubble size represents transaction volume USD. Y-axis represents USD size, X-axis represents relative arrival time.
        </p>
      </div>

      <div className="relative h-96 w-full rounded-xl bg-slate-950 border border-slate-800/80 p-4 flex flex-col justify-between overflow-hidden">
        {/* Grid Lines */}
        <div className="absolute inset-0 grid grid-rows-4 grid-cols-6 border-slate-800/20 pointer-events-none">
          {[...Array(24)].map((_, i) => (
            <div key={i} className="border-b border-r border-slate-800/30"></div>
          ))}
        </div>

        {/* Y-Axis Scale Labels */}
        <div className="absolute left-3 top-3 text-[10px] font-mono text-slate-500">$50M+</div>
        <div className="absolute left-3 top-1/3 text-[10px] font-mono text-slate-500">$10M</div>
        <div className="absolute left-3 top-2/3 text-[10px] font-mono text-slate-500">$1M</div>

        {/* Plotted Bubbles */}
        <div className="relative w-full h-full">
          {transactions.map((tx, idx) => {
            const yPos = Math.max(10, Math.min(90, 100 - (tx.usdValue / 50000000) * 85));
            const xPos = Math.max(5, Math.min(92, 95 - (idx / transactions.length) * 88));
            const bubbleSize = Math.max(24, Math.min(64, (tx.usdValue / 50000000) * 50 + 20));

            const isBuy = tx.action === 'BUY';
            const isSell = tx.action === 'SELL';

            return (
              <div
                key={tx.id}
                onClick={() => setInspectTx(tx)}
                style={{
                  top: `${yPos}%`,
                  left: `${xPos}%`,
                  width: `${bubbleSize}px`,
                  height: `${bubbleSize}px`
                }}
                className={`absolute -translate-x-1/2 -translate-y-1/2 rounded-full cursor-pointer transition-all duration-300 hover:scale-125 hover:z-20 flex items-center justify-center border shadow-lg ${
                  isBuy
                    ? 'bg-emerald-500/30 border-emerald-400 text-emerald-200 shadow-emerald-500/20'
                    : isSell
                    ? 'bg-rose-500/30 border-rose-400 text-rose-200 shadow-rose-500/20'
                    : 'bg-cyan-500/30 border-cyan-400 text-cyan-200 shadow-cyan-500/20'
                }`}
                title={`${tx.token}: ${formatUsd(tx.usdValue)} (${tx.fromEntity} -> ${tx.toEntity})`}
              >
                <span className="text-[9px] font-black tracking-tighter truncate px-1">
                  {tx.token}
                </span>
              </div>
            );
          })}
        </div>

        {/* X-Axis Footer */}
        <div className="flex justify-between text-[10px] font-mono text-slate-500 pt-2 border-t border-slate-800">
          <span>Older Activity</span>
          <span>Real-time Streams ➔</span>
        </div>
      </div>
    </div>
  );
};
