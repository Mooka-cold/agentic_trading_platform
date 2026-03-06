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
    Get historical K-line data with indicators directly from DB.
    """
    # Select all indicators stored by Streamer
    # Note: DB column names match the model (rsi_14, sma_7, etc.)
    # We alias them to match frontend expectations if needed, 
    # but frontend seems to map them manually or use same names.
    # Let's check frontend mapping:
    # rsi -> rsi_14 (frontend uses latest.rsi ?? null)
    # Actually frontend checks `latest.rsi` but Streamer saves `rsi_14`.
    # Let's return both or alias it to be safe.
    
    query = text("""
        SELECT 
            time, open, high, low, close, volume,
            rsi_14 as rsi,
            macd, macd_signal, macd_hist,
            sma_7, sma_25, 
            ema_7, ema_25,
            bb_upper, bb_middle, bb_lower,
            atr_14
        FROM market_klines 
        WHERE symbol = :symbol AND interval = :interval
        ORDER BY time DESC
        LIMIT :limit
    """)
    
    result = db.execute(query, {"symbol": symbol, "interval": interval, "limit": limit}).fetchall()
    
    if not result:
        return []

    data = []
    # Reverse to return chronological order (oldest first) as chart libraries usually expect
    for row in reversed(result):
        ts = int(row.time.timestamp())
        
        # Helper to safely get float or None
        def safe_val(val):
            return float(val) if val is not None else None

        item = {
            "time": ts,
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(row.volume),
            
            # Indicators
            "rsi": safe_val(row.rsi),
            "macd": safe_val(row.macd),
            "macd_signal": safe_val(row.macd_signal),
            "macd_hist": safe_val(row.macd_hist),
            
            # MA20/MA50 are not explicitly in DB (streamer calcs BB_Middle which is SMA20)
            # We can map bb_middle to ma20 if needed, or just return what we have.
            # Frontend asks for ma20, ma50. Streamer saves bb_middle (SMA20).
            # Let's map ma20 = bb_middle. ma50 might be missing in DB if streamer doesn't save it.
            # Streamer saves: rsi_14, macd*, bb*, atr_14, sma_7, ema_25.
            # Wait, Streamer saves `ema_25` but frontend asks for `ema_7` and `ema_25`.
            # Let's check Streamer save_to_db again.
            # Streamer saves: rsi_14, macd, macd_signal, macd_hist, bb_upper, bb_middle, bb_lower, atr_14, sma_7, ema_25.
            # It seems Streamer DOES NOT save ma50, ema_7, sma_25.
            # So for those missing ones, we might still return None or need to add them to DB schema later.
            # For now, return what we have in DB.
            
            "ma20": safe_val(row.bb_middle), # BB Middle is SMA 20
            "ma50": None, # Not in DB
            
            "sma_7": safe_val(row.sma_7),
            "sma_25": safe_val(row.sma_25), # Added to query just in case, but check schema
            "ema_7": safe_val(row.ema_7),   # Added to query
            "ema_25": safe_val(row.ema_25),
            
            "bb_upper": safe_val(row.bb_upper),
            "bb_middle": safe_val(row.bb_middle),
            "bb_lower": safe_val(row.bb_lower),
            "atr_14": safe_val(row.atr_14),
            
            # Calc times - since we fetch from DB, the calc time is the candle time
            # IF the value exists.
            "rsi_calc_time": ts if row.rsi is not None else None,
            "macd_calc_time": ts if row.macd is not None else None,
            "macd_signal_calc_time": ts if row.macd_signal is not None else None,
            "macd_hist_calc_time": ts if row.macd_hist is not None else None,
            "ma20_calc_time": ts if row.bb_middle is not None else None,
            "ma50_calc_time": None,
            "sma_7_calc_time": ts if row.sma_7 is not None else None,
            "sma_25_calc_time": ts if row.sma_25 is not None else None,
            "ema_7_calc_time": ts if row.ema_7 is not None else None,
            "ema_25_calc_time": ts if row.ema_25 is not None else None,
            "bb_upper_calc_time": ts if row.bb_upper is not None else None,
            "bb_middle_calc_time": ts if row.bb_middle is not None else None,
            "bb_lower_calc_time": ts if row.bb_lower is not None else None,
            "atr_14_calc_time": ts if row.atr_14 is not None else None
        }
        data.append(item)
        
    return data
