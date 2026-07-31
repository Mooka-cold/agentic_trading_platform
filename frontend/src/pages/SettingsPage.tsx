import { useEffect, useState } from 'react';
import { Panel } from '@/components/shared/StatusBadge';
import { Button } from '@/components/ui/button';
import { LogOut, User, Key, Server, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';

export default function SettingsPage() {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    toast.success('Logged out successfully');
    navigate('/login');
  };

  return (
    <div className="space-y-6 animate-slide-in max-w-4xl mx-auto pb-10">
      <div>
        <h1 className="text-xl font-mono font-bold text-foreground">Settings & Account</h1>
        <p className="text-xs font-mono text-muted-foreground mt-0.5">Manage your terminal settings and subscription.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Panel title="Account Information">
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-secondary/50 rounded-full border border-border">
                <User className="h-5 w-5 text-primary" />
              </div>
              <div>
                <div className="text-sm font-mono text-foreground font-bold">Trader Profile</div>
                <div className="text-xs font-mono text-muted-foreground">Standard Tier</div>
              </div>
            </div>
            
            <div className="pt-4 border-t border-border space-y-2">
              <div className="flex justify-between items-center text-xs font-mono">
                <span className="text-muted-foreground">Status</span>
                <span className="text-success flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-success animate-pulse-glow" /> Active</span>
              </div>
              <div className="flex justify-between items-center text-xs font-mono">
                <span className="text-muted-foreground">Subscription</span>
                <span className="text-foreground">SaaS Pro (Monthly)</span>
              </div>
            </div>

            <Button variant="destructive" className="w-full mt-4 gap-2 text-xs font-mono" onClick={handleLogout}>
              <LogOut className="h-4 w-4" />
              Logout / Disconnect
            </Button>
          </div>
        </Panel>

        <Panel title="LLM Gateway Quota">
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-secondary/50 rounded-full border border-border">
                <Server className="h-5 w-5 text-primary" />
              </div>
              <div>
                <div className="text-sm font-mono text-foreground font-bold">Unified Gateway</div>
                <div className="text-xs font-mono text-muted-foreground">Managed by Platform</div>
              </div>
            </div>

            <div className="pt-4 border-t border-border space-y-3">
              <div>
                <div className="flex justify-between items-center text-xs font-mono mb-1">
                  <span className="text-muted-foreground">Monthly Tokens Used</span>
                  <span className="text-foreground">1.2M / 10M</span>
                </div>
                <div className="h-1.5 w-full bg-secondary rounded-full overflow-hidden">
                  <div className="h-full bg-primary" style={{ width: '12%' }} />
                </div>
              </div>
              
              <div className="text-[10px] text-muted-foreground font-mono bg-secondary/30 p-2 rounded border border-border mt-4">
                ℹ️ In the SaaS version, LLM API keys are managed globally by the platform. You do not need to provide your own OpenAI keys. The Gateway handles routing, load balancing, and rate limiting automatically.
              </div>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}
