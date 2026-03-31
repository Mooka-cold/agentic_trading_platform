import { Panel, StatusBadge } from '@/components/shared/StatusBadge';
import { cn } from '@/lib/utils';
import type { ReflectionEntry, RuleChange } from '@/types';
import { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { fetchSessions, fetchSessionDetail } from '@/data/api';

export default function ReflectionPage() {
  const [reflections, setReflections] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadReflections() {
      try {
        const history = await fetchSessions();
        const top10 = history.slice(0, 10);
        
        const refs = [];
        for (const sess of top10) {
          const detail = await fetchSessionDetail(sess.id);
          const reflectionLog = detail.logs.find((l: any) => l.agent_id === 'reflector' && l.artifact?.type === 'REFLECTION');
          if (reflectionLog) {
            try {
              const content = JSON.parse(reflectionLog.artifact.content);
              refs.push({
                id: reflectionLog.id,
                sessionId: sess.id,
                symbol: sess.symbol,
                sessionStatus: sess.status,
                whatWentRight: content.what_went_right || [],
                whatWentWrong: content.what_went_wrong || [],
                improvements: content.improvements || [],
                failureMode: content.failure_mode || null,
                ruleChanges: [],
                timestamp: reflectionLog.timestamp,
              });
            } catch (e) {}
          }
        }
        setReflections(refs);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadReflections();
  }, []);

  // Compute failure modes from loaded reflections
  const failureModeMap: Record<string, number> = {};
  let totalWithFailure = 0;
  reflections.forEach(r => {
    if (r.failureMode) {
      failureModeMap[r.failureMode] = (failureModeMap[r.failureMode] || 0) + 1;
      totalWithFailure++;
    }
  });
  
  const failureModes = Object.entries(failureModeMap).map(([mode, count]) => ({
    mode,
    count,
    pct: Math.round((count / totalWithFailure) * 100),
  })).sort((a, b) => b.count - a.count);

  const allRuleChanges: (RuleChange & { sessionId: string })[] = reflections
    .filter(r => r.ruleChanges?.length)
    .flatMap(r => r.ruleChanges.map((rc: any) => ({ ...rc, sessionId: r.sessionId })));

  if (loading) {
    return <div className="p-8 text-center text-muted-foreground"><Loader2 className="h-6 w-6 animate-spin mx-auto mb-2"/> Analyzing reflections...</div>;
  }

  return (
    <div className="space-y-6 animate-slide-in">
      <div>
        <h1 className="text-xl font-mono font-bold text-foreground">Reflection Lab</h1>
        <p className="text-xs font-mono text-muted-foreground mt-0.5">Post-trade analysis, failure patterns & strategy evolution</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Failure Mode Stats */}
        <Panel title="Failure Mode Distribution" className="lg:col-span-1">
          <div className="space-y-3">
            {failureModes.map(fm => (
              <div key={fm.mode}>
                <div className="flex items-center justify-between text-xs font-mono mb-1">
                  <span className="text-foreground">{fm.mode.replace('_', ' ')}</span>
                  <span className="text-muted-foreground">{fm.count} ({fm.pct}%)</span>
                </div>
                <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                  <div
                    className={cn('h-full rounded-full',
                      fm.mode === 'stale_data' ? 'bg-stale' :
                        fm.mode === 'risk_rejected' ? 'bg-danger' :
                          fm.mode === 'slippage_exceeded' ? 'bg-warning' :
                            fm.mode === 'api_failure' ? 'bg-danger' : 'bg-info'
                    )}
                    style={{ width: `${fm.pct}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Panel>

        {/* Rule Changes History */}
        <Panel title="Rule Change History" className="lg:col-span-2">
          {allRuleChanges.length === 0 ? (
            <p className="text-xs font-mono text-muted-foreground">No rule changes recorded</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="text-muted-foreground border-b border-border">
                    <th className="text-left py-2 pr-3">Session</th>
                    <th className="text-left py-2 pr-3">Parameter</th>
                    <th className="text-left py-2 pr-3">Old</th>
                    <th className="text-left py-2 pr-3">New</th>
                    <th className="text-left py-2">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {allRuleChanges.map((rc, i) => (
                    <tr key={i} className="border-b border-border/30">
                      <td className="py-2 pr-3 text-primary">{rc.sessionId}</td>
                      <td className="py-2 pr-3 text-foreground">{rc.parameter}</td>
                      <td className="py-2 pr-3 text-danger">{rc.oldValue}</td>
                      <td className="py-2 pr-3 text-success">{rc.newValue}</td>
                      <td className="py-2 text-muted-foreground">{rc.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>

      {/* Individual Reflections */}
      <Panel title="Session Reflections">
        <div className="space-y-4">
          {reflections.length === 0 ? (
            <p className="text-xs font-mono text-muted-foreground">No reflection data found in recent sessions</p>
          ) : reflections.map((ref) => (
            <div key={ref.id} className="p-4 rounded-lg border border-border bg-secondary/20">
              <div className="flex items-center gap-3 mb-3">
                <span className="text-sm font-mono text-primary font-semibold">{ref.sessionId}</span>
                <span className="text-xs font-mono text-foreground font-semibold">{ref.symbol}</span>
                <StatusBadge status={ref.sessionStatus as any} />
                {ref.failureMode && (
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-danger/10 text-danger border border-danger/20">
                    {ref.failureMode}
                  </span>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
                <div>
                  <p className="text-success font-medium mb-2 uppercase tracking-wider text-[10px]">What Went Right</p>
                  <ul className="space-y-1.5">
                    {ref.whatWentRight.map((item, i) => (
                      <li key={i} className="text-muted-foreground pl-3 border-l-2 border-success/30 leading-relaxed">{item}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="text-danger font-medium mb-2 uppercase tracking-wider text-[10px]">What Went Wrong</p>
                  <ul className="space-y-1.5">
                    {ref.whatWentWrong.map((item, i) => (
                      <li key={i} className="text-muted-foreground pl-3 border-l-2 border-danger/30 leading-relaxed">{item}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="text-primary font-medium mb-2 uppercase tracking-wider text-[10px]">Improvements</p>
                  <ul className="space-y-1.5">
                    {ref.improvements.map((item, i) => (
                      <li key={i} className="text-muted-foreground pl-3 border-l-2 border-primary/30 leading-relaxed">{item}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
