import { Panel, StatusBadge } from '@/components/shared/StatusBadge';
import { cn } from '@/lib/utils';
import { useState, useEffect } from 'react';
import { fetchPositions, fetchOrders, fetchPaperAccountSnapshot } from '@/data/api';
import { Loader2 } from 'lucide-react';

export default function PortfolioPage() {
  const [positions, setPositions] = useState<any[]>([]);
  const [orders, setOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchPositions(), fetchOrders(), fetchPaperAccountSnapshot()])
      .then(([posData, orderData, accountData]) => {
        const cashBalance = Number(accountData?.balance ?? 0);
        const mergedPositions = [
          {
            symbol: 'USDT-CASH',
            side: 'CASH',
            quantity: cashBalance,
            entry_price: 1,
            current_price: 1,
            unrealized_pnl: 0,
            is_cash: true,
          },
          ...posData,
        ];
        setPositions(mergedPositions);
        setOrders(orderData);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6 animate-slide-in">
      <div>
        <h1 className="text-xl font-mono font-bold text-foreground">Live Portfolio</h1>
        <p className="text-xs font-mono text-muted-foreground mt-0.5">Current positions and order history</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Open Positions">
          {loading ? (
            <div className="py-8 text-center text-muted-foreground"><Loader2 className="h-6 w-6 animate-spin mx-auto mb-2"/> Loading...</div>
          ) : positions.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">No open positions</div>
          ) : (
            <div className="space-y-2">
              {positions.map((p, i) => (
                <div key={i} className="p-3 rounded border border-border/50 bg-secondary/20 flex items-center justify-between text-xs font-mono">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-bold text-foreground">{p.symbol}</span>
                      <span className={cn('px-1.5 py-0.5 rounded text-[10px]', p.side === 'LONG' ? 'bg-success/20 text-success' : p.side === 'CASH' ? 'bg-sky-500/20 text-sky-300' : 'bg-danger/20 text-danger')}>
                        {p.side}
                      </span>
                    </div>
                    {p.is_cash ? (
                      <div className="text-muted-foreground">Balance: ${Number(p.quantity || 0).toLocaleString()}</div>
                    ) : (
                      <div className="text-muted-foreground">
                        Qty: {p.quantity} @ ${p.entry_price?.toLocaleString()}
                      </div>
                    )}
                  </div>
                  <div className="text-right">
                    {p.is_cash ? (
                      <div className="text-muted-foreground text-[10px] mt-1">Available to trade</div>
                    ) : (
                      <>
                        <div className={cn('font-bold', p.unrealized_pnl >= 0 ? 'text-success' : 'text-danger')}>
                          ${p.unrealized_pnl?.toFixed(2)}
                        </div>
                        <div className="text-muted-foreground">
                          Mark: ${p.current_price?.toLocaleString()}
                        </div>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Order History">
          {loading ? (
            <div className="py-8 text-center text-muted-foreground"><Loader2 className="h-6 w-6 animate-spin mx-auto mb-2"/> Loading...</div>
          ) : orders.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">No recent orders</div>
          ) : (
            <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
              {orders.map((o, i) => (
                <div key={i} className="p-3 rounded border border-border/50 bg-secondary/20 text-xs font-mono">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-foreground">{o.symbol}</span>
                      <span className={cn('px-1.5 py-0.5 rounded text-[10px]', o.side === 'BUY' ? 'bg-success/20 text-success' : 'bg-danger/20 text-danger')}>
                        {o.side}
                      </span>
                    </div>
                    <StatusBadge status={o.status === 'FILLED' ? 'completed' : o.status} className="text-[10px] px-1 py-0" />
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-muted-foreground">
                    <div>Type: {o.type}</div>
                    <div className="text-right">Qty: {o.quantity}</div>
                    <div>Price: ${o.price?.toLocaleString() || o.executed_price?.toLocaleString()}</div>
                    <div className="text-right">{new Date(o.created_at).toLocaleString()}</div>
                  </div>
                  {o.pnl !== null && o.pnl !== undefined && (
                    <div className="mt-2 pt-2 border-t border-border/30 flex justify-between">
                      <span className="text-muted-foreground">Realized PnL</span>
                      <span className={cn('font-bold', o.pnl >= 0 ? 'text-success' : 'text-danger')}>
                        ${o.pnl.toFixed(2)}
                      </span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
