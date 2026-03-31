import { SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar';
import { AppSidebar } from './AppSidebar';
import { Search } from 'lucide-react';
import { useState } from 'react';

export function AppLayout({ children }: { children: React.ReactNode }) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full bg-background">
        <AppSidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <header className="h-11 flex items-center border-b border-border px-3 gap-3 bg-card/50 backdrop-blur shrink-0">
            <SidebarTrigger className="text-muted-foreground hover:text-foreground" />
            <div className="flex-1" />
            <div className="relative">
              {searchOpen ? (
                <input
                  autoFocus
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onBlur={() => { setSearchOpen(false); setSearchQuery(''); }}
                  placeholder="Search session, symbol, agent..."
                  className="w-64 h-7 px-3 text-xs font-mono bg-secondary border border-border rounded text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                />
              ) : (
                <button onClick={() => setSearchOpen(true)} className="flex items-center gap-1.5 text-xs font-mono text-muted-foreground hover:text-foreground transition-colors">
                  <Search className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">Search</span>
                  <kbd className="hidden sm:inline px-1.5 py-0.5 text-[10px] bg-secondary rounded border border-border">⌘K</kbd>
                </button>
              )}
            </div>
          </header>
          <main className="flex-1 overflow-auto p-4 lg:p-6 scrollbar-thin">
            {children}
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}
