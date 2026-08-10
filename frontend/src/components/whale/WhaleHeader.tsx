import React from 'react';
import { Activity, Zap, BarChart2, TrendingUp, Shield, Volume2, VolumeX, Pause, Play } from 'lucide-react';

interface WhaleHeaderProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  soundEnabled: boolean;
  setSoundEnabled: (enabled: boolean) => void;
  isLive: boolean;
  setIsLive: (isLive: boolean) => void;
}

export const WhaleHeader: React.FC<WhaleHeaderProps> = ({
  activeTab,
  setActiveTab,
  soundEnabled,
  setSoundEnabled,
  isLive,
  setIsLive,
}) => {
  return (
    <header className="border-b border-slate-800/80 bg-[#0d111a]/80 backdrop-blur-xl sticky top-0 z-30 transition-all">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Logo & Live Pulse */}
        <div className="flex items-[#10b981] justify-center gap-3">
          <div className="p-2 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-600/20 border border-cyan-500/30 text-cyan-400 shadow-lg shadow-cyan-500/10">
            <Activity className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-wider bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
                WHALE<span className="text-cyan-400 font-extrabold">TRACKER</span>
                <span className="text-xs font-semibold px-2 py-0.5 ml-2 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-300">
                  PRO
                </span>
              </h1>
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                LIVE STREAM
              </div>
            </div>
            <p className="text-xs text-slate-400 hidden sm:block">
              Real-time multi-chain institutional flow & mega-whale alert terminal
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="hidden lg:flex items-center gap-1 p-1 rounded-xl bg-slate-900/80 border border-slate-800">
          {[
            { id: 'live', icon: Zap, label: 'Live Stream' },
            { id: 'visualizer', icon: BarChart2, label: 'Flow Visualizer' },
            { id: 'trends', icon: TrendingUp, label: 'Market Trends' },
            { id: 'entities', icon: Shield, label: 'Smart Money' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === tab.id
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <tab.icon className="w-3.5 h-3.5" /> {tab.label}
            </button>
          ))}
        </nav>

        {/* Quick Utility Toggles */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSoundEnabled(!soundEnabled)}
            title="Toggle Audio Alert Chime"
            className={`p-2 rounded-lg border transition-all ${
              soundEnabled
                ? 'bg-slate-800 border-slate-700 text-cyan-400'
                : 'bg-slate-900 border-slate-800 text-slate-500'
            }`}
          >
            {soundEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
          </button>

          <button
            onClick={() => setIsLive(!isLive)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all ${
              isLive
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20'
                : 'bg-amber-500/10 border-amber-500/30 text-amber-400 hover:bg-amber-500/20'
            }`}
          >
            {isLive ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            <span>{isLive ? 'Pause Feed' : 'Resume Feed'}</span>
          </button>
        </div>
      </div>
    </header>
  );
};
