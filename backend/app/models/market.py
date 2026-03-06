from sqlalchemy import Column, String, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class MarketKline(Base):
    __tablename__ = "market_klines"

    time = Column(DateTime(timezone=True), primary_key=True)
    symbol = Column(String, primary_key=True)
    interval = Column(String, primary_key=True) # 1m, 1h, 1d
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    source = Column(String) # binance, okx

    # --- Technical Indicators ---
    # Trend
    sma_7 = Column(Float, nullable=True)
    sma_25 = Column(Float, nullable=True)
    ema_7 = Column(Float, nullable=True)
    ema_25 = Column(Float, nullable=True)
    
    # Momentum
    rsi_14 = Column(Float, nullable=True)
    macd = Column(Float, nullable=True)
    macd_signal = Column(Float, nullable=True)
    macd_hist = Column(Float, nullable=True)
    
    # Volatility
    bb_upper = Column(Float, nullable=True)
    bb_middle = Column(Float, nullable=True)
    bb_lower = Column(Float, nullable=True)
    atr_14 = Column(Float, nullable=True)
