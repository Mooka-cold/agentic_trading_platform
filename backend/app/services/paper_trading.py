import uuid
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.base import Base
from shared.models.user import User
from app.db.session import SessionLocalMarket
from shared.models.market import MarketKline
from shared.models.system import SystemConfig
from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey, text, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone

# --- Models (Ideally should be in app/models/paper.py) ---

class PaperAccount(Base):
    __tablename__ = "paper_accounts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, nullable=True) # Optional link to real user
    balance = Column(Numeric(20, 8), nullable=False, default=200000.0) # Updated default to 200k
    currency = Column(String(10), nullable=False, default='USDT')
    created_at = Column(DateTime(timezone=True), server_default=text('now()'))
    updated_at = Column(DateTime(timezone=True), server_default=text('now()'), onupdate=datetime.now)
    
    # Portfolio Risk Fields
    daily_start_balance = Column(Numeric(20, 8), default=200000.0) # Updated default
    high_watermark = Column(Numeric(20, 8), default=200000.0) # Updated default
    is_locked = Column(Boolean, default=False)
    lock_reason = Column(String(255), nullable=True)

class PaperOrder(Base):
    __tablename__ = "paper_orders"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("paper_accounts.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False) # BUY/SELL
    type = Column(String(10), nullable=False) # MARKET/LIMIT
    intent = Column(String(20), nullable=False, default='MARKET') # OPEN_LONG, CLOSE_SHORT, etc.
    price = Column(Numeric(20, 8), nullable=True)
    quantity = Column(Numeric(20, 8), nullable=False)
    status = Column(String(20), nullable=False, default='PENDING')
    pnl = Column(Numeric(20, 8), nullable=True) # Realized PnL for CLOSE orders
    session_id = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text('now()'))
    filled_at = Column(DateTime(timezone=True), nullable=True)

class SessionReflection(Base):
    __tablename__ = "session_reflections"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String, ForeignKey("workflow_sessions.id"), nullable=False) # Changed from order_id to session_id
    stage = Column(String(20), nullable=False) # IMMEDIATE, T_PLUS_1H, T_PLUS_6H, T_PLUS_24H
    market_context = Column(Text, nullable=True) # JSON stored as Text
    price_change_pct = Column(Numeric(10, 4), nullable=True)
    score = Column(Numeric(5, 2), nullable=True)
    content = Column(Text, nullable=False) # The JSON output from LLM
    created_at = Column(DateTime(timezone=True), server_default=text('now()'))

class PaperPosition(Base):
    __tablename__ = "paper_positions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("paper_accounts.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)
    entry_price = Column(Numeric(20, 8), nullable=False)
    size = Column(Numeric(20, 8), nullable=False)
    stop_loss = Column(Numeric(20, 8), nullable=True)
    take_profit = Column(Numeric(20, 8), nullable=True)
    status = Column(String(20), nullable=False, default='OPEN')
    session_id = Column(String(50), nullable=True)
    opened_at = Column(DateTime(timezone=True), server_default=text('now()'))
    closed_at = Column(DateTime(timezone=True), nullable=True)

# --- Service ---

class PaperTradingService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_account(self, user_id: int = None) -> PaperAccount:
        user_id = 1 if user_id is None else user_id
        query = select(PaperAccount).where(PaperAccount.user_id == user_id) if user_id else select(PaperAccount).limit(1)
        account = self.db.execute(query).scalar_one_or_none()
        
        if not account:
            account = PaperAccount(user_id=user_id, balance=100000.0)
            self.db.add(account)
            self.db.commit()
            self.db.refresh(account)
        return account

    def get_equity(self, user_id: int = None, current_prices: dict = None) -> float:
        """
        Calculate total equity: Balance + Unrealized PnL
        """
        account = self.get_or_create_account(user_id)
        balance = float(account.balance)
        unrealized_pnl = 0.0
        
        if current_prices:
            positions = self.get_open_positions(user_id)
            for pos in positions:
                if pos.symbol in current_prices:
                    price = float(current_prices[pos.symbol])
                    entry = float(pos.entry_price)
                    size = float(pos.size)
                    if pos.side == 'LONG':
                        unrealized_pnl += (price - entry) * size
                    else:
                        unrealized_pnl += (entry - price) * size
        
        return balance + unrealized_pnl

    def _get_latest_prices(self, symbols: list[str]) -> dict:
        prices = {}
        if not symbols:
            return prices
        market_db = SessionLocalMarket()
        try:
            for symbol in symbols:
                row = market_db.execute(
                    select(MarketKline.close)
                    .where(MarketKline.symbol == symbol)
                    .where(MarketKline.interval == "1m")
                    .order_by(MarketKline.time.desc())
                    .limit(1)
                ).first()
                if row and row[0] is not None:
                    prices[symbol] = float(row[0])
                    continue
                row_fallback = market_db.execute(
                    select(MarketKline.close)
                    .where(MarketKline.symbol == symbol)
                    .order_by(MarketKline.time.desc())
                    .limit(1)
                ).first()
                if row_fallback and row_fallback[0] is not None:
                    prices[symbol] = float(row_fallback[0])
        finally:
            market_db.close()
        return prices

    def _safe_float(self, value, default: float) -> float:
        try:
            return float(value)
        except Exception:
            return default

    def _get_execution_controls(self) -> dict:
        min_slippage_cfg = self.db.query(SystemConfig).filter(SystemConfig.key == "PAPER_MIN_SLIPPAGE_BPS").first()
        taker_fee_cfg = self.db.query(SystemConfig).filter(SystemConfig.key == "PAPER_TAKER_FEE_BPS").first()
        stale_cfg = self.db.query(SystemConfig).filter(SystemConfig.key == "PAPER_MAX_PRICE_STALENESS_SECONDS").first()
        leverage_cfg = self.db.query(SystemConfig).filter(SystemConfig.key == "PAPER_MAX_PORTFOLIO_LEVERAGE").first()
        min_slippage_bps = self._safe_float(min_slippage_cfg.value if min_slippage_cfg else None, 1.0)
        taker_fee_bps = self._safe_float(taker_fee_cfg.value if taker_fee_cfg else None, 4.0)
        max_staleness_seconds = self._safe_float(stale_cfg.value if stale_cfg else None, 180.0)
        max_portfolio_leverage = self._safe_float(leverage_cfg.value if leverage_cfg else None, 4.0)
        return {
            "min_slippage_bps": max(0.0, min_slippage_bps),
            "taker_fee_bps": max(0.0, taker_fee_bps),
            "max_staleness_seconds": max(30.0, max_staleness_seconds),
            "max_portfolio_leverage": max(1.0, max_portfolio_leverage),
        }

    def _current_gross_notional(self, account_id) -> Decimal:
        positions = self.db.execute(
            select(PaperPosition)
            .where(PaperPosition.account_id == account_id)
            .where(PaperPosition.status == 'OPEN')
        ).scalars().all()
        gross = Decimal("0")
        for pos in positions:
            size = Decimal(str(pos.size or 0))
            entry = Decimal(str(pos.entry_price or 0))
            gross += abs(size * entry)
        return gross

    def _cap_open_qty_by_leverage(
        self,
        account: PaperAccount,
        candidate_qty: Decimal,
        price: Decimal,
        controls: dict
    ) -> tuple[Decimal, dict]:
        if candidate_qty <= 0 or price <= 0:
            return Decimal("0"), {"allowed_qty": 0.0, "reason": "invalid_input"}
        balance = Decimal(str(account.balance or 0))
        if balance <= 0:
            return Decimal("0"), {"allowed_qty": 0.0, "reason": "non_positive_balance"}
        max_leverage = Decimal(str(controls["max_portfolio_leverage"]))
        gross = self._current_gross_notional(account.id)
        max_notional = balance * max_leverage
        available_notional = max_notional - gross
        if available_notional <= 0:
            return Decimal("0"), {
                "allowed_qty": 0.0,
                "reason": "portfolio_leverage_too_high",
                "gross_notional": float(gross),
                "max_notional": float(max_notional),
            }
        max_qty = (available_notional / price).quantize(Decimal("0.0001"))
        allowed_qty = min(candidate_qty, max_qty)
        if allowed_qty < 0:
            allowed_qty = Decimal("0")
        return allowed_qty, {
            "allowed_qty": float(allowed_qty),
            "reason": "ok" if allowed_qty >= candidate_qty else "capped_by_portfolio_leverage",
            "gross_notional": float(gross),
            "max_notional": float(max_notional),
        }

    def _latest_price_staleness_seconds(self, symbol: str) -> float | None:
        market_db = SessionLocalMarket()
        try:
            row = market_db.execute(
                select(MarketKline.time)
                .where(MarketKline.symbol == symbol)
                .where(MarketKline.interval == "1m")
                .order_by(MarketKline.time.desc())
                .limit(1)
            ).first()
            if not row or row[0] is None:
                return None
            latest_ts = row[0]
            if latest_ts.tzinfo is None:
                latest_ts = latest_ts.replace(tzinfo=timezone.utc)
            now_utc = datetime.now(timezone.utc)
            return max(0.0, float((now_utc - latest_ts).total_seconds()))
        finally:
            market_db.close()

    def _get_risk_thresholds(self) -> dict:
        daily_cfg = self.db.query(SystemConfig).filter(SystemConfig.key == "PAPER_DAILY_LOSS_LIMIT_PCT").first()
        maxdd_cfg = self.db.query(SystemConfig).filter(SystemConfig.key == "PAPER_MAX_DRAWDOWN_LIMIT_PCT").first()
        daily_limit = self._safe_float(daily_cfg.value if daily_cfg else None, 0.05)
        max_drawdown_limit = self._safe_float(maxdd_cfg.value if maxdd_cfg else None, 0.15)
        daily_limit = min(max(daily_limit, 0.001), 0.99)
        max_drawdown_limit = min(max(max_drawdown_limit, 0.001), 0.99)
        return {
            "daily_loss_limit_pct": daily_limit,
            "max_drawdown_limit_pct": max_drawdown_limit
        }

    def _compute_equity_snapshot(self, user_id: int = None, current_equity: float = None) -> dict:
        account = self.get_or_create_account(user_id)
        if current_equity is None:
            open_positions = self.get_open_positions(user_id)
            symbols = list({p.symbol for p in open_positions})
            latest_prices = self._get_latest_prices(symbols)
            current_equity = self.get_equity(user_id, latest_prices if latest_prices else None)
        daily_start = float(account.daily_start_balance or 100000.0)
        high_water = float(account.high_watermark or 100000.0)
        daily_dd = (current_equity - daily_start) / daily_start if daily_start > 0 else 0.0
        max_dd = (current_equity - high_water) / high_water if high_water > 0 else 0.0
        return {
            "account": account,
            "current_equity": float(current_equity),
            "daily_start_balance": daily_start,
            "high_watermark": high_water,
            "daily_dd": daily_dd,
            "max_dd": max_dd
        }

    def check_portfolio_risk(self, user_id: int = None, current_equity: float = None) -> dict:
        """
        Check Portfolio-Level Risk Limits (Circuit Breakers)
        Returns: {"allowed": bool, "reason": str}
        """
        snapshot = self._compute_equity_snapshot(user_id, current_equity)
        account = snapshot["account"]
        
        if account.is_locked:
            return {"allowed": False, "reason": f"Account Locked: {account.lock_reason}"}
        limits = self._get_risk_thresholds()
        current_equity = snapshot["current_equity"]
        daily_dd = snapshot["daily_dd"]
        max_dd = snapshot["max_dd"]
        if daily_dd < -limits["daily_loss_limit_pct"]:
            account.is_locked = True
            account.lock_reason = f"Daily Loss Limit Hit ({daily_dd*100:.2f}%)"
            self.db.commit()
            return {"allowed": False, "reason": account.lock_reason}
        if max_dd < -limits["max_drawdown_limit_pct"]:
            account.is_locked = True
            account.lock_reason = f"Max Drawdown Limit Hit ({max_dd*100:.2f}%)"
            self.db.commit()
            return {"allowed": False, "reason": account.lock_reason}
        
        high_water = snapshot["high_watermark"]
        if current_equity > high_water:
            account.high_watermark = current_equity
            self.db.commit()

        return {"allowed": True, "reason": "OK"}

    def reset_daily_metrics(self, user_id: int = None, current_equity: float = None):
        """
        Reset Daily Start Balance at 00:00 UTC
        """
        account = self.get_or_create_account(user_id)
        if current_equity is None:
             # If not provided, default to balance (ignoring open PnL if not provided)
             # This is suboptimal but prevents crash. Ideally caller provides Equity.
             current_equity = float(account.balance)
        
        account.daily_start_balance = current_equity
        account.is_locked = False # Reset lock daily? Or manual unlock?
        # Usually daily loss limit resets daily. Max DD lock persists.
        if "Daily Loss" in (account.lock_reason or ""):
             account.is_locked = False
             account.lock_reason = None
             
        self.db.commit()

    def reset_daily_metrics_all(self) -> dict:
        accounts = self.db.execute(select(PaperAccount)).scalars().all()
        reset_count = 0
        for account in accounts:
            positions = self.db.execute(
                select(PaperPosition)
                .where(PaperPosition.account_id == account.id)
                .where(PaperPosition.status == 'OPEN')
            ).scalars().all()
            symbols = list({p.symbol for p in positions})
            latest_prices = self._get_latest_prices(symbols)
            balance = float(account.balance)
            unrealized_pnl = 0.0
            for pos in positions:
                price = latest_prices.get(pos.symbol)
                if price is None:
                    continue
                entry = float(pos.entry_price)
                size = float(pos.size)
                if pos.side == 'LONG':
                    unrealized_pnl += (price - entry) * size
                else:
                    unrealized_pnl += (entry - price) * size
            equity = balance + unrealized_pnl
            account.daily_start_balance = equity
            if "Daily Loss" in (account.lock_reason or ""):
                account.is_locked = False
                account.lock_reason = None
            reset_count += 1
        self.db.commit()
        return {"status": "ok", "reset_count": reset_count}

    def get_risk_state(self, user_id: int = None, current_equity: float = None) -> dict:
        snapshot = self._compute_equity_snapshot(user_id, current_equity)
        account = snapshot["account"]
        limits = self._get_risk_thresholds()
        return {
            "allowed": not bool(account.is_locked),
            "is_locked": bool(account.is_locked),
            "lock_reason": account.lock_reason,
            "current_equity": snapshot["current_equity"],
            "daily_start_balance": snapshot["daily_start_balance"],
            "high_watermark": snapshot["high_watermark"],
            "daily_dd": snapshot["daily_dd"],
            "max_dd": snapshot["max_dd"],
            "daily_loss_limit_pct": limits["daily_loss_limit_pct"],
            "max_drawdown_limit_pct": limits["max_drawdown_limit_pct"]
        }


    def get_pending_orders(self, user_id: int = None) -> list[PaperOrder]:
        """
        Get all pending (LIMIT/STOP_LIMIT) orders.
        """
        account = self.get_or_create_account(user_id)
        orders = self.db.execute(
            select(PaperOrder)
            .where(PaperOrder.account_id == account.id)
            .where(PaperOrder.status == 'PENDING')
            .order_by(PaperOrder.created_at.asc())
        ).scalars().all()
        return orders

    def place_order(self, symbol: str, side: str, order_type: str, quantity: float, current_price: float, trigger_price: float = None, sl: float = None, tp: float = None, session_id: str = None, order_book: dict = None, user_id: int = 1):
        """
        Place an order. If MARKET, execute immediately. If LIMIT/STOP_LIMIT, create PENDING order.
        """
        order_type = order_type.upper()
        if order_type == 'MARKET':
            return self.execute_market_order(symbol, side, quantity, current_price, sl, tp, session_id, order_book, user_id)
            
        account = self.get_or_create_account(user_id)
        # Calculate intent loosely (actual intent resolved at execution)
        intent = "OPEN" # Default, can be refined when triggered
        
        # Determine the price to store for the order (LIMIT price or STOP trigger)
        store_price = trigger_price if trigger_price else current_price

        order = PaperOrder(
            account_id=account.id,
            symbol=symbol,
            side=side.upper(),
            type=order_type,
            intent=intent,
            price=Decimal(str(store_price)),
            quantity=Decimal(str(quantity)),
            status='PENDING',
            session_id=session_id
        )
        # Store SL/TP in a JSON field if we had one, but since PaperOrder doesn't have sl/tp columns, 
        # we might need to add them or rely on the trigger execution to fetch them from session.
        # For MVP, we will execute without SL/TP if it's a limit order, OR we can alter the PaperOrder model.
        # Given we shouldn't change DB schema heavily right now, we will add them later or just store in intent temporarily.
        self.db.add(order)
        self.db.commit()
        
        return order, {"status": "PENDING", "order_id": str(order.id), "mode": "LIMIT"}

    def check_and_trigger_pending_orders(self, current_prices: dict):
        """
        Called by market_streamer on every new price tick to trigger pending limit orders.
        """
        pending_orders = self.db.execute(
            select(PaperOrder).where(PaperOrder.status == 'PENDING')
        ).scalars().all()
        
        triggered_count = 0
        for order in pending_orders:
            if order.symbol not in current_prices:
                continue
                
            curr_price = current_prices[order.symbol]
            order_price = float(order.price)
            
            is_triggered = False
            if order.type == 'LIMIT':
                if order.side == 'BUY' and curr_price <= order_price:
                    is_triggered = True
                elif order.side == 'SELL' and curr_price >= order_price:
                    is_triggered = True
            elif order.type == 'STOP_LIMIT':
                if order.side == 'BUY' and curr_price >= order_price:
                    is_triggered = True
                elif order.side == 'SELL' and curr_price <= order_price:
                    is_triggered = True
                    
            if is_triggered:
                print(f"[Sim Match] Triggering PENDING {order.type} {order.side} for {order.symbol} at {curr_price} (Target: {order_price})")
                # Execute as market order at current price
                try:
                    # We need to temporarily change status to PROCESSING to avoid double triggers
                    order.status = 'PROCESSING'
                    self.db.commit()
                    
                    trigger_account = self.db.execute(
                        select(PaperAccount).where(PaperAccount.id == order.account_id)
                    ).scalar_one_or_none()
                    trigger_user_id = trigger_account.user_id if trigger_account and trigger_account.user_id is not None else 1
                    _, exec_info = self.execute_market_order(
                        symbol=order.symbol,
                        side=order.side,
                        quantity=float(order.quantity),
                        current_price=curr_price,
                        session_id=order.session_id,
                        user_id=trigger_user_id
                    )
                    
                    # Update original order status
                    order.status = 'FILLED' if exec_info.get("mode") != "UNKNOWN" else 'FAILED'
                    order.filled_at = datetime.now(timezone.utc)
                    self.db.commit()
                    triggered_count += 1
                except Exception as e:
                    print(f"[Sim Match] Failed to execute triggered order {order.id}: {e}")
                    order.status = 'PENDING' # Revert
                    self.db.commit()
                    
        return triggered_count

    def execute_market_order(self, symbol: str, side: str, quantity: float, current_price: float, sl: float = None, tp: float = None, session_id: str = None, order_book: dict = None, user_id: int = 1):
        """
        Execute a market order immediately with basic margin and PnL realization.
        Supports Slippage Simulation via order_book and Liquidity Constraint.
        """
        account = self.get_or_create_account(user_id)
        controls = self._get_execution_controls()
        quantity = Decimal(str(quantity))
        requested_price = float(current_price)
        
        # 0. Slippage Simulation & Liquidity Check
        slippage_info = {"avg_price": float(current_price), "slippage_pct": 0.0}
        max_liquidity_qty = float('inf')
        
        if order_book:
            try:
                # order_book structure: {'bids': [[price, qty], ...], 'asks': [[price, qty], ...]}
                # If BUY -> consume Asks (Low to High)
                # If SELL -> consume Bids (High to Low)
                levels = order_book['asks'] if side.upper() == 'BUY' else order_book['bids']
                
                # Calculate Max Available Liquidity in current OrderBook snapshot
                total_book_qty = sum(float(item[1]) for item in levels)
                max_liquidity_qty = total_book_qty
                
                # Constraint: Cannot fill more than available in the book (simulating deep liquidity exhaustion)
                # In reality, you'd eat into hidden liquidity or wait, but for paper trading, we cap it.
                # Or better: Fill what we can, reject the rest (Partial Fill).
                # For now, let's allow "virtual liquidity" at the worst price if size > book, but penalize heavily.
                
                target_qty = float(quantity)
                remaining_qty = target_qty
                total_cost = 0.0
                best_price = float(levels[0][0])
                
                filled_qty = 0.0
                
                for item in levels:
                    p, q = float(item[0]), float(item[1])
                    fill = min(remaining_qty, q)
                    total_cost += fill * p
                    remaining_qty -= fill
                    filled_qty += fill
                    if remaining_qty <= 0: break
                
                # If still remaining (market depth insufficient), fill at last price + penalty (Virtual Impact)
                if remaining_qty > 0:
                     last_price = float(levels[-1][0])
                     # Virtual Impact: Price moves 0.1% per 1% of excess volume relative to book depth?
                     # Simple approach: Fill rest at last_price * (1 +/- 0.005)
                     penalty_factor = 1.005 if side.upper() == 'BUY' else 0.995
                     virtual_price = last_price * penalty_factor
                     total_cost += remaining_qty * virtual_price
                     print(f"⚠️ [Liquidity] Order size {target_qty} > Book Depth {filled_qty}. Filling remainder at virtual price {virtual_price:.2f}")
                
                avg_exec_price = total_cost / target_qty
                slippage_pct = abs(avg_exec_price - best_price) / best_price
                
                slippage_info = {
                    "avg_price": avg_exec_price,
                    "slippage_pct": slippage_pct,
                    "best_price": best_price
                }
                print(f"📉 [Slippage] {side} {quantity} {symbol}: Best {best_price} -> Avg {avg_exec_price:.2f} (Slip: {slippage_pct*100:.4f}%)")
                
                # Update execution price
                current_price = avg_exec_price
                
            except Exception as e:
                print(f"⚠️ [Slippage] Calculation failed: {e}. Using base price.")

        min_slippage_rate = controls["min_slippage_bps"] / 10000.0
        if requested_price > 0 and min_slippage_rate > 0:
            current_slippage = abs(float(current_price) - requested_price) / requested_price
            if current_slippage < min_slippage_rate:
                if side.upper() == "BUY":
                    current_price = requested_price * (1 + min_slippage_rate)
                else:
                    current_price = requested_price * (1 - min_slippage_rate)

        price = Decimal(str(current_price))
        value = quantity * price
        
        # Simple Margin Requirement (e.g., 10% margin / 10x leverage)
        margin_rate = Decimal("0.1")
        required_margin = value * margin_rate
        
        sl_dec = Decimal(str(sl)) if sl else None
        tp_dec = Decimal(str(tp)) if tp else None

        # Return info about execution
        execution_info = {
            "pnl": 0.0,
            "closed_session_id": None,
            "mode": "OPEN",
            "order_id": None,
            "intent": None # Will be set to OPEN_LONG, CLOSE_SHORT, etc.
        }
        
        # 1. Check for "Reduction Only" status (If balance is critically low)
        is_reduction_only = account.balance <= 0
        
        # Determine if this order is purely reducing risk
        # (This is simplified: in reality we'd check if side is opposite to existing position)
        
        # 2. Update Position & Realize PnL
        if side.upper() == 'BUY':
            # Check for existing SHORT positions to close first (Short Covering)
            short_positions = self.db.execute(
                select(PaperPosition)
                .where(PaperPosition.account_id == account.id)
                .where(PaperPosition.symbol == symbol)
                .where(PaperPosition.status == 'OPEN')
                .where(PaperPosition.side == 'SHORT')
                .order_by(PaperPosition.opened_at) # FIFO
            ).scalars().all()
            
            remaining_qty = quantity
            
            # Close Shorts
            if short_positions:
                execution_info["intent"] = "CLOSE_SHORT" # Primary intent if closing
            
            for pos in short_positions:
                if remaining_qty <= 0: break
                
                pos_size = pos.size
                close_qty = min(remaining_qty, pos_size)
                
                # Realize PnL: (Entry - Exit) * Size for Short
                # PnL = (Entry - Exit) * Size
                pnl = (pos.entry_price - price) * close_qty
                
                # Update Balance
                account.balance += pnl
                
                execution_info["pnl"] += float(pnl)
                execution_info["closed_session_id"] = pos.session_id
                execution_info["mode"] = "CLOSE"
                
                if remaining_qty >= pos_size:
                    pos.status = 'CLOSED'
                    pos.closed_at = datetime.now()
                    remaining_qty -= pos_size
                else:
                    pos.size -= remaining_qty
                    remaining_qty = Decimal("0") # Fixed type mismatch
            
            # Open Long (Remaining) - Only if NOT reduction only
            if remaining_qty > 0:
                staleness_sec = self._latest_price_staleness_seconds(symbol)
                if staleness_sec is None or staleness_sec > controls["max_staleness_seconds"]:
                    print(f"⚠️ [PaperTrading] Order Rejected: stale market data ({staleness_sec}s) for {symbol}")
                    quantity = quantity - remaining_qty
                    remaining_qty = Decimal("0")
                if remaining_qty > 0 and execution_info["intent"] == "CLOSE_SHORT":
                     # If we closed shorts AND still have quantity, it's a Flip or partial open
                     # If we had shorts, and now we are opening long -> FLIP_TO_LONG
                     execution_info["intent"] = "FLIP_TO_LONG"
                elif remaining_qty > 0:
                     execution_info["intent"] = "OPEN_LONG"

                if remaining_qty > 0 and is_reduction_only:
                    print(f"⚠️ [PaperTrading] Order Rejected: Account in Reduction-Only mode (Balance: {account.balance})")
                    quantity = quantity - remaining_qty
                elif remaining_qty > 0:
                    # Check if enough balance for margin
                    if account.balance < (remaining_qty * price * margin_rate):
                        print(f"⚠️ [PaperTrading] Order Partially Rejected: Insufficient Margin")
                        if price > 0:
                            affordable_qty = (account.balance / (price * margin_rate)).quantize(Decimal("0.0001"))
                            if affordable_qty > 0:
                                remaining_qty = affordable_qty
                            else:
                                remaining_qty = Decimal("0")
                        else:
                            remaining_qty = Decimal("0")
                            
                    if remaining_qty > 0:
                        allowed_qty, leverage_guard = self._cap_open_qty_by_leverage(
                            account=account,
                            candidate_qty=remaining_qty,
                            price=price,
                            controls=controls
                        )
                        trimmed = remaining_qty - allowed_qty
                        if trimmed > 0:
                            quantity -= trimmed
                            print(f"⚠️ [PaperTrading] Leverage gate capped LONG open qty: {remaining_qty} -> {allowed_qty}")
                        if allowed_qty <= 0:
                            execution_info["leverage_guard"] = leverage_guard
                            remaining_qty = Decimal("0")
                        else:
                            remaining_qty = allowed_qty
                            execution_info["leverage_guard"] = leverage_guard

                    if remaining_qty > 0:
                        position = PaperPosition(
                            account_id=account.id,
                            symbol=symbol,
                            side='LONG',
                            entry_price=price,
                            size=remaining_qty,
                            status='OPEN',
                            stop_loss=sl_dec,
                            take_profit=tp_dec,
                            session_id=session_id
                        )
                        self.db.add(position)
        
        elif side.upper() == 'SELL':
            # Check for existing LONG positions to close first (Long Selling)
            long_positions = self.db.execute(
                select(PaperPosition)
                .where(PaperPosition.account_id == account.id)
                .where(PaperPosition.symbol == symbol)
                .where(PaperPosition.status == 'OPEN')
                .where(PaperPosition.side == 'LONG')
                .order_by(PaperPosition.opened_at) # FIFO
            ).scalars().all()

            remaining_qty = quantity
            
            # Close Longs
            if long_positions:
                execution_info["intent"] = "CLOSE_LONG"

            for pos in long_positions:
                if remaining_qty <= 0: break
                
                pos_size = pos.size
                close_qty = min(remaining_qty, pos_size)
                
                # Realize PnL: (Exit - Entry) * Size for Long
                pnl = (price - pos.entry_price) * close_qty
                account.balance += pnl
                
                execution_info["pnl"] += float(pnl)
                execution_info["closed_session_id"] = pos.session_id
                execution_info["mode"] = "CLOSE"

                if remaining_qty >= pos_size:
                    pos.status = 'CLOSED'
                    pos.closed_at = datetime.now()
                    remaining_qty -= pos_size
                else:
                    pos.size -= remaining_qty
                    remaining_qty = Decimal("0")
            
            # Open Short (Remaining) - Only if NOT reduction only
            if remaining_qty > 0:
                staleness_sec = self._latest_price_staleness_seconds(symbol)
                if staleness_sec is None or staleness_sec > controls["max_staleness_seconds"]:
                    print(f"⚠️ [PaperTrading] Order Rejected: stale market data ({staleness_sec}s) for {symbol}")
                    quantity = quantity - remaining_qty
                    remaining_qty = Decimal("0")
                if remaining_qty > 0 and execution_info["intent"] == "CLOSE_LONG":
                    execution_info["intent"] = "FLIP_TO_SHORT"
                elif remaining_qty > 0:
                    execution_info["intent"] = "OPEN_SHORT"

                if remaining_qty > 0 and is_reduction_only:
                    print(f"⚠️ [PaperTrading] Order Rejected: Account in Reduction-Only mode (Balance: {account.balance})")
                    quantity = quantity - remaining_qty
                elif remaining_qty > 0:
                    # Check if enough balance for margin
                    if account.balance < (remaining_qty * price * margin_rate):
                        print(f"⚠️ [PaperTrading] Order Partially Rejected: Insufficient Margin")
                        if price > 0:
                            affordable_qty = (account.balance / (price * margin_rate)).quantize(Decimal("0.0001"))
                            if affordable_qty > 0:
                                remaining_qty = affordable_qty
                            else:
                                remaining_qty = Decimal("0")
                        else:
                            remaining_qty = Decimal("0")

                    if remaining_qty > 0:
                        allowed_qty, leverage_guard = self._cap_open_qty_by_leverage(
                            account=account,
                            candidate_qty=remaining_qty,
                            price=price,
                            controls=controls
                        )
                        trimmed = remaining_qty - allowed_qty
                        if trimmed > 0:
                            quantity -= trimmed
                            print(f"⚠️ [PaperTrading] Leverage gate capped SHORT open qty: {remaining_qty} -> {allowed_qty}")
                        if allowed_qty <= 0:
                            execution_info["leverage_guard"] = leverage_guard
                            remaining_qty = Decimal("0")
                        else:
                            remaining_qty = allowed_qty
                            execution_info["leverage_guard"] = leverage_guard

                    if remaining_qty > 0:
                        position = PaperPosition(
                            account_id=account.id,
                            symbol=symbol,
                            side='SHORT',
                            entry_price=price,
                            size=remaining_qty,
                            status='OPEN',
                            stop_loss=sl_dec,
                            take_profit=tp_dec,
                            session_id=session_id
                        )
                        self.db.add(position)
        
        fee_rate = Decimal(str(controls["taker_fee_bps"] / 10000.0))
        executed_notional = quantity * price if quantity > 0 else Decimal("0")
        fee_amount = executed_notional * fee_rate
        if fee_amount > 0:
            account.balance -= fee_amount
            execution_info["pnl"] -= float(fee_amount)

        if quantity <= 0 and execution_info["mode"] == "OPEN":
            execution_info["mode"] = "REJECTED"

        # Create Order Record with updated final quantity
        order = PaperOrder(
            account_id=account.id,
            symbol=symbol,
            side=side.upper(),
            type='MARKET',
            intent=execution_info["intent"] or 'MARKET', # Store intent
            price=price,
            quantity=quantity, # This might be inaccurate if partial fill logic is buggy.
            status='FILLED' if quantity > 0 else 'REJECTED',
            pnl=execution_info["pnl"] if execution_info["mode"] == "CLOSE" else None, # Store PnL
            session_id=session_id,
            filled_at=datetime.now()
        )
        self.db.add(order)
        self.db.commit() # Commit to get ID
        
        execution_info["order_id"] = str(order.id)
        execution_info["status"] = order.status

        return order, execution_info

    def cancel_pending_orders(self, user_id: int = None, symbol: str = None) -> dict:
        account = self.get_or_create_account(user_id)
        query = (
            select(PaperOrder)
            .where(PaperOrder.account_id == account.id)
            .where(PaperOrder.status == 'PENDING')
        )
        if symbol:
            query = query.where(PaperOrder.symbol == symbol)
        orders = self.db.execute(query).scalars().all()
        if not orders:
            return {"cancelled": 0, "symbol": symbol}
        now = datetime.now(timezone.utc)
        for o in orders:
            o.status = "CANCELLED"
            o.filled_at = now
        self.db.commit()
        return {"cancelled": len(orders), "symbol": symbol}

    def get_open_positions(self, user_id: int = None) -> list[PaperPosition]:
        """
        Get all open positions for an account.
        """
        account = self.get_or_create_account(user_id)
        positions = self.db.execute(
            select(PaperPosition)
            .where(PaperPosition.account_id == account.id)
            .where(PaperPosition.status == 'OPEN')
            .order_by(PaperPosition.opened_at.desc())
        ).scalars().all()
        return positions

    def get_order_history(self, user_id: int = None, limit: int = 20) -> list[PaperOrder]:
        """
        Get recent order history.
        """
        account = self.get_or_create_account(user_id)
        orders = self.db.execute(
            select(PaperOrder)
            .where(PaperOrder.account_id == account.id)
            .order_by(PaperOrder.created_at.desc())
            .limit(limit)
        ).scalars().all()
        return orders
