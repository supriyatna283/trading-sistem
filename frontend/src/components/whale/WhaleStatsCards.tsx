import React from 'react';
import { DollarSign, Flame, TrendingUp, Cpu, Bot } from 'lucide-react';
import { motion } from 'framer-motion';
import { formatUsd } from './constants';

interface WhaleStatsCardsProps {
  dashboardData: any;
}

export const WhaleStatsCards: React.FC<WhaleStatsCardsProps> = ({ dashboardData }) => {
  const total24hVolume = dashboardData?.total_volume_24h || 0;
  const megaTransactionsCount = dashboardData?.mega_moves_count || 0;
  const topToken = dashboardData?.top_asset || 'N/A';

  return (
    <section className="bg-slate-950/50 backdrop-blur-xl border-b border-slate-800/60 pb-6 pt-4 relative z-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 grid grid-cols-2 md:grid-cols-4 gap-4">
        
        <div className="p-4 rounded-2xl bg-gradient-to-b from-slate-800/40 to-slate-900/40 backdrop-blur-md border border-slate-700/50 flex items-center justify-between hover:border-cyan-500/30 hover:shadow-[0_0_15px_rgba(6,182,212,0.15)] transition-all group">
          <div>
            <p className="text-[10px] font-bold text-slate-400 tracking-widest uppercase">Detected 24h Flow</p>
            <p className="text-2xl font-black text-white tracking-tight mt-1 group-hover:text-cyan-400 transition-colors">
              {formatUsd(total24hVolume)}
            </p>
          </div>
          <div className="p-3 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-600/20 text-cyan-400 border border-cyan-500/20 shadow-lg shadow-cyan-500/10">
            <DollarSign className="w-6 h-6" />
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-gradient-to-b from-slate-800/40 to-slate-900/40 backdrop-blur-md border border-slate-700/50 flex items-center justify-between hover:border-amber-500/30 hover:shadow-[0_0_15px_rgba(245,158,11,0.15)] transition-all group">
          <div>
            <p className="text-[10px] font-bold text-slate-400 tracking-widest uppercase">Mega Moves (&gt;$5M)</p>
            <p className="text-2xl font-black text-white tracking-tight mt-1 flex items-center gap-2 group-hover:text-amber-400 transition-colors">
              {megaTransactionsCount}
              <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                +18%
              </span>
            </p>
          </div>
          <div className="p-3 rounded-xl bg-gradient-to-br from-amber-500/20 to-orange-600/20 text-amber-400 border border-amber-500/20 shadow-lg shadow-amber-500/10">
            <Flame className="w-6 h-6" />
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-gradient-to-b from-slate-800/40 to-slate-900/40 backdrop-blur-md border border-slate-700/50 flex items-center justify-between hover:border-emerald-500/30 hover:shadow-[0_0_15px_rgba(16,185,129,0.15)] transition-all group">
          <div>
            <p className="text-[10px] font-bold text-slate-400 tracking-widest uppercase">Top Accumulation</p>
            <p className="text-2xl font-black text-white tracking-tight mt-1 group-hover:text-emerald-400 transition-colors">
              {topToken}
            </p>
          </div>
          <div className="p-3 rounded-xl bg-gradient-to-br from-emerald-500/20 to-teal-600/20 text-emerald-400 border border-emerald-500/20 shadow-lg shadow-emerald-500/10">
            <TrendingUp className="w-6 h-6" />
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-gradient-to-b from-slate-800/40 to-slate-900/40 backdrop-blur-md border border-slate-700/50 flex items-center justify-between hover:border-purple-500/30 hover:shadow-[0_0_15px_rgba(168,85,247,0.15)] transition-all group">
          <div>
            <p className="text-[10px] font-bold text-slate-400 tracking-widest uppercase">Network Telemetry</p>
            <div className="flex flex-col gap-0.5 text-[11px] font-semibold mt-1">
              <span className="text-slate-200">
                <span className="text-slate-500">ETH Gas:</span> 14 Gwei
              </span>
              <span className="text-slate-200">
                <span className="text-slate-500">SOL TPS:</span> 2,840
              </span>
            </div>
          </div>
          <div className="p-3 rounded-xl bg-gradient-to-br from-purple-500/20 to-fuchsia-600/20 text-purple-400 border border-purple-500/20 shadow-lg shadow-purple-500/10">
            <Cpu className="w-6 h-6" />
          </div>
        </div>
      </div>
      
      {/* AI Narrative Banner */}
      {dashboardData?.ai_narrative && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-5">
          <div className="rounded-2xl border border-indigo-500/40 bg-gradient-to-r from-indigo-900/40 via-purple-900/20 to-indigo-900/40 backdrop-blur-xl p-5 flex items-start gap-4 relative overflow-hidden shadow-[0_0_30px_rgba(99,102,241,0.1)]">
            
            {/* Animated glow effect in background */}
            <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0 pointer-events-none">
                <div className="absolute -top-[50%] -left-[10%] w-[40%] h-[200%] bg-indigo-500/10 rotate-12 blur-3xl rounded-full"></div>
                <div className="absolute top-[20%] -right-[10%] w-[30%] h-[150%] bg-purple-500/10 -rotate-12 blur-3xl rounded-full"></div>
            </div>

            <div className="p-2.5 bg-gradient-to-br from-indigo-500/30 to-purple-600/30 text-indigo-300 rounded-xl shrink-0 mt-0.5 border border-indigo-400/30 shadow-lg shadow-indigo-500/20 relative z-10">
              <Bot className="w-6 h-6" />
            </div>
            <div className="flex-1 relative z-10">
              <h4 className="text-xs font-black tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-indigo-300 to-purple-300 mb-1.5 flex items-center gap-2 uppercase">
                NVIDIA Nemotron Insight 
                <span className="relative flex h-2.5 w-2.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,0.8)]"></span>
                </span>
              </h4>
              <motion.p 
                key={dashboardData.ai_narrative} 
                initial={{ opacity: 0, y: 5 }} 
                animate={{ opacity: 1, y: 0 }} 
                className="text-[15px] leading-relaxed font-medium text-indigo-100"
              >
                {dashboardData.ai_narrative}
              </motion.p>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};
