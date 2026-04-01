import { NavLink } from '@/components/NavLink';
import { useLocation } from 'react-router-dom';
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from '@/components/ui/sidebar';
import {
  LayoutDashboard,
  GitBranch,
  Orbit,
  FileSearch,
  Brain,
  Activity,
  Settings,
  ChartCandlestick,
} from 'lucide-react';

const navItems = [
  { title: 'Overview', url: '/', icon: LayoutDashboard },
  { title: 'Dashboard', url: '/dashboard', icon: ChartCandlestick },
  { title: 'Swarm', url: '/swarm', icon: Orbit },
  { title: 'Portfolio', url: '/portfolio', icon: Activity },
  { title: 'Session', url: '/session', icon: FileSearch },
  { title: 'Reflection', url: '/reflection', icon: Brain },
  { title: 'Orchestration', url: '/orchestration', icon: GitBranch },
  { title: 'Settings', url: '/settings', icon: Settings },
];

export function AppSidebar() {
  const { state } = useSidebar();
  const collapsed = state === 'collapsed';
  const location = useLocation();

  return (
    <Sidebar collapsible="icon" className="border-r border-border">
      <SidebarContent>
        <div className={`px-4 py-4 border-b border-border ${collapsed ? 'px-2' : ''}`}>
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-primary shrink-0" />
            {!collapsed && (
              <div>
                <h1 className="text-sm font-mono font-bold text-primary text-glow">AGENT TRADE</h1>
                <p className="text-[10px] font-mono text-muted-foreground">Multi-Agent Trading System</p>
              </div>
            )}
          </div>
        </div>

        <SidebarGroup>
          <SidebarGroupLabel className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest">
            Navigation
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild>
                    <NavLink
                      to={item.url}
                      end={item.url === '/'}
                      className="hover:bg-secondary/50 text-muted-foreground"
                      activeClassName="bg-primary/10 text-primary font-medium"
                    >
                      <item.icon className="mr-2 h-4 w-4 shrink-0" />
                      {!collapsed && <span className="text-sm">{item.title}</span>}
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {!collapsed && (
          <div className="mt-auto p-4 border-t border-border">
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-success animate-pulse-glow" />
              <span className="text-xs font-mono text-muted-foreground">System Online</span>
            </div>
            <p className="text-[10px] font-mono text-muted-foreground mt-1">v0.1.0 · Open Source</p>
          </div>
        )}
      </SidebarContent>
    </Sidebar>
  );
}
