import React from 'react';
import { PieChart, TrendingUp } from 'lucide-react';
import { formatUsd } from './constants';

interface TrendsTabProps {
  dashboardData: any;
}

export const TrendsTab: React.FC<TrendsTabProps> = ({ dashboardData }) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div className="p-6 rounded-2xl border border-slate-800/80 bg-[#0d111a] shadow-2xl space-y-4">
        <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
          <PieChart className="w-4 h-4 text-cyan-400" />
          Chain Volume Breakdown
        </h3>
        <div className="space-y-3">
          {(dashboardData?.chain_breakdown
            ? Object.entries(dashboardData.chain_breakdown).map(([chain, data]: any) => {
                const colors: any = {
                  ethereum: 'bg-indigo-500',
                  solana: 'bg-purple-500',
                  bsc: 'bg-amber-500',
                  base: 'bg-blue-500',
                  arbitrum: 'bg-cyan-500',
                };
                return {
                  chain: chain.toUpperCase(),
                  pct: data.percentage,
                  val: formatUsd(data.volume),
                  color: colors[chain] || 'bg-slate-500',
                };
              })
            : []
          ).map((c) => (
            <div key={c.chain} className="space-y-1">
              <div className="flex justify-between text-xs font-semibold text-slate-300">
                <span>{c.chain}</span>
                <span className="font-mono">
                  {c.val} ({c.pct}%)
                </span>
              </div>
              <div className="w-full h-2 rounded-full bg-slate-900 overflow-hidden">
                <div
                  className={`h-full ${c.color}`}
                  style={{ width: `${c.pct}%` }}
                ></div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="p-6 rounded-2xl border border-slate-800/80 bg-[#0d111a] shadow-2xl space-y-4">
        <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-emerald-400" />
          Institutional Net Flow Bias
        </h3>
        <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-400">24h Net Exchange Inflow / Outflow</p>
              <p className="text-lg font-bold text-emerald-400 mt-0.5">
                {dashboardData?.net_flow_bias?.description || 'Loading...'}
              </p>
            </div>
            <span className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold text-xs">
              {dashboardData?.net_flow_bias?.label || 'LOADING'}
            </span>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Real-time calculation of net exchange flows based on on-chain transactions exceeding minimum tracking thresholds.
          </p>
        </div>
      </div>
    </div>
  );
};
