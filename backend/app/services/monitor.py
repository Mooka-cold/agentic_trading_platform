from sqlalchemy.orm import Session
from app.services.paper_trading import PaperTradingService, PaperPosition
from app.db.session import get_market_db
from sqlalchemy import text
from decimal import Decimal

from app.core.config import settings

class PositionMonitorService:
    def __init__(self, db: Session, user_id: int = 1):
        self.db = db
        self.user_id = user_id
        self.paper_service = PaperTradingService(db)
        self.ai_engine_url = settings.AI_ENGINE_URL
        self.trailing_stop_pct = settings.RISK_TRAILING_STOP_PCT
        self.ai_trigger_pct = settings.RISK_AI_TRIGGER_PCT

    def check_and_manage_positions(self):
        """
        Scan all open positions and apply risk rules.
        """
        positions = self.paper_service.get_open_positions(self.user_id)
        if not positions:
            return

        print(f"[Guardian] Scanning {len(positions)} open positions...")
        
        for pos in positions:
            self._manage_position(pos)

    def _get_current_price_and_depth(self, symbol: str):
        # Use Global PriceStreamer (Zero Latency)
        from app.services.price_streamer import price_streamer
        
        # Ensure subscription (idempotent)
        # Note: In a real async app, start() should be called at startup.
        # Here we assume it's running, or we trigger it if we are in an async context?
        # Monitor runs in a thread pool (sync wrapper), so we can't await start() here easily.
        # But get_latest is sync.
        
        price, depth = price_streamer.get_latest(symbol)
        
        if price:
            return price, depth
            
        # If Streamer not ready or no data yet, fallback to REST (once)
        # This prevents failure during cold start
        print(f"[Guardian] Streamer cache miss for {symbol}. Trying REST fallback...")
        import ccxt
        try:
            exchange = ccxt.binance()
            ticker = exchange.fetch_ticker(symbol)
            return float(ticker['last']), None
        except:
            return None, None

    def _manage_position(self, pos: PaperPosition):
        try:
            # 1. Get Current Price & Depth
            current_price, order_book = self._get_current_price_and_depth(pos.symbol)
            
            if not current_price:
                 # Fallback to DB if CCXT fails
                 current_price = self._get_db_price(pos.symbol)
            
            if not current_price:
                print(f"[Guardian] Could not fetch price for {pos.symbol}")
                return
    
            entry = float(pos.entry_price)
            pnl_pct = 0.0
            
            if pos.side == 'LONG':
                pnl_pct = (current_price - entry) / entry
            elif pos.side == 'SHORT':
                pnl_pct = (entry - current_price) / entry

            # 2. Check Hard Stop Loss
            if pos.stop_loss:
                sl = float(pos.stop_loss)
                triggered = False
                if pos.side == 'LONG' and current_price <= sl:
                    triggered = True
                elif pos.side == 'SHORT' and current_price >= sl:
                    triggered = True
                
                if triggered:
                    print(f"[Guardian] HARD STOP LOSS triggered for {pos.symbol} @ {current_price} (SL: {sl})")
                    self._close_position(pos, "STOP_LOSS", current_price, order_book)
                    return

            # 3. Check Take Profit
            if pos.take_profit:
                tp = float(pos.take_profit)
                triggered = False
                if pos.side == 'LONG' and current_price >= tp:
                    triggered = True
                elif pos.side == 'SHORT' and current_price <= tp:
                    triggered = True
                
                if triggered:
                    print(f"[Guardian] TAKE PROFIT triggered for {pos.symbol} @ {current_price} (TP: {tp})")
                    self._close_position(pos, "TAKE_PROFIT", current_price, order_book)
                    return

            # 4. Trailing Stop (Simplified Logic)
            # If profit > 2%, move SL to break even
            if pnl_pct > self.trailing_stop_pct:
                # Move SL to Entry if it's below entry (or not set)
                # For LONG: SL should increase. For SHORT: SL should decrease.
                new_sl = Decimal(str(entry))
                should_update = False
                
                if not pos.stop_loss:
                    should_update = True
                elif pos.side == 'LONG' and float(pos.stop_loss) < entry:
                    should_update = True
                elif pos.side == 'SHORT' and float(pos.stop_loss) > entry:
                    should_update = True
                    
                if should_update:
                    print(f"[Guardian] Trailing Stop Activated for {pos.symbol}: Moving SL to Break Even ({entry})")
                    pos.stop_loss = new_sl
                    self.db.commit()

            # 5. Soft Risk Trigger (AI Re-evaluation)
            # If position is losing > 0.5%, ask Analyst if we should hold
            if pnl_pct < self.ai_trigger_pct:
                 self._trigger_ai_analysis(pos.symbol)
                 
        except Exception as e:
            print(f"[Guardian] Error managing position {pos.symbol}: {e}")

    def _trigger_ai_analysis(self, symbol: str):
        import httpx
        try:
            # Call AI Engine Trigger Endpoint
            # Using short timeout to not block Guardian
            with httpx.Client(timeout=1.0) as client:
                client.post(
                    f"{self.ai_engine_url}/workflow/trigger",
                    json={"symbol": symbol, "session_id": f"guardian-{symbol}"}
                )
                print(f"[Guardian] 🚨 Soft Risk! Triggered AI Analysis for {symbol}")
        except Exception as e:
            # Ignore connection errors (fire and forget)
            pass

    def _close_position(self, pos: PaperPosition, reason: str, price: float, order_book: dict = None):
        try:
            # Execute Market Order via Paper Service
            # Note: We call paper_service directly, not ExecutionService, to avoid circular dependency if possible.
            # And Guardian runs in backend, so it has direct DB access.
            
            # Close Position
            side = "SELL" if pos.side == "LONG" else "BUY"
            # execute_market_order handles PnL calculation and Position update
            order, exec_info = self.paper_service.execute_market_order(
                symbol=pos.symbol,
                side=side,
                quantity=float(pos.size),
                current_price=price,
                session_id=f"guardian-{reason.lower()}",
                order_book=order_book
            )
            print(f"[Guardian] Closed {pos.symbol} due to {reason} at {price}")
            
            # TRIGGER AI REFLECTION
            # We must notify the Reflector so it can analyze WHY we hit SL/TP.
            # This is crucial for the "Feedback Loop".
            self._trigger_ai_reflection(exec_info["order_id"], exec_info)
            
        except Exception as e:
            print(f"[Guardian] Failed to close position: {e}")

    def _trigger_ai_reflection(self, order_id: str, exec_info: dict):
        import httpx
        try:
            # Construct a special payload for Reflector
            # We use the existing /workflow/trigger endpoint but with a special flag?
            # Or better: call Reflector directly via a new endpoint if available.
            # Currently AI Engine has /workflow/review which triggers periodic checks.
            # But we want IMMEDIATE reflection on this specific closure.
            
            # Let's use the 'execution_result' structure expected by Reflector
            # We can't easily inject state into a running agent from here.
            # BUT, Reflector scans for "recently closed orders without reflection".
            # So, by just closing the order in DB, the next Periodic Review (every 5m) WILL pick it up!
            
            # HOWEVER, to be faster, we can poke the AI Engine to run a review NOW.
            with httpx.Client(timeout=1.0) as client:
                client.post(
                    f"{self.ai_engine_url}/workflow/review/periodic",
                    json={} # Trigger immediate check
                )
                print(f"[Guardian] 🧠 Triggered Immediate AI Reflection for Order {order_id}")

        except Exception as e:
            print(f"[Guardian] Failed to trigger reflection: {e}")

    def _get_db_price(self, symbol: str) -> float:
        # Fallback to DB (Low Priority)
        db_gen = get_market_db()
        market_db = next(db_gen)
        try:
            result = market_db.execute(
                text("SELECT close FROM market_klines WHERE symbol = :s ORDER BY time DESC LIMIT 1"),
                {"s": symbol}
            ).scalar()
            
            if result:
                 return float(result)
            return None
        except Exception as e:
            print(f"[Guardian] Price fetch error: {e}")
            return None
        finally:
            market_db.close()
