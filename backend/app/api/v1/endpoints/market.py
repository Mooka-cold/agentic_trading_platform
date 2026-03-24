from typing import Any, List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.session import get_user_db, get_market_db
from app.services.macro_data import MacroDataService
from app.services.onchain_data import OnChainDataService
from datetime import datetime, timedelta
import pandas as pd
from shared.core.symbols import get_schedule_symbols_from_env

router = APIRouter()

def _active_symbols() -> List[str]:
    return get_schedule_symbols_from_env()

@router.get("/symbols")
def get_market_symbols() -> Dict[str, Any]:
    symbols = _active_symbols()
    return {"symbols": symbols, "count": len(symbols)}

@router.get("/ticker")
async def get_market_ticker(
    symbol: str = Query(..., description="Trading pair, e.g. BTC/USDT"),
    levels: int = Query(default=5, ge=1, le=20, description="Order book levels to return")
) -> Any:
    """
    Get real-time ticker and depth summary from Redis cache.
    Extremely fast endpoint for dashboard updates.
    """
    from app.services.redis_stream import redis_stream
    
    ticker_key = f"market:ticker:{symbol}"
    depth_key = f"market:orderbook:{symbol}"
    
    ticker_data = await redis_stream.get_cache(ticker_key)
    depth_data = await redis_stream.get_cache(depth_key)
    
    if not ticker_data:
        return {"symbol": symbol, "price": 0, "status": "connecting"}
        
    price = float(ticker_data.get('last', 0))
    change_24h = float(ticker_data.get('percentage', 0))
    
    bid_price = 0
    bid_qty = 0
    ask_price = 0
    ask_qty = 0
    bids_top: List[List[float]] = []
    asks_top: List[List[float]] = []
    bid_depth_qty = 0.0
    ask_depth_qty = 0.0
    bid_depth_notional = 0.0
    ask_depth_notional = 0.0
    
    if depth_data:
        bids = depth_data.get('bids', [])
        asks = depth_data.get('asks', [])
        if bids:
            bid_price = float(bids[0][0])
            bid_qty = float(bids[0][1])
            bids_top = [[float(x[0]), float(x[1])] for x in bids[:levels]]
            bid_depth_qty = sum(float(x[1]) for x in bids_top)
            bid_depth_notional = sum(float(x[0]) * float(x[1]) for x in bids_top)
        if asks:
            ask_price = float(asks[0][0])
            ask_qty = float(asks[0][1])
            asks_top = [[float(x[0]), float(x[1])] for x in asks[:levels]]
            ask_depth_qty = sum(float(x[1]) for x in asks_top)
            ask_depth_notional = sum(float(x[0]) * float(x[1]) for x in asks_top)
    spread = abs(ask_price - bid_price) if ask_price > 0 and bid_price > 0 else 0.0
    spread_pct = (spread / price) * 100 if price > 0 else 0.0
    total_depth_notional = bid_depth_notional + ask_depth_notional
    imbalance = ((bid_depth_notional - ask_depth_notional) / total_depth_notional) if total_depth_notional > 0 else 0.0
            
    return {
        "symbol": symbol,
        "price": price,
        "change24h": change_24h,
        "bid": bid_price,
        "bid_qty": bid_qty,
        "ask": ask_price,
        "ask_qty": ask_qty,
        "timestamp": ticker_data.get('timestamp'),
        "levels": levels,
        "bids": bids_top,
        "asks": asks_top,
        "spread": spread,
        "spread_pct": spread_pct,
        "bid_depth_qty": bid_depth_qty,
        "ask_depth_qty": ask_depth_qty,
        "bid_depth_notional": bid_depth_notional,
        "ask_depth_notional": ask_depth_notional,
        "depth_imbalance": imbalance
    }

@router.get("/seconds")
def get_second_series(
    symbol: str = Query(..., description="Trading pair, e.g. BTC/USDT"),
    window: int = Query(600, ge=60, le=600)
) -> Dict[str, Any]:
    from app.services.price_streamer import price_streamer
    points = price_streamer.get_recent_seconds(symbol, window)
    return {
        "symbol": symbol,
        "window": window,
        "points": points
    }

@router.get("/macro")
def get_macro_metrics(
    db: Session = Depends(get_user_db)
) -> Dict[str, Any]:
    """
    Get latest macro economic metrics.
    """
    service = MacroDataService(db)
    return service.get_latest_snapshot()

@router.get("/onchain/{symbol}")
def get_onchain_metrics(
    symbol: str,
    db: Session = Depends(get_user_db)
) -> Dict[str, Any]:
    """
    Get latest on-chain metrics for a symbol.
    """
    service = OnChainDataService(db)
    return service.get_latest_snapshot(symbol)

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

    # Helper to safely get float or None
    def safe_val(val):
        return float(val) if val is not None else None

    # Reverse to return chronological order (oldest first) as chart libraries usually expect
    for row in reversed(result):
        ts = int(row.time.timestamp())

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
