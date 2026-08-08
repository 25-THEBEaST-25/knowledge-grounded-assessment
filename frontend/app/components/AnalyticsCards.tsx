'use client';

import React from 'react';

interface AnalyticsCard {
  id: string;
  title: string;
  value: string | number;
  subtitle?: string;
  icon: string;
  bgColor: string;
  trend?: {
    direction: 'up' | 'down';
    percentage: number;
  };
}

const analyticsData: AnalyticsCard[] = [
  {
    id: '1',
    title: 'Total Assessments',
    value: 24,
    subtitle: 'Active assessments',
    icon: '📋',
    bgColor: 'from-blue-50 to-blue-100',
    trend: { direction: 'up', percentage: 12 },
  },
  {
    id: '2',
    title: 'Student Submissions',
    value: 187,
    subtitle: 'This semester',
    icon: '📨',
    bgColor: 'from-green-50 to-green-100',
    trend: { direction: 'up', percentage: 8 },
  },
  {
    id: '3',
    title: 'Average Score',
    value: '78.5%',
    subtitle: 'Class performance',
    icon: '📊',
    bgColor: 'from-purple-50 to-purple-100',
    trend: { direction: 'up', percentage: 5 },
  },
  {
    id: '4',
    title: 'Pending Reviews',
    value: 12,
    subtitle: 'Awaiting feedback',
    icon: '⏳',
    bgColor: 'from-orange-50 to-orange-100',
    trend: { direction: 'down', percentage: 3 },
  },
];

export default function AnalyticsCards() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {analyticsData.map((card) => (
        <div
          key={card.id}
          className={`bg-gradient-to-br ${card.bgColor} rounded-xl shadow-md p-6 border border-opacity-20 hover:shadow-lg transition-shadow`}
        >
          {/* Header */}
          <div className="flex items-start justify-between mb-4">
            <div className="text-4xl">{card.icon}</div>
            {card.trend && (
              <div
                className={`flex items-center gap-1 text-sm font-semibold ${
                  card.trend.direction === 'up'
                    ? 'text-green-600'
                    : 'text-red-600'
                }`}
              >
                {card.trend.direction === 'up' ? '↑' : '↓'}
                {card.trend.percentage}%
              </div>
            )}
          </div>

          {/* Title */}
          <h3 className="text-slate-600 text-sm font-medium mb-2 uppercase tracking-wide">
            {card.title}
          </h3>

          {/* Value */}
          <p className="text-3xl font-bold text-slate-900 mb-1">{card.value}</p>

          {/* Subtitle */}
          {card.subtitle && (
            <p className="text-slate-600 text-sm">{card.subtitle}</p>
          )}

          {/* Bottom accent */}
          <div className="mt-4 pt-4 border-t border-opacity-30 border-slate-300">
            <p className="text-xs text-slate-600 hover:text-slate-900 transition-colors cursor-pointer font-medium">
              View Details →
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
