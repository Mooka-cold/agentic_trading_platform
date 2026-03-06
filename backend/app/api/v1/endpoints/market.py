from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.session import get_market_db
from datetime import datetime, timedelta
import pandas as pd

router = APIRouter()

@router.get("/kline")
def get_kline_data(
    symbol: str = Query(..., description="Trading pair, e.g. BTC/USDT"),
    interval: str = Query("1m", description="Timeframe: 1m, 1h, 4h, 1d"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_market_db)
) -> Any:
    """
    Get historical K-line data with calculated indicators (RSI, MACD, MA).
    """
    query = text("""
        SELECT time, open, high, low, close, volume 
        FROM market_klines 
        WHERE symbol = :symbol AND interval = :interval
        ORDER BY time DESC
        LIMIT :limit
    """)
    
    result = db.execute(query, {"symbol": symbol, "interval": interval, "limit": limit}).fetchall()
    
    if not result:
        return []

    # Format for DataFrame
    data = []
    for row in reversed(result):
        data.append({
            "time": int(row.time.timestamp()),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(row.volume)
        })
        
    df = pd.DataFrame(data)
    
    # --- Calculate Indicators ---
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).abs().rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # MACD (12, 26, 9)
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    
    df['macd'] = macd
    df['macd_signal'] = signal
    df['macd_hist'] = hist
    
    # MA (20, 50)
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['ma50'] = df['close'].rolling(window=50).mean()

    df['sma_7'] = df['close'].rolling(window=7).mean()
    df['sma_25'] = df['close'].rolling(window=25).mean()
    df['ema_7'] = df['close'].ewm(span=7, adjust=False).mean()
    df['ema_25'] = df['close'].ewm(span=25, adjust=False).mean()

    ma20 = df['close'].rolling(window=20).mean()
    std20 = df['close'].rolling(window=20).std()
    df['bb_upper'] = ma20 + (std20 * 2)
    df['bb_middle'] = ma20
    df['bb_lower'] = ma20 - (std20 * 2)

    high_low = (df['high'] - df['low']).abs()
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr_14'] = tr.rolling(window=14).mean()
    
    def _last_valid_time(series: pd.Series) -> int | None:
        valid_times = df.loc[series.notna(), 'time']
        if valid_times.empty:
            return None
        return int(valid_times.iloc[-1])

    calc_times = {
        "rsi_calc_time": _last_valid_time(df['rsi']),
        "macd_calc_time": _last_valid_time(df['macd']),
        "macd_signal_calc_time": _last_valid_time(df['macd_signal']),
        "macd_hist_calc_time": _last_valid_time(df['macd_hist']),
        "ma20_calc_time": _last_valid_time(df['ma20']),
        "ma50_calc_time": _last_valid_time(df['ma50']),
        "sma_7_calc_time": _last_valid_time(df['sma_7']),
        "sma_25_calc_time": _last_valid_time(df['sma_25']),
        "ema_7_calc_time": _last_valid_time(df['ema_7']),
        "ema_25_calc_time": _last_valid_time(df['ema_25']),
        "bb_upper_calc_time": _last_valid_time(df['bb_upper']),
        "bb_middle_calc_time": _last_valid_time(df['bb_middle']),
        "bb_lower_calc_time": _last_valid_time(df['bb_lower']),
        "atr_14_calc_time": _last_valid_time(df['atr_14'])
    }

    for key, value in calc_times.items():
        df[key] = value

    df = df.where(pd.notnull(df), None)
    
    return df.to_dict('records')
