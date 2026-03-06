import uuid
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.base import Base
from app.models.user import User  # Assuming User model exists
from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey, text, Text
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

# --- Models (Ideally should be in app/models/paper.py) ---

class PaperAccount(Base):
    __tablename__ = "paper_accounts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, nullable=True)
    balance = Column(Numeric(20, 8), nullable=False, default=100000.0)
    currency = Column(String(10), nullable=False, default='USDT')
    created_at = Column(DateTime(timezone=True), server_default=text('now()'))
    updated_at = Column(DateTime(timezone=True), server_default=text('now()'), onupdate=datetime.now)

class PaperOrder(Base):
    __tablename__ = "paper_orders"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("paper_accounts.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False) # BUY/SELL
    type = Column(String(10), nullable=False) # MARKET/LIMIT
    price = Column(Numeric(20, 8), nullable=True)
    quantity = Column(Numeric(20, 8), nullable=False)
    status = Column(String(20), nullable=False, default='PENDING')
    session_id = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text('now()'))
    filled_at = Column(DateTime(timezone=True), nullable=True)

class TradeReflection(Base):
    __tablename__ = "trade_reflections"
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

    def execute_market_order(self, symbol: str, side: str, quantity: float, current_price: float, sl: float = None, tp: float = None, session_id: str = None):
        """
        Execute a market order immediately with basic margin and PnL realization.
        """
        account = self.get_or_create_account()
        quantity = Decimal(str(quantity))
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
            "mode": "OPEN"
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
            for pos in short_positions:
                if remaining_qty <= 0: break
                
                pos_size = pos.size
                close_qty = min(remaining_qty, pos_size)
                
                # Realize PnL: (Entry - Exit) * Size for Short
                pnl = (pos.entry_price - price) * close_qty
                account.balance += pnl # Add realized PnL to balance
                execution_info["pnl"] += float(pnl)
                execution_info["closed_session_id"] = pos.session_id
                execution_info["mode"] = "CLOSE"
                
                if remaining_qty >= pos_size:
                    pos.status = 'CLOSED'
                    pos.closed_at = datetime.now()
                    remaining_qty -= pos_size
                else:
                    pos.size -= remaining_qty
                    remaining_qty = 0
            
            # Open Long (Remaining) - Only if NOT reduction only
            if remaining_qty > 0:
                if is_reduction_only:
                    print(f"⚠️ [PaperTrading] Order Rejected: Account in Reduction-Only mode (Balance: {account.balance})")
                    # We return the order as REJECTED or just don't fill the rest
                    # For simplicity, we fill 0 for the remaining
                    quantity = quantity - remaining_qty
                else:
                    # Check if enough balance for margin
                    if account.balance < (remaining_qty * price * margin_rate):
                        print(f"⚠️ [PaperTrading] Order Partially Rejected: Insufficient Margin")
                        # Adjust quantity to what we can afford
                        affordable_qty = (account.balance / (price * margin_rate)).quantize(Decimal("0.00000001"))
                        if affordable_qty > 0:
                            remaining_qty = affordable_qty
                            quantity = (quantity - remaining_qty) + affordable_qty
                        else:
                            remaining_qty = 0
                            quantity = quantity - remaining_qty

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
                    remaining_qty = 0
            
            # Open Short (Remaining) - Only if NOT reduction only
            if remaining_qty > 0:
                if is_reduction_only:
                    print(f"⚠️ [PaperTrading] Order Rejected: Account in Reduction-Only mode (Balance: {account.balance})")
                    quantity = quantity - remaining_qty
                else:
                    # Check if enough balance for margin
                    if account.balance < (remaining_qty * price * margin_rate):
                        print(f"⚠️ [PaperTrading] Order Partially Rejected: Insufficient Margin")
                        affordable_qty = (account.balance / (price * margin_rate)).quantize(Decimal("0.00000001"))
                        if affordable_qty > 0:
                            remaining_qty = affordable_qty
                            quantity = (quantity - remaining_qty) + affordable_qty
                        else:
                            remaining_qty = 0
                            quantity = quantity - remaining_qty

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

        # Create Order Record with updated final quantity
        order = PaperOrder(
            account_id=account.id,
            symbol=symbol,
            side=side.upper(),
            type='MARKET',
            price=price,
            quantity=quantity,
            status='FILLED' if quantity > 0 else 'REJECTED',
            session_id=session_id,
            filled_at=datetime.now()
        )
        self.db.add(order)

        self.db.commit()
        return order, execution_info

    def get_open_positions(self, user_id: int = None) -> list[PaperPosition]:
        """
        Get all open positions for an account.
        """
        account = self.get_or_create_account(user_id)
        positions = self.db.execute(
            select(PaperPosition)
            .where(PaperPosition.account_id == account.id)
            .where(PaperPosition.status == 'OPEN')
        ).scalars().all()
        return positions
