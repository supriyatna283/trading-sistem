'use client';

import React from 'react';
import { Filter } from 'lucide-react';

interface WhaleFiltersProps {
    chainFilter: string;
    setChainFilter: (chain: string) => void;
    minUsdFilter: string;
    setMinUsdFilter: (usd: string) => void;
    entityFilter: string;
    setEntityFilter: (entity: string) => void;
    disabled?: boolean;
}

export default function WhaleFilters({
    chainFilter,
    setChainFilter,
    minUsdFilter,
    setMinUsdFilter,
    entityFilter,
    setEntityFilter,
    disabled = false
}: WhaleFiltersProps) {
    return (
        <div className="bg-[#151A21] border border-gray-800 rounded-xl p-4 flex flex-col md:flex-row gap-4 items-center shadow-xl">
            <div className="flex items-center gap-2 text-gray-400 font-sans mr-4">
                <Filter size={18} />
                <span className="font-medium text-sm">Filters</span>
            </div>
            
            <div className="flex gap-2">
                {['all', 'ethereum', 'bsc', 'solana'].map((chain) => (
                    <button
                        key={chain}
                        disabled={disabled}
                        onClick={() => setChainFilter(chain)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-colors ${
                            chainFilter === chain 
                                ? 'bg-[#5B8DEF] text-white shadow-[0_0_10px_rgba(91,141,239,0.3)]' 
                                : 'bg-gray-800/50 text-gray-400 hover:bg-gray-700 hover:text-gray-200'
                        } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                        {chain}
                    </button>
                ))}
            </div>

            <div className="flex-1"></div>

            <div className="flex items-center gap-4 text-sm font-sans w-full md:w-auto">
                <div className="flex items-center gap-2 w-full md:w-auto">
                    <label className="text-gray-400 text-xs whitespace-nowrap">Min Value:</label>
                    <select
                        disabled={disabled}
                        value={minUsdFilter}
                        onChange={(e) => setMinUsdFilter(e.target.value)}
                        className="bg-gray-800/50 border border-gray-700 text-white rounded-lg px-3 py-1.5 focus:outline-none focus:border-[#5B8DEF] transition-colors appearance-none w-full md:w-auto cursor-pointer"
                    >
                        <option value="100000">$100k+</option>
                        <option value="500000">$500k+</option>
                        <option value="1000000">$1M+</option>
                        <option value="5000000">$5M+</option>
                    </select>
                </div>

                <div className="flex items-center gap-2 w-full md:w-auto">
                    <label className="text-gray-400 text-xs whitespace-nowrap">Entity:</label>
                    <select
                        disabled={disabled}
                        value={entityFilter}
                        onChange={(e) => setEntityFilter(e.target.value)}
                        className="bg-gray-800/50 border border-gray-700 text-white rounded-lg px-3 py-1.5 focus:outline-none focus:border-[#5B8DEF] transition-colors appearance-none w-full md:w-auto cursor-pointer"
                    >
                        <option value="all">All Entities</option>
                        <option value="exchange">Exchanges</option>
                        <option value="fund">Funds</option>
                        <option value="whale">Whales</option>
                        <option value="unlabeled">Unlabeled</option>
                    </select>
                </div>
            </div>
        </div>
    );
}
