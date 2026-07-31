import { useState, useEffect, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Brain, Users, Save, ShieldAlert, Cpu, Gavel, Plus, X, GripVertical } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/data/api";
import { DndContext, DragOverlay, closestCenter, useSensor, useSensors, PointerSensor } from "@dnd-kit/core";
import { useDraggable, useDroppable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { cn } from "@/lib/utils";

// --- Draggable Component ---
function DraggablePersona({ persona }: { persona: any }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `persona-${persona.id}`,
    data: { type: "persona", persona },
  });
  
  const style = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div 
      ref={setNodeRef} 
      style={style} 
      {...listeners} 
      {...attributes}
      className="p-3 bg-secondary/30 rounded border border-border hover:border-primary/50 transition-colors cursor-grab active:cursor-grabbing flex gap-3"
    >
      <div className="mt-1 text-muted-foreground">
        <GripVertical className="h-4 w-4" />
      </div>
      <div>
        <div className="font-mono font-semibold text-sm mb-1 text-foreground">{persona.name}</div>
        <p className="text-xs text-muted-foreground line-clamp-2">{persona.description}</p>
      </div>
    </div>
  );
}

// --- Droppable Slot Component ---
function DroppableSlot({ id, label, currentPersonaId, getPersonaName, onRemove }: any) {
  const { isOver, setNodeRef } = useDroppable({
    id: id,
    data: { type: "slot" }
  });

  return (
    <div 
      ref={setNodeRef}
      className={`relative w-28 h-28 shrink-0 rounded border-2 border-dashed transition-colors flex flex-col items-center justify-center p-2 group
        ${isOver ? 'border-primary bg-primary/10' : 'border-border bg-secondary/10 hover:border-border/80'}
        ${currentPersonaId ? 'border-solid border-primary/30 bg-secondary/30' : ''}
      `}
    >
      {currentPersonaId ? (
        <>
          <div className="flex flex-col items-center text-center w-full">
            <span className="text-[10px] text-muted-foreground uppercase mb-1">{label}</span>
            <span className="text-xs font-mono font-bold text-primary line-clamp-2 leading-tight">{getPersonaName(currentPersonaId)}</span>
          </div>
          <button 
            onClick={() => onRemove(id)} 
            className="absolute top-1 right-1 p-1 bg-background/80 backdrop-blur opacity-0 group-hover:opacity-100 hover:bg-destructive/20 text-muted-foreground hover:text-destructive rounded transition-all z-10 cursor-pointer"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </>
      ) : (
        <span className="text-[10px] text-center font-mono text-muted-foreground italic pointer-events-none opacity-50">
          Drop here
        </span>
      )}
    </div>
  );
}

// --- Topology Preview Component ---
function TopologyPreview({ config, getPersonaName }: { config: any; getPersonaName: (id: string) => string }) {
  const seats = useMemo(() => {
    const s: any[] = [];

    // 4-lane pipeline (Data -> Strategy -> Finalizer -> Risk)
    // X coordinates: 15%, 40%, 65%, 90%

    // Lane 1: Market Analysts
    const marketAgents = (config?.market_agent_ids || []).filter(Boolean);
    marketAgents.forEach((id: string, idx: number) => {
      const total = marketAgents.length;
      const startY = 50 - (total - 1) * 15;
      s.push({ role: id, label: getPersonaName(id), team: 'Data Team', x: 15, y: startY + idx * 30 });
    });

    // Lane 2: Strategy Masters
    const strategyAgents = (config?.strategy_agent_ids || []).filter(Boolean);
    strategyAgents.forEach((id: string, idx: number) => {
      const total = strategyAgents.length;
      const startY = 50 - (total - 1) * 15;
      s.push({ role: id, label: getPersonaName(id), team: 'Strategy Team', x: 40, y: startY + idx * 30 });
    });

    // Lane 3: Finalizer + Risk (stacked vertically)
    const finalizerId = config?.finalizer_agent_id;
    const riskAgents = (config?.risk_agent_ids || []).filter(Boolean);
    const lane3Count = (finalizerId ? 1 : 0) + riskAgents.length;
    let currentLane3Y = 50 - (lane3Count - 1) * 15;

    if (finalizerId) {
      s.push({ role: finalizerId, label: getPersonaName(finalizerId), team: 'Risk Team', x: 65, y: currentLane3Y, isFinalizer: true });
      currentLane3Y += 30;
    }
    riskAgents.forEach((id: string) => {
      s.push({ role: id, label: getPersonaName(id), team: 'Risk Team', x: 65, y: currentLane3Y, isRisk: true });
      currentLane3Y += 30;
    });

    return s;
  }, [config, getPersonaName]);

  const edges = useMemo(() => {
    const e: [any, any][] = [];
    const market = seats.filter(s => s.team === 'Data Team');
    const strategy = seats.filter(s => s.team === 'Strategy Team');
    const finalizer = seats.find(s => s.isFinalizer);
    const risk = seats.filter(s => s.isRisk);

    market.forEach(m => strategy.forEach(d => e.push([m, d])));
    if (finalizer) strategy.forEach(d => e.push([d, finalizer]));
    if (finalizer && risk.length > 0) {
      risk.forEach(r => e.push([finalizer, r]));
    }

    return e;
  }, [seats]);

  return (
    <div className="relative w-full h-[320px] rounded-lg border border-border/60 bg-secondary/10 overflow-hidden">
      {/* Background Lanes */}
      <div className="absolute inset-0 flex w-full">
        <div className="flex-1 border-r border-border/30 bg-background/20 relative">
          <span className="absolute top-2 left-2 text-[9px] font-mono text-muted-foreground uppercase opacity-50">Data</span>
        </div>
        <div className="flex-1 border-r border-border/30 bg-background/20 relative">
          <span className="absolute top-2 left-2 text-[9px] font-mono text-muted-foreground uppercase opacity-50">Strategy</span>
        </div>
        <div className="flex-1 bg-background/20 relative">
          <span className="absolute top-2 left-2 text-[9px] font-mono text-muted-foreground uppercase opacity-50">Risk &amp; Finalize</span>
        </div>
      </div>

      <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 100 100" preserveAspectRatio="none">
        <defs>
          <marker id="preview-arrow" markerWidth="6" markerHeight="4" refX="5" refY="2" orient="auto">
            <polygon points="0 0, 6 2, 0 4" fill="hsl(var(--primary))" opacity="0.4" />
          </marker>
        </defs>
        {edges.map(([p1, p2], i) => {
          const dx = p2.x - p1.x;
          const dy = p2.y - p1.y;
          const horizontal = Math.abs(dx) >= Math.abs(dy);
          const c1x = horizontal ? p1.x + dx * 0.4 : p1.x;
          const c1y = horizontal ? p1.y : p1.y + dy * 0.4;
          const c2x = horizontal ? p1.x + dx * 0.6 : p2.x;
          const c2y = horizontal ? p2.y : p1.y + dy * 0.6;
          return (
            <path
              key={i}
              d={`M ${p1.x} ${p1.y} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${p2.x} ${p2.y}`}
              fill="none"
              stroke="hsl(var(--primary))"
              strokeWidth="0.4"
              strokeDasharray="2 1.5"
              opacity="0.3"
              markerEnd="url(#preview-arrow)"
            />
          );
        })}
      </svg>
      {seats.map((seat, i) => (
        <div
          key={i}
          className="absolute w-9 h-9 -translate-x-1/2 -translate-y-1/2 rounded-full border border-primary/40 bg-card flex flex-col items-center justify-center shadow-md hover:scale-110 transition-transform"
          style={{ left: `${seat.x}%`, top: `${seat.y}%` }}
        >
          <Users className="h-4 w-4 text-primary/80 mb-0.5" />
          <div className="absolute top-full mt-1.5 w-24 text-center">
            <span className="text-[9px] font-mono text-foreground leading-tight line-clamp-2 bg-background/90 px-1 py-0.5 rounded shadow-sm border border-border/50">
              {seat.label}
            </span>
          </div>
        </div>
      ))}
      {seats.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center text-xs font-mono text-muted-foreground">
          Drag personas into slots to build the topology
        </div>
      )}
    </div>
  );
}

// --- Main Page ---
export default function AgentStudioPage() {
  const queryClient = useQueryClient();

  const { data: personas, isLoading: loadingPersonas } = useQuery({
    queryKey: ["personas"],
    queryFn: () => api.get("/system/personas").then((res) => res.data),
  });

  const { data: teamConfig, isLoading: loadingConfig } = useQuery({
    queryKey: ["team-config"],
    queryFn: () => api.get("/system/team-config").then((res) => res.data),
  });

  const updateConfig = useMutation({
    mutationFn: (newConfig: any) => api.put("/system/team-config", newConfig),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team-config"] });
      toast.success("Team configuration saved successfully!");
    },
    onError: (err) => {
      toast.error("Failed to save team configuration");
      console.error(err);
    },
  });

  const [localConfig, setLocalConfig] = useState<any>(null);
  
  // Initialize config
  useEffect(() => {
    if (teamConfig && !localConfig) {
      // Ensure arrays exist and have at least 1 slot if empty
      const conf = { ...teamConfig };
      if (!conf.market_agent_ids || conf.market_agent_ids.length === 0) conf.market_agent_ids = [null];
      if (!conf.strategy_agent_ids || conf.strategy_agent_ids.length === 0) conf.strategy_agent_ids = [null];
      if (!conf.risk_agent_ids || conf.risk_agent_ids.length === 0) conf.risk_agent_ids = [null];
      setLocalConfig(conf);
    }
  }, [teamConfig, localConfig]);

  // Drag and Drop State
  const [activePersona, setActivePersona] = useState<any>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const handleDragStart = (event: any) => {
    const { active } = event;
    if (active.data.current?.type === "persona") {
      setActivePersona(active.data.current.persona);
    }
  };

  const handleDragEnd = (event: any) => {
    const { active, over } = event;
    setActivePersona(null);

    if (over && over.data.current?.type === "slot") {
      const personaId = active.id.replace('persona-', '');
      const slotId = String(over.id); // Ensure string

      setLocalConfig((prev: any) => {
        const next = { ...prev };
        
        if (slotId.includes('_ids_')) {
          // It's a list slot
          const [key, indexStr] = slotId.split('_ids_');
          const index = parseInt(indexStr);
          const arrayKey = `${key}_ids`;
          const arr = [...(next[arrayKey] || [])];
          arr[index] = personaId;
          next[arrayKey] = arr;
        } else {
          // It's a single slot
          next[slotId] = personaId;
        }
        return next;
      });
    }
  };

  const handleRemove = (slotId: string) => {
    slotId = String(slotId);
    setLocalConfig((prev: any) => {
      const next = { ...prev };
      if (slotId.includes('_ids_')) {
        const [key, indexStr] = slotId.split('_ids_');
        const index = parseInt(indexStr);
        const arrayKey = `${key}_ids`;
        const arr = [...(next[arrayKey] || [])];
        
        // If it's the last slot and we remove it, just null it out so the slot remains
        if (arr.length === 1) {
          arr[0] = null;
        } else {
          arr.splice(index, 1);
        }
        next[arrayKey] = arr;
      } else {
        next[slotId] = null;
      }
      return next;
    });
  };

  const handleAddSlot = (arrayKey: string) => {
    setLocalConfig((prev: any) => {
      const next = { ...prev };
      const arr = [...(next[arrayKey] || [])];
      arr.push(null);
      next[arrayKey] = arr;
      return next;
    });
  };

  const handleSave = () => {
    if (localConfig) {
      // Clean up nulls before sending
      const payload: any = { ...localConfig };
      payload.market_agent_ids = (payload.market_agent_ids || []).filter(Boolean);
      payload.strategy_agent_ids = (payload.strategy_agent_ids || []).filter(Boolean);
      payload.risk_agent_ids = (payload.risk_agent_ids || []).filter(Boolean);
      // Strip legacy keys just in case
      delete payload.decision_agent_ids;
      delete payload.arbitrator_agent_id;
      delete payload.risk_agent_id;
      delete payload.execution_agent_id;
      updateConfig.mutate(payload);
    }
  };

  if (loadingPersonas || loadingConfig || !localConfig) {
    return <div className="p-6 text-muted-foreground font-mono">Loading Studio...</div>;
  }

  const getPersonaName = (id: string) => {
    if (!id) return "None";
    const p = personas?.find((p: any) => p.id === id);
    return p ? p.name : id;
  };

  const stages = [
    { key: "market_agent_ids", label: "Market Analysts", icon: Cpu, isList: true, desc: "Extract insights from price and orderbook data." },
    { key: "strategy_agent_ids", label: "Strategy Masters", icon: Brain, isList: true, desc: "Multiple investment philosophies debate and propose trades." },
    { key: "finalizer_agent_id", label: "Final Decision Maker", icon: Gavel, isList: false, desc: "Reads debate and makes the final call." },
    { key: "risk_agent_ids", label: "Risk Officers (Multi-Sig)", icon: ShieldAlert, isList: true, desc: "≥2 risk officers required for multi-signature consensus." },
  ];

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
      <div className="space-y-6 max-w-7xl mx-auto pb-10 h-[calc(100vh-6rem)] flex flex-col">
        <div className="flex items-center justify-between shrink-0">
          <div>
            <h1 className="text-2xl font-bold font-mono text-primary text-glow flex items-center gap-2">
              <Users className="h-6 w-6" />
              Agent Studio
            </h1>
            <p className="text-sm text-muted-foreground font-mono mt-1">
              Drag and drop personas from the roster to build your personalized trading team.
            </p>
          </div>
          <button
            onClick={handleSave}
            disabled={updateConfig.isPending}
            className="px-4 py-2 bg-primary/20 text-primary border border-primary/50 rounded flex items-center gap-2 hover:bg-primary/30 transition-colors font-mono text-sm"
          >
            <Save className="h-4 w-4" />
            {updateConfig.isPending ? "Saving..." : "Save Team Topology"}
          </button>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 flex-1 min-h-0">
          {/* Left Column: Persona Roster (Draggable Pool) */}
          <div className="bg-card border border-border rounded-lg p-5 flex flex-col h-full overflow-hidden">
            <h2 className="text-lg font-bold font-mono mb-4 text-foreground">Candidate Pool</h2>
            <p className="text-xs text-muted-foreground mb-4 shrink-0">Drag a persona to assign them to a stage.</p>
            
            <div className="overflow-y-auto pr-2 space-y-3 scrollbar-thin flex-1 pb-4">
              {personas?.map((p: any) => (
                <DraggablePersona key={p.id} persona={p} />
              ))}
            </div>
          </div>

          {/* Middle Column: Workflow Stages (Droppable Areas) */}
          <div className="xl:col-span-2 bg-card border border-border rounded-lg p-5 flex flex-col h-full overflow-hidden">
            <h2 className="text-lg font-bold font-mono mb-4 text-foreground">Stage Slots</h2>
            
            <div className="overflow-y-auto pr-2 space-y-6 scrollbar-thin flex-1 pb-4">
              {stages.map((stage) => (
                <div key={stage.key} className="p-4 bg-secondary/20 rounded border border-border/50">
                  <div className="flex items-center gap-2 mb-4">
                    <stage.icon className="h-5 w-5 text-primary" />
                    <div>
                      <h3 className="font-mono font-semibold text-foreground">{stage.label}</h3>
                      <p className="text-xs text-muted-foreground mt-0.5">{stage.desc}</p>
                    </div>
                  </div>
                  
                  <div className="flex flex-wrap gap-3">
                    {stage.isList ? (
                      <>
                        {localConfig[stage.key].map((personaId: string | null, index: number) => (
                          <DroppableSlot 
                            key={`${stage.key}_${index}`} 
                            id={`${stage.key}_${index}`} 
                            label={`Seat ${index + 1}`}
                            currentPersonaId={personaId}
                            getPersonaName={getPersonaName}
                            onRemove={handleRemove}
                          />
                        ))}
                        <button 
                          onClick={() => handleAddSlot(stage.key)}
                          className="w-28 h-28 shrink-0 rounded border-2 border-dashed border-border/50 bg-secondary/5 hover:bg-primary/5 hover:border-primary/30 transition-colors flex flex-col items-center justify-center gap-2 text-muted-foreground hover:text-primary cursor-pointer"
                          title="Add another seat"
                        >
                          <Plus className="h-6 w-6" />
                          <span className="text-[10px] font-mono uppercase">Add Seat</span>
                        </button>
                      </>
                    ) : (
                      <DroppableSlot 
                        key={stage.key} 
                        id={stage.key} 
                        label="Single Seat"
                        currentPersonaId={localConfig[stage.key]}
                        getPersonaName={getPersonaName}
                        onRemove={handleRemove}
                      />
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right Column: Live Topology Preview */}
          <div className="bg-card border border-border rounded-lg p-5 flex flex-col h-full overflow-hidden">
            <h2 className="text-lg font-bold font-mono mb-4 text-foreground">Topology Preview</h2>
            <p className="text-xs text-muted-foreground mb-4 shrink-0">Real-time team structure & communication edges.</p>
            <div className="flex-1">
              <TopologyPreview config={localConfig} getPersonaName={getPersonaName} />
            </div>
          </div>
        </div>
      </div>

      <DragOverlay>
        {activePersona ? (
          <div className="p-3 bg-secondary rounded border border-primary shadow-2xl opacity-90 rotate-3 cursor-grabbing w-[300px]">
            <div className="font-mono font-semibold text-sm mb-1 text-foreground">{activePersona.name}</div>
            <p className="text-xs text-muted-foreground line-clamp-2">{activePersona.description}</p>
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}