"use client";

import React from 'react';
import { 
  LayoutDashboard, 
  BrainCircuit, 
  History, 
  Settings, 
  User, 
  LogOut, 
  Cpu
} from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export const SideNav = () => {
  const pathname = usePathname();

  return (
    <div className="flex flex-col items-center h-full w-full py-6 gap-6">
      {/* Brand Logo */}
      <div className="w-10 h-10 bg-blue-500 rounded-xl flex items-center justify-center text-white font-bold shadow-lg shadow-blue-500/20 mb-4 shrink-0">
        AI
      </div>

      <nav className="flex flex-col gap-4 w-full items-center flex-1">
        <NavItem href="/" icon={<LayoutDashboard size={20} />} active={pathname === '/'} label="Dashboard" />
        <NavItem href="/agents" icon={<Cpu size={20} />} active={pathname === '/agents'} label="Agents Swarm" />
        <NavItem href="/history" icon={<History size={20} />} active={pathname === '/history'} label="History" />
        
        <div className="w-8 h-px bg-slate-800 my-2"></div>
        
        <NavItem href="/strategy" icon={<BrainCircuit size={20} />} active={pathname === '/strategy'} label="Strategy Lab" />
        <NavItem href="/profile" icon={<User size={20} />} active={pathname === '/profile'} label="Profile" />
        <NavItem href="/settings" icon={<Settings size={20} />} active={pathname === '/settings'} label="Settings" />
      </nav>

      <div className="mt-auto">
        <button className="w-10 h-10 rounded-xl flex items-center justify-center text-slate-400 hover:text-red-500 hover:bg-slate-800 transition-all">
          <LogOut size={20} />
        </button>
      </div>
    </div>
  );
};

const NavItem = ({ href, icon, active, label }: { href: string, icon: React.ReactNode, active: boolean, label: string }) => (
  <Link href={href}>
    <div 
      title={label}
      className={`
        w-10 h-10 rounded-xl flex items-center justify-center transition-all cursor-pointer
        ${active ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20' : 'text-slate-400 hover:bg-slate-800 hover:text-white'}
      `}
    >
      {icon}
    </div>
  </Link>
);
