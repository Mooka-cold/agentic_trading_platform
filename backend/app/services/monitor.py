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

    def _manage_position(self, pos: PaperPosition):
        # 1. Get Current Price
        current_price = self._get_current_price(pos.symbol)
        if not current_price:
            print(f"[Guardian] Could not fetch price for {pos.symbol}")
            return

        # 2. Check Hard Stop Loss
        if pos.side == 'LONG' and pos.stop_loss and current_price <= float(pos.stop_loss):
            print(f"[Guardian] HARD STOP LOSS triggered for {pos.symbol} @ {current_price} (SL: {pos.stop_loss})")
            self._close_position(pos, "STOP_LOSS", current_price)
            return

        # 3. Check Take Profit
        if pos.side == 'LONG' and pos.take_profit and current_price >= float(pos.take_profit):
            print(f"[Guardian] TAKE PROFIT triggered for {pos.symbol} @ {current_price} (TP: {pos.take_profit})")
            self._close_position(pos, "TAKE_PROFIT", current_price)
            return

        # 4. Trailing Stop (Simplified Logic)
        # If profit > 2%, move SL to break even
        entry = float(pos.entry_price)
        pnl_pct = (current_price - entry) / entry
        
        if pnl_pct > self.trailing_stop_pct:
            # Move SL to Entry if it's below entry (or not set)
            if not pos.stop_loss or float(pos.stop_loss) < entry:
                print(f"[Guardian] Trailing Stop Activated for {pos.symbol}: Moving SL to Break Even ({entry})")
                pos.stop_loss = Decimal(str(entry))
                self.db.commit()

        # 5. Soft Risk Trigger (AI Re-evaluation)
        # If position is losing > 0.5%, ask Analyst if we should hold
        if pnl_pct < self.ai_trigger_pct:
             self._trigger_ai_analysis(pos.symbol)

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

    def _close_position(self, pos: PaperPosition, reason: str, price: float):
        try:
            self.paper_service.execute_market_order(
                symbol=pos.symbol,
                side="SELL" if pos.side == "LONG" else "BUY",
                quantity=float(pos.size),
                current_price=price
            )
            print(f"[Guardian] Closed {pos.symbol} due to {reason} at {price}")
            
            # TODO: Notify AI Engine / Reflector
            
        except Exception as e:
            print(f"[Guardian] Failed to close position: {e}")

    def _get_current_price(self, symbol: str) -> float:
        # Use a fresh market db session
        db_gen = get_market_db()
        market_db = next(db_gen)
        try:
            result = market_db.execute(
                text("SELECT close FROM market_klines WHERE symbol = :s ORDER BY time DESC LIMIT 1"),
                {"s": symbol}
            ).scalar()
            return float(result) if result else None
        finally:
            market_db.close()
