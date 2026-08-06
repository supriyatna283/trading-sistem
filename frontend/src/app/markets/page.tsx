import React from 'react';
import MainLayout from '@/components/MainLayout';
import MarketTable from '@/components/markets/MarketTable';
import { ArrowTrendingUpIcon } from '@heroicons/react/24/outline';

export const metadata = {
  title: 'Live Markets | Trading Intelligence',
  description: 'Real-time cryptocurrency market screener and live ticker.',
};

export default function MarketsPage() {
  const [status, setStatus] = React.useState<'LIVE' | 'DEGRADED'>('LIVE');

  return (
    <MainLayout>
      <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500 pb-12">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-emerald-500/20 text-emerald-400 rounded-lg">
                <ArrowTrendingUpIcon className="w-6 h-6" />
              </div>
              <h1 className="text-3xl font-bold tracking-tight text-white">Live Markets</h1>
            </div>
            <p className="text-gray-400 max-w-2xl text-sm md:text-base">
              Real-time cryptocurrency market screener powered by Binance WebSockets.
              Ranking is determined by global Market Cap.
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            {status === 'LIVE' ? (
              <div className="flex items-center gap-2 text-xs font-medium text-emerald-400 bg-emerald-500/10 px-3 py-1.5 rounded-full border border-emerald-500/20">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                Live WebSocket Connected
              </div>
            ) : (
              <div className="flex items-center gap-2 text-xs font-medium text-amber-400 bg-amber-500/10 px-3 py-1.5 rounded-full border border-amber-500/20">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
                </span>
                Degraded (REST Polling)
              </div>
            )}
          </div>
        </div>

        {/* Main Content */}
        <div className="relative">
          {/* Subtle background glow */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-3xl h-64 bg-emerald-500/10 blur-[120px] rounded-full pointer-events-none" />
          
          <MarketTable onStatusChange={setStatus} />
        </div>
      </div>
    </MainLayout>
  );
}
