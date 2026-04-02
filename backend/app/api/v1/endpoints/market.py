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

def _interval_to_seconds(interval: str) -> Optional[int]:
    mapping = {"1s": 1, "1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
    return mapping.get(interval)

def _rollup_symbol_interval(db: Session, symbol: str, src_interval: str, dst_interval: str, limit_hint: int = 300) -> int:
    src_seconds = _interval_to_seconds(src_interval)
    dst_seconds = _interval_to_seconds(dst_interval)
    if src_seconds is None or dst_seconds is None or dst_seconds <= src_seconds or (dst_seconds % src_seconds) != 0:
        return 0

    last_dst = db.execute(
        text(
            """
            SELECT MAX(time) AS last_time
            FROM market_klines
            WHERE symbol = :symbol AND interval = :interval
            """
        ),
        {"symbol": symbol, "interval": dst_interval},
    ).scalar()
    if last_dst:
        start_time = last_dst - timedelta(seconds=dst_seconds)
    else:
        lookback_seconds = min(max(dst_seconds * max(limit_hint, 1), 3600), 7 * 24 * 3600)
        start_time = datetime.utcnow() - timedelta(seconds=lookback_seconds)

    rows = db.execute(
        text(
            """
            SELECT time, open, high, low, close, volume
            FROM market_klines
            WHERE symbol = :symbol AND interval = :interval AND time >= :start_time
            ORDER BY time ASC
            """
        ),
        {"symbol": symbol, "interval": src_interval, "start_time": start_time},
    ).fetchall()
    if len(rows) < 2:
        return 0

    df = pd.DataFrame(
        [
            {
                "time": row.time,
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": float(row.volume or 0.0),
            }
            for row in rows
        ]
    )
    if df.empty:
        return 0

    epoch_sec = (pd.to_datetime(df["time"], utc=True).astype("int64") // 10**9).astype("int64")
    bucket_sec = (epoch_sec // dst_seconds) * dst_seconds
    df["bucket_time"] = pd.to_datetime(bucket_sec, unit="s", utc=True)
    grouped = df.groupby("bucket_time", as_index=False).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    if grouped.empty:
        return 0

    if last_dst is not None:
        grouped = grouped[grouped["bucket_time"] > pd.to_datetime(last_dst, utc=True)]
        if grouped.empty:
            return 0

    grouped = grouped.tail(limit_hint)
    payload = [
        {
            "time": row.bucket_time.to_pydatetime(),
            "symbol": symbol,
            "interval": dst_interval,
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(row.volume),
            "source": f"derived_from_{src_interval}",
        }
        for row in grouped.itertuples(index=False)
    ]
    db.execute(
        text(
            """
            INSERT INTO market_klines (time, symbol, interval, open, high, low, close, volume, source)
            VALUES (:time, :symbol, :interval, :open, :high, :low, :close, :volume, :source)
            ON CONFLICT (time, symbol, interval)
            DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                source = EXCLUDED.source
            """
        ),
        payload,
    )
    db.commit()
    return len(payload)

def _solidify_rollups(db: Session, symbols: List[str], limit_hint: int = 300) -> Dict[str, Dict[str, int]]:
    chain = [("1s", "1m"), ("1m", "5m"), ("5m", "15m"), ("15m", "1h"), ("1h", "4h"), ("4h", "1d")]
    stats: Dict[str, Dict[str, int]] = {}
    for symbol in symbols:
        symbol_stats: Dict[str, int] = {}
        for src, dst in chain:
            count = _rollup_symbol_interval(db, symbol, src, dst, limit_hint=limit_hint)
            symbol_stats[f"{src}->{dst}"] = count
        stats[symbol] = symbol_stats
    return stats

def _backfill_from_second_klines(db: Session, symbol: str, interval: str, limit: int) -> int:
    if interval not in {"1m", "5m", "15m", "1h"}:
        return 0
    src_map = {"1m": "1s", "5m": "1m", "15m": "5m", "1h": "15m"}
    return _rollup_symbol_interval(db, symbol, src_map[interval], interval, limit_hint=max(limit, 100))

@router.get("/symbols")
def get_market_symbols() -> Dict[str, Any]:
    symbols = _active_symbols()
    return {"symbols": symbols, "count": len(symbols)}

@router.post("/rollup/solidify")
def solidify_market_rollups(
    symbols: Optional[str] = Query(None, description="Comma separated symbols, e.g. BTC/USDT,ETH/USDT"),
    limit_hint: int = Query(300, ge=50, le=5000),
    db: Session = Depends(get_market_db),
) -> Dict[str, Any]:
    target_symbols = [s.strip() for s in (symbols or "").split(",") if s.strip()] or _active_symbols()
    stats = _solidify_rollups(db, target_symbols, limit_hint=limit_hint)
    total_inserted = sum(v for symbol_stats in stats.values() for v in symbol_stats.values())
    return {
        "symbols": target_symbols,
        "limit_hint": limit_hint,
        "total_inserted": total_inserted,
        "stats": stats,
    }

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

@router.get("/onchain/{symbol}/wallet-events")
def get_onchain_wallet_events(
    symbol: str,
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(50, ge=1, le=500),
    min_usd: float = Query(0.0, ge=0.0),
    db: Session = Depends(get_user_db)
) -> Dict[str, Any]:
    service = OnChainDataService(db)
    events = service.get_wallet_events(symbol=symbol, hours=hours, limit=limit, min_usd=min_usd)
    return {
        "symbol": symbol,
        "window_hours": hours,
        "limit": limit,
        "min_usd": min_usd,
        "count": len(events),
        "items": events,
    }

@router.get("/onchain/{symbol}/wallet-summary")
def get_onchain_wallet_summary(
    symbol: str,
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_user_db)
) -> Dict[str, Any]:
    service = OnChainDataService(db)
    return service.get_wallet_summary(symbol=symbol, hours=hours)

@router.get("/kline")
def get_kline_data(
    symbol: str = Query(..., description="Trading pair, e.g. BTC/USDT"),
    interval: str = Query("1m", description="Timeframe: 1m, 5m, 15m, 1h, 4h, 1d"),
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
        inserted = _backfill_from_second_klines(db, symbol, interval, limit)
        if inserted > 0:
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
