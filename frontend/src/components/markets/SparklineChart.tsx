'use client';

import React from 'react';

interface SparklineChartProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  isPositive?: boolean;
}

export default function SparklineChart({
  data,
  width = 120,
  height = 40,
  color,
  isPositive,
}: SparklineChartProps) {
  if (!data || data.length === 0) {
    return <div style={{ width, height }} className="bg-gray-800/50 rounded flex items-center justify-center text-xs text-gray-500">No data</div>;
  }

  // Auto-determine color if not provided based on first and last point
  const startPrice = data[0];
  const endPrice = data[data.length - 1];
  const calculatedIsPositive = isPositive !== undefined ? isPositive : endPrice >= startPrice;
  const strokeColor = color || (calculatedIsPositive ? '#10B981' : '#EF4444');

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1; // avoid division by zero

  const paddingY = 4;
  const innerHeight = height - paddingY * 2;

  const points = data.map((val, index) => {
    const x = (index / (data.length - 1)) * width;
    const y = height - paddingY - ((val - min) / range) * innerHeight;
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg width={width} height={height} className="overflow-visible">
      {/* Optional: Add gradient fill */}
      <defs>
        <linearGradient id={`gradient-${strokeColor}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={strokeColor} stopOpacity={0.2} />
          <stop offset="100%" stopColor={strokeColor} stopOpacity={0} />
        </linearGradient>
      </defs>
      
      {/* Filled Area */}
      <polygon
        points={`0,${height} ${points} ${width},${height}`}
        fill={`url(#gradient-${strokeColor})`}
      />
      
      {/* Stroke Line */}
      <polyline
        fill="none"
        stroke={strokeColor}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  );
}
