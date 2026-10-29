import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Search,
  History,
  Shield,
} from 'lucide-react';
import { cn } from '../lib/utils.js';

const navigation = [
  { name: 'Workbench', href: '/', icon: LayoutDashboard },
  { name: 'New Investigation', href: '/investigate', icon: Search },
  { name: 'Saved Reports', href: '/history', icon: History },
];

export function Layout({ children }) {
  const location = useLocation();
  const isActive = (item) => location.pathname === item.href ||
    (item.href === '/history' && location.pathname.startsWith('/report/'));

  return (
    <div className="min-h-screen bg-[#f4f7fb] text-neutral-900">
      <aside className="fixed inset-y-0 left-0 z-50 hidden w-[264px] bg-[#0f172a] text-white shadow-2xl shadow-slate-950/15 md:block">
        <div className="flex h-full flex-col">
          <Link to="/" className="flex items-center gap-3 border-b border-white/10 px-6 py-5">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-300 text-[#0f172a]"><Shield className="h-5 w-5" /></span>
            <span><strong className="block text-sm tracking-[0.18em]">CYRAXI</strong><span className="mt-0.5 block text-[11px] text-white/50">RESEARCH WORKBENCH</span></span>
          </Link>
          <div className="px-5 pt-6"><p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-white/35">Workspace</p></div>
          <nav className="flex-1 space-y-1 px-3 py-3">
            {navigation.map((item) => (
              <Link key={item.name} to={item.href} className={cn(
                'group relative flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition-colors',
                isActive(item) ? 'bg-white/10 text-accent-200' : 'text-white/60 hover:bg-white/5 hover:text-white',
              )}>
                {isActive(item) && <span className="absolute bottom-2 left-0 top-2 w-0.5 rounded-full bg-accent-300" />}
                <item.icon className={cn('h-[18px] w-[18px]', isActive(item) ? 'text-accent-300' : 'text-white/40 group-hover:text-white/80')} />
                {item.name}
              </Link>
            ))}
          </nav>
          <div className="m-4 rounded-2xl border border-white/10 bg-white/[0.04] p-4">
            <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-accent-300" /><p className="text-xs font-semibold text-white/85">Experimental build</p></div>
            <p className="mt-2 text-[11px] leading-5 text-white/45">Archive-backed baselines. Availability depends on local data and graph services.</p>
          </div>
        </div>
      </aside>

      <header className="sticky top-0 z-40 border-b border-neutral-200 bg-[#f8fafc]/95 px-4 py-3 backdrop-blur md:hidden">
        <div className="flex items-center gap-2"><span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#0f172a] text-accent-300"><Shield className="h-4 w-4" /></span><strong className="text-xs tracking-[0.16em]">CYRAXI</strong><span className="text-xs text-neutral-500">Research workbench</span></div>
        <nav className="mt-3 flex gap-1 overflow-x-auto pb-0.5">
          {navigation.map((item) => <Link key={item.name} to={item.href} className={cn('flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium', isActive(item) ? 'bg-primary-100 text-primary-800' : 'text-neutral-600 hover:bg-neutral-100')}><item.icon className="h-3.5 w-3.5" />{item.name}</Link>)}
        </nav>
      </header>

      <main className="md:ml-[264px]">
        {children}
      </main>
    </div>
  );
}
