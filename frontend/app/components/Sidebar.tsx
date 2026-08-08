'use client';

import Link from 'next/link';
import { useState } from 'react';

interface NavItem {
  id: string;
  label: string;
  href: string;
  icon: string;
}

const navItems: NavItem[] = [
  { id: '1', label: 'Dashboard', href: '/dashboard', icon: '📊' },
  { id: '2', label: 'Assessments', href: '/assessments', icon: '📝' },
  { id: '3', label: 'Analytics', href: '/analytics', icon: '📈' },
  { id: '4', label: 'Students', href: '/students', icon: '👥' },
  { id: '5', label: 'Settings', href: '/settings', icon: '⚙️' },
];

export default function Sidebar() {
  const [isOpen, setIsOpen] = useState(true);

  return (
    <aside
      className={`${
        isOpen ? 'w-64' : 'w-20'
      } bg-gradient-to-b from-slate-900 to-slate-800 text-white transition-all duration-300 ease-in-out min-h-screen flex flex-col shadow-lg`}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-6 border-b border-slate-700">
        {isOpen && (
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-500 rounded-lg flex items-center justify-center font-bold text-lg">
              FD
            </div>
            <h1 className="text-xl font-bold">Faculty</h1>
          </div>
        )}
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
        >
          {isOpen ? '←' : '→'}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-2">
        {navItems.map((item) => (
          <Link
            key={item.id}
            href={item.href}
            className="flex items-center gap-4 px-4 py-3 rounded-lg hover:bg-slate-700 transition-colors group relative"
          >
            <span className="text-xl">{item.icon}</span>
            {isOpen && <span className="font-medium">{item.label}</span>}
            {!isOpen && (
              <div className="absolute left-20 bg-slate-700 px-3 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap text-sm">
                {item.label}
              </div>
            )}
          </Link>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-slate-700">
        <div className="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-700 transition-colors cursor-pointer">
          <div className="w-10 h-10 bg-slate-600 rounded-full flex items-center justify-center">
            👤
          </div>
          {isOpen && (
            <div className="flex-1">
              <p className="font-medium text-sm">Dr. Jane Smith</p>
              <p className="text-xs text-slate-400">Faculty</p>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
