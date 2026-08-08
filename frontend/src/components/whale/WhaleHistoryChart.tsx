'use client';

import React, { useMemo } from 'react';
import { 
    BarChart, 
    Bar, 
    XAxis, 
    YAxis, 
    CartesianGrid, 
    Tooltip, 
    ResponsiveContainer,
    LineChart,
    Line,
    ComposedChart
} from 'recharts';

export interface HistoryData {
    date: string;
    volume: number;
    tx_count: number;
}

interface WhaleHistoryChartProps {
    data: HistoryData[];
    loading?: boolean;
}

const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
        return (
            <div className="bg-[#151A21] border border-gray-700 p-3 rounded shadow-lg font-sans">
                <p className="text-gray-300 font-medium mb-2">{label}</p>
                <div className="flex flex-col gap-1">
                    <p className="text-sm">
                        <span className="text-gray-400">Volume: </span>
                        <span className="text-[#5B8DEF] font-bold">
                            ${(payload[0].value / 1000000).toFixed(2)}M
                        </span>
                    </p>
                    <p className="text-sm">
                        <span className="text-gray-400">Transactions: </span>
                        <span className="text-[#00D97E] font-bold">
                            {payload[1].value}
                        </span>
                    </p>
                </div>
            </div>
        );
    }
    return null;
};

export default function WhaleHistoryChart({ data, loading = false }: WhaleHistoryChartProps) {
    const formatYAxis = (value: number) => {
        return `$${(value / 1000000).toFixed(0)}M`;
    };

    if (loading) {
        return (
            <div className="bg-[#151A21] border border-gray-800 rounded-xl h-[400px] flex items-center justify-center shadow-xl">
                <div className="text-gray-500 font-mono animate-pulse">Loading historical data...</div>
            </div>
        );
    }

    if (!data || data.length === 0) {
        return (
            <div className="bg-[#151A21] border border-gray-800 rounded-xl h-[400px] flex items-center justify-center shadow-xl">
                <div className="text-gray-500 font-mono">No historical data available for selected filters.</div>
            </div>
        );
    }

    return (
        <div className="bg-[#151A21] border border-gray-800 rounded-xl p-6 shadow-xl h-[400px]">
            <h3 className="text-white font-sans font-medium mb-4">Whale Volume Trends</h3>
            <div className="w-full h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={data} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#2D3748" vertical={false} />
                        <XAxis 
                            dataKey="date" 
                            stroke="#718096" 
                            tick={{ fill: '#718096', fontSize: 12, fontFamily: 'monospace' }}
                            tickMargin={10}
                            axisLine={false}
                            tickLine={false}
                        />
                        <YAxis 
                            yAxisId="left"
                            stroke="#718096" 
                            tick={{ fill: '#718096', fontSize: 12, fontFamily: 'monospace' }}
                            tickFormatter={formatYAxis}
                            axisLine={false}
                            tickLine={false}
                        />
                        <YAxis 
                            yAxisId="right" 
                            orientation="right" 
                            stroke="#718096"
                            tick={{ fill: '#718096', fontSize: 12, fontFamily: 'monospace' }}
                            axisLine={false}
                            tickLine={false}
                        />
                        <Tooltip content={<CustomTooltip />} cursor={{ fill: '#2D3748', opacity: 0.4 }} />
                        <Bar 
                            yAxisId="left" 
                            dataKey="volume" 
                            fill="#5B8DEF" 
                            radius={[4, 4, 0, 0]} 
                            barSize={30}
                        />
                        <Line 
                            yAxisId="right" 
                            type="monotone" 
                            dataKey="tx_count" 
                            stroke="#00D97E" 
                            strokeWidth={3}
                            dot={{ fill: '#00D97E', r: 4, strokeWidth: 0 }}
                            activeDot={{ r: 6, fill: '#00D97E', stroke: '#151A21', strokeWidth: 2 }}
                        />
                    </ComposedChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
