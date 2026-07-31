import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Workflow, Play, Clock, Activity, Plus, Trash2, Save } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/data/api";
import { Badge } from "@/components/ui/badge";

export default function AutomationBuilderPage() {
  const queryClient = useQueryClient();

  const { data: rules, isLoading } = useQuery({
    queryKey: ["automation-rules"],
    queryFn: () => api.get("/system/automation/rules").then((res) => res.data),
  });

  const createRule = useMutation({
    mutationFn: (newRule: any) => api.post("/system/automation/rules", newRule),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["automation-rules"] });
      toast.success("Rule created successfully!");
    },
    onError: (err) => {
      toast.error("Failed to create rule");
      console.error(err);
    },
  });

  const [ruleType, setRuleType] = useState("CRON");
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [cronExpr, setCronExpr] = useState("0 * * * *");
  const [indicator, setIndicator] = useState("RSI");
  const [operator, setOperator] = useState("<");
  const [val, setVal] = useState("30");

  const handleCreate = () => {
    const payload: any = {
      symbol: symbol,
      rule_type: ruleType,
      is_active: true,
      condition_payload: {},
      action_payload: {}
    };

    if (ruleType === "CRON") {
      payload.condition_payload = { cron: cronExpr };
    } else if (ruleType === "INDICATOR") {
      payload.condition_payload = { indicator, operator, value: parseFloat(val) };
    }

    createRule.mutate(payload);
  };

  if (isLoading) {
    return <div className="p-6 text-muted-foreground font-mono">Loading Automation Rules...</div>;
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold font-mono text-primary text-glow flex items-center gap-2">
            <Workflow className="h-6 w-6" />
            Automation Builder
          </h1>
          <p className="text-sm text-muted-foreground font-mono mt-1">
            Configure triggers to automatically launch your Agent Team workflow.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="bg-card border border-border rounded-lg p-5">
          <h2 className="text-lg font-bold font-mono mb-4 text-foreground flex items-center gap-2">
            <Plus className="h-5 w-5 text-primary" />
            New Trigger Rule
          </h2>
          
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-mono text-muted-foreground mb-1">Trigger Type</label>
              <select 
                value={ruleType} 
                onChange={(e) => setRuleType(e.target.value)}
                className="w-full bg-secondary border border-border rounded px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="CRON">Time-based (CRON)</option>
                <option value="INDICATOR">Market Indicator</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-mono text-muted-foreground mb-1">Target Symbol</label>
              <input 
                type="text" 
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                className="w-full bg-secondary border border-border rounded px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            {ruleType === "CRON" && (
              <div>
                <label className="block text-xs font-mono text-muted-foreground mb-1">CRON Expression</label>
                <input 
                  type="text" 
                  value={cronExpr}
                  onChange={(e) => setCronExpr(e.target.value)}
                  placeholder="e.g. 0 * * * * (Every hour)"
                  className="w-full bg-secondary border border-border rounded px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
            )}

            {ruleType === "INDICATOR" && (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-mono text-muted-foreground mb-1">Indicator</label>
                  <select 
                    value={indicator} 
                    onChange={(e) => setIndicator(e.target.value)}
                    className="w-full bg-secondary border border-border rounded px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="RSI">RSI (14)</option>
                    <option value="MACD">MACD Histogram</option>
                  </select>
                </div>
                <div className="flex gap-2">
                  <div className="flex-1">
                    <label className="block text-xs font-mono text-muted-foreground mb-1">Operator</label>
                    <select 
                      value={operator} 
                      onChange={(e) => setOperator(e.target.value)}
                      className="w-full bg-secondary border border-border rounded px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-primary"
                    >
                      <option value="<">&lt;</option>
                      <option value=">">&gt;</option>
                      <option value="==">==</option>
                    </select>
                  </div>
                  <div className="flex-1">
                    <label className="block text-xs font-mono text-muted-foreground mb-1">Value</label>
                    <input 
                      type="number" 
                      value={val}
                      onChange={(e) => setVal(e.target.value)}
                      className="w-full bg-secondary border border-border rounded px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-primary"
                    />
                  </div>
                </div>
              </div>
            )}

            <button
              onClick={handleCreate}
              disabled={createRule.isPending}
              className="w-full py-2 bg-primary/20 text-primary border border-primary/50 rounded flex items-center justify-center gap-2 hover:bg-primary/30 transition-colors font-mono text-sm mt-4"
            >
              <Save className="h-4 w-4" />
              {createRule.isPending ? "Saving..." : "Save Rule"}
            </button>
          </div>
        </div>

        <div className="xl:col-span-2 space-y-4">
          <div className="bg-card border border-border rounded-lg p-5">
            <h2 className="text-lg font-bold font-mono mb-4 text-foreground">Active Triggers</h2>
            
            {rules?.length === 0 ? (
              <div className="text-sm text-muted-foreground font-mono italic p-4 border border-dashed border-border rounded text-center">
                No automation rules configured.
              </div>
            ) : (
              <div className="space-y-3">
                {rules?.map((rule: any) => (
                  <div key={rule.id} className="p-4 bg-secondary/30 rounded border border-border flex items-center justify-between group">
                    <div className="flex items-center gap-4">
                      <div className="p-2 bg-background rounded border border-border">
                        {rule.rule_type === 'CRON' ? <Clock className="h-5 w-5 text-primary" /> : <Activity className="h-5 w-5 text-primary" />}
                      </div>
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-mono font-bold text-sm text-foreground">{rule.symbol}</span>
                          <Badge variant="outline" className={rule.is_active ? "bg-success/10 text-success border-success/30" : "bg-muted text-muted-foreground"}>
                            {rule.is_active ? "ACTIVE" : "PAUSED"}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground font-mono">
                          {rule.rule_type === 'CRON' 
                            ? `Schedule: ${rule.condition_payload.cron}` 
                            : `Condition: ${rule.condition_payload.indicator} ${rule.condition_payload.operator} ${rule.condition_payload.value}`
                          }
                        </p>
                      </div>
                    </div>
                    
                    <button className="p-2 text-muted-foreground hover:text-destructive transition-colors opacity-0 group-hover:opacity-100">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
