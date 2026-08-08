'use client';

import React, { useState, useEffect } from 'react';
import { useWhaleSocket } from '@/lib/hooks/useWhaleSocket';
import WhaleFeed from '@/components/whale/WhaleFeed';
import WhaleHistoryChart, { HistoryData } from '@/components/whale/WhaleHistoryChart';
import WhaleFilters from '@/components/whale/WhaleFilters';
import { Activity, BarChart2, Radio } from 'lucide-react';

export default function WhaleTrackerPage() {
    const [activeTab, setActiveTab] = useState<'live' | 'history'>('live');
    const [chainFilter, setChainFilter] = useState('all');
    const [minUsdFilter, setMinUsdFilter] = useState('10000');
    const [entityFilter, setEntityFilter] = useState('all');
    
    const [historyData, setHistoryData] = useState<HistoryData[]>([]);
    const [loadingHistory, setLoadingHistory] = useState(false);

    // Determine API URL based on environment variables
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const WS_URL = API_BASE.replace(/^http/, 'ws') + '/ws/whale';
    const API_URL = API_BASE + '/api';

    const { transactions, isConnected, setInitialTransactions } = useWhaleSocket(WS_URL);

    // Fetch initial live data
    useEffect(() => {
        if (activeTab !== 'live') return;

        const fetchLive = async () => {
            try {
                const params = new URLSearchParams({
                    limit: '50'
                });
                if (chainFilter !== 'all') params.append('chain', chainFilter);

                const res = await fetch(`${API_URL}/whale/live?${params.toString()}`);
                if (res.ok) {
                    const data = await res.json();
                    setInitialTransactions(data);
                }
            } catch (error) {
                console.error("Failed to fetch live whales", error);
            }
        };

        fetchLive();
    }, [activeTab, chainFilter, setInitialTransactions, API_URL]);

    // Fetch history data
    useEffect(() => {
        if (activeTab !== 'history') return;

        const fetchHistory = async () => {
            setLoadingHistory(true);
            try {
                const params = new URLSearchParams({
                    days: '7',
                    min_usd: minUsdFilter
                });
                if (chainFilter !== 'all') params.append('chain', chainFilter);
                if (entityFilter !== 'all') params.append('entity_type', entityFilter);

                const res = await fetch(`${API_URL}/whale/history?${params.toString()}`);
                if (res.ok) {
                    const data = await res.json();
                    setHistoryData(data);
                }
            } catch (error) {
                console.error("Failed to fetch history data", error);
            } finally {
                setLoadingHistory(false);
            }
        };

        fetchHistory();
    }, [activeTab, chainFilter, minUsdFilter, entityFilter, API_URL]);

    // Filter live transactions locally based on selected filters
    const filteredTransactions = transactions.filter(tx => {
        if (chainFilter !== 'all' && tx.chain_id !== chainFilter) return false;
        if (tx.usd_value < parseFloat(minUsdFilter)) return false;
        if (entityFilter !== 'all') {
            const fromMatch = tx.from_wallet?.entity_type === entityFilter;
            const toMatch = tx.to_wallet?.entity_type === entityFilter;
            if (!fromMatch && !toMatch) return false;
        }
        return true;
    });

    return (
        <div className="min-h-screen bg-[#0B0E11] text-gray-300 p-4 md:p-8">
            <div className="max-w-7xl mx-auto space-y-6">
                
                {/* Header Section */}
                <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4 mb-8">
                    <div>
                        <h1 className="text-3xl font-bold text-white font-sans flex items-center gap-3">
                            Whale Tracker 
                            {isConnected ? (
                                <span className="flex items-center gap-1.5 text-xs font-mono bg-[#00D97E]/10 text-[#00D97E] px-2 py-1 rounded-full border border-[#00D97E]/20">
                                    <span className="relative flex h-2 w-2">
                                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00D97E] opacity-75"></span>
                                      <span className="relative inline-flex rounded-full h-2 w-2 bg-[#00D97E]"></span>
                                    </span>
                                    LIVE
                                </span>
                            ) : (
                                <span className="flex items-center gap-1.5 text-xs font-mono bg-red-500/10 text-red-500 px-2 py-1 rounded-full border border-red-500/20">
                                    <Radio size={12} />
                                    DISCONNECTED
                                </span>
                            )}
                        </h1>
                        <p className="text-gray-500 mt-2 text-sm font-sans">
                            Real-time on-chain detection for massive multi-chain movements.
                        </p>
                    </div>

                    {/* Tabs */}
                    <div className="flex bg-[#151A21] border border-gray-800 rounded-lg p-1 shadow-lg">
                        <button
                            onClick={() => setActiveTab('live')}
                            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
                                activeTab === 'live'
                                    ? 'bg-gray-800 text-white shadow'
                                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
                            }`}
                        >
                            <Activity size={16} />
                            Live Feed
                        </button>
                        <button
                            onClick={() => setActiveTab('history')}
                            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
                                activeTab === 'history'
                                    ? 'bg-gray-800 text-white shadow'
                                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
                            }`}
                        >
                            <BarChart2 size={16} />
                            Historical Trends
                        </button>
                    </div>
                </div>

                <WhaleFilters 
                    chainFilter={chainFilter}
                    setChainFilter={setChainFilter}
                    minUsdFilter={minUsdFilter}
                    setMinUsdFilter={setMinUsdFilter}
                    entityFilter={entityFilter}
                    setEntityFilter={setEntityFilter}
                />

                <div className="mt-6">
                    {activeTab === 'live' ? (
                        <WhaleFeed transactions={filteredTransactions} />
                    ) : (
                        <WhaleHistoryChart data={historyData} loading={loadingHistory} />
                    )}
                </div>

            </div>
        </div>
    );
}
