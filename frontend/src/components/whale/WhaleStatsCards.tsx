import React from 'react';
import { DollarSign, Flame, TrendingUp, Cpu } from 'lucide-react';
import { formatUsd } from './constants';

interface WhaleStatsCardsProps {
  dashboardData: any;
}

export const WhaleStatsCards: React.FC<WhaleStatsCardsProps> = ({ dashboardData }) => {
  const total24hVolume = dashboardData?.total_volume_24h || 0;
  const megaTransactionsCount = dashboardData?.mega_moves_count || 0;
  const topToken = dashboardData?.top_asset || 'N/A';

  return (
    <section className="bg-[#0f1420] border-b border-slate-800/80 py-4 relative z-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 flex items-center justify-between hover:bg-slate-800/60 transition-colors">
          <div>
            <p className="text-[11px] font-medium text-slate-400 tracking-wider uppercase">Detected 24h Flow</p>
            <p className="text-xl font-black text-slate-100 tracking-tight mt-0.5">
              {formatUsd(total24hVolume)}
            </p>
          </div>
          <div className="p-2.5 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            <DollarSign className="w-5 h-5" />
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 flex items-center justify-between hover:bg-slate-800/60 transition-colors">
          <div>
            <p className="text-[11px] font-medium text-slate-400 tracking-wider uppercase">Mega Moves (&gt;$5M)</p>
            <p className="text-xl font-black text-amber-400 tracking-tight mt-0.5 flex items-center gap-1.5">
              {megaTransactionsCount}
              <span className="text-xs font-semibold text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
                +18%
              </span>
            </p>
          </div>
          <div className="p-2.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Flame className="w-5 h-5" />
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 flex items-center justify-between hover:bg-slate-800/60 transition-colors">
          <div>
            <p className="text-[11px] font-medium text-slate-400 tracking-wider uppercase">Top Accumulation</p>
            <p className="text-xl font-black text-emerald-400 tracking-tight mt-0.5">
              {topToken}
            </p>
          </div>
          <div className="p-2.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <TrendingUp className="w-5 h-5" />
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 flex items-center justify-between hover:bg-slate-800/60 transition-colors">
          <div>
            <p className="text-[11px] font-medium text-slate-400 tracking-wider uppercase">Network Telemetry</p>
            <div className="flex items-center gap-3 text-xs font-semibold mt-1">
              <span className="text-slate-300">
                <span className="text-slate-500">ETH Gas:</span> 14 Gwei
              </span>
              <span className="text-slate-300">
                <span className="text-slate-500">SOL TPS:</span> 2,840
              </span>
            </div>
          </div>
          <div className="p-2.5 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <Cpu className="w-5 h-5" />
          </div>
        </div>
      </div>
    </section>
  );
};
