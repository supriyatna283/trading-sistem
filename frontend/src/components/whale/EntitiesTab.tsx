import React from 'react';
import { Shield } from 'lucide-react';
import { formatUsd, ENTITY_BADGES } from './constants';

interface EntitiesTabProps {
  dashboardData: any;
  setInspectWallet: (wallet: any) => void;
}

export const EntitiesTab: React.FC<EntitiesTabProps> = ({ dashboardData, setInspectWallet }) => {
  return (
    <div className="p-6 rounded-2xl border border-slate-800/80 bg-[#0d111a] shadow-2xl space-y-4">
      <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
        <Shield className="w-5 h-5 text-indigo-400" />
        Tracked Smart Money Entities & Institutional Profiles
      </h3>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {(dashboardData?.top_entities
          ? dashboardData.top_entities.map((e: any) => {
              let rating = 'Active Entity';
              if (e.type === 'exchange') rating = 'High Liquidity';
              else if (e.type === 'market_maker') rating = 'High Frequency';
              else if (e.type === 'whale') rating = 'High Impact';

              return {
                name: e.name,
                type: e.type.replace('_', ' ').toUpperCase(),
                volume: formatUsd(e.volume) + ' 24h',
                rating: rating,
                badge: e.type,
              };
            })
          : []
        ).map((entity: any) => (
          <div
            key={entity.name}
            onClick={() => setInspectWallet({ name: entity.name, type: entity.badge, address: '0x71C...88B1' })}
            className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-cyan-500/50 cursor-pointer transition-all space-y-2 group"
          >
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-200 text-sm group-hover:text-cyan-300">
                {entity.name}
              </span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${ENTITY_BADGES[entity.badge]?.bg || ENTITY_BADGES.unknown.bg}`}>
                {ENTITY_BADGES[entity.badge]?.label || ENTITY_BADGES.unknown.label}
              </span>
            </div>
            <div className="flex justify-between text-xs text-slate-400">
              <span>
                24h Flow: <strong className="text-slate-200">{entity.volume}</strong>
              </span>
              <span className="text-cyan-400">{entity.rating}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
