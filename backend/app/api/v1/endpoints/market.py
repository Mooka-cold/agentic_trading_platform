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

def _compute_indicators_for_rows(rows_asc: List[Any]) -> pd.DataFrame:
    """
    Compute indicators on the fly from OHLCV rows (chronological order).
    Used as a fallback when DB-stored indicator columns are NULL.
    """
    if not rows_asc:
        return pd.DataFrame()

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
            for row in rows_asc
        ]
    )

    if df.empty:
        return df

    close = df["close"]
    high = df["high"]
    low = df["low"]

    # RSI(14)
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0.0, pd.NA)
    df["rsi"] = 100.0 - (100.0 / (1.0 + rs))

    # MACD(12,26,9)
    ema12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
    ema26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False, min_periods=9).mean()
    df["macd"] = macd
    df["macd_signal"] = signal
    df["macd_hist"] = macd - signal

    # SMA / EMA
    df["ma20"] = close.rolling(window=20, min_periods=20).mean()
    df["ma50"] = close.rolling(window=50, min_periods=50).mean()
    df["sma_7"] = close.rolling(window=7, min_periods=7).mean()
    df["sma_25"] = close.rolling(window=25, min_periods=25).mean()
    df["ema_7"] = close.ewm(span=7, adjust=False, min_periods=7).mean()
    df["ema_25"] = close.ewm(span=25, adjust=False, min_periods=25).mean()

    # Bollinger Bands(20,2)
    std20 = close.rolling(window=20, min_periods=20).std(ddof=0)
    df["bb_middle"] = df["ma20"]
    df["bb_upper"] = df["bb_middle"] + 2 * std20
    df["bb_lower"] = df["bb_middle"] - 2 * std20

    # ATR(14)
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["atr_14"] = tr.rolling(window=14, min_periods=14).mean()

    return df

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

    rows_asc = list(reversed(result))
    computed_df = _compute_indicators_for_rows(rows_asc)
    computed_by_ts = {
        int(pd.Timestamp(t).timestamp()): row
        for t, row in zip(computed_df["time"], computed_df.to_dict(orient="records"))
    } if not computed_df.empty else {}

    data = []

    # Helper to safely get float or None
    def safe_val(val):
        if val is None or pd.isna(val):
            return None
        return float(val)

    indicator_update_payload: List[Dict[str, Any]] = []

    # Return chronological order (oldest first) as chart libraries usually expect
    for row in rows_asc:
        ts = int(row.time.timestamp())
        calc = computed_by_ts.get(ts, {})
        rsi_val = safe_val(row.rsi) if row.rsi is not None else safe_val(calc.get("rsi"))
        macd_val = safe_val(row.macd) if row.macd is not None else safe_val(calc.get("macd"))
        macd_signal_val = safe_val(row.macd_signal) if row.macd_signal is not None else safe_val(calc.get("macd_signal"))
        macd_hist_val = safe_val(row.macd_hist) if row.macd_hist is not None else safe_val(calc.get("macd_hist"))
        ma20_val = safe_val(row.bb_middle) if row.bb_middle is not None else safe_val(calc.get("ma20"))
        ma50_val = safe_val(calc.get("ma50"))
        sma7_val = safe_val(row.sma_7) if row.sma_7 is not None else safe_val(calc.get("sma_7"))
        sma25_val = safe_val(row.sma_25) if row.sma_25 is not None else safe_val(calc.get("sma_25"))
        ema7_val = safe_val(row.ema_7) if row.ema_7 is not None else safe_val(calc.get("ema_7"))
        ema25_val = safe_val(row.ema_25) if row.ema_25 is not None else safe_val(calc.get("ema_25"))
        bb_upper_val = safe_val(row.bb_upper) if row.bb_upper is not None else safe_val(calc.get("bb_upper"))
        bb_middle_val = safe_val(row.bb_middle) if row.bb_middle is not None else safe_val(calc.get("bb_middle"))
        bb_lower_val = safe_val(row.bb_lower) if row.bb_lower is not None else safe_val(calc.get("bb_lower"))
        atr14_val = safe_val(row.atr_14) if row.atr_14 is not None else safe_val(calc.get("atr_14"))

        # Persist computed indicators back to DB when source row has NULLs.
        if (
            (row.rsi is None and rsi_val is not None)
            or (row.macd is None and macd_val is not None)
            or (row.macd_signal is None and macd_signal_val is not None)
            or (row.macd_hist is None and macd_hist_val is not None)
            or (row.sma_7 is None and sma7_val is not None)
            or (row.sma_25 is None and sma25_val is not None)
            or (row.ema_7 is None and ema7_val is not None)
            or (row.ema_25 is None and ema25_val is not None)
            or (row.bb_upper is None and bb_upper_val is not None)
            or (row.bb_middle is None and bb_middle_val is not None)
            or (row.bb_lower is None and bb_lower_val is not None)
            or (row.atr_14 is None and atr14_val is not None)
        ):
            indicator_update_payload.append(
                {
                    "time": row.time,
                    "symbol": symbol,
                    "interval": interval,
                    "rsi_14": rsi_val,
                    "macd": macd_val,
                    "macd_signal": macd_signal_val,
                    "macd_hist": macd_hist_val,
                    "sma_7": sma7_val,
                    "sma_25": sma25_val,
                    "ema_7": ema7_val,
                    "ema_25": ema25_val,
                    "bb_upper": bb_upper_val,
                    "bb_middle": bb_middle_val,
                    "bb_lower": bb_lower_val,
                    "atr_14": atr14_val,
                }
            )

        item = {
            "time": ts,
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(row.volume),
            
            # Indicators
            "rsi": rsi_val,
            "macd": macd_val,
            "macd_signal": macd_signal_val,
            "macd_hist": macd_hist_val,
            
            # MA20/MA50 are not explicitly in DB (streamer calcs BB_Middle which is SMA20)
            "ma20": ma20_val, # BB Middle is SMA20; fallback to computed MA20
            "ma50": ma50_val,
            
            "sma_7": sma7_val,
            "sma_25": sma25_val,
            "ema_7": ema7_val,
            "ema_25": ema25_val,
            
            "bb_upper": bb_upper_val,
            "bb_middle": bb_middle_val,
            "bb_lower": bb_lower_val,
            "atr_14": atr14_val,
            
            # Calc times - since we fetch from DB, the calc time is the candle time
            # IF the value exists.
            "rsi_calc_time": ts if rsi_val is not None else None,
            "macd_calc_time": ts if macd_val is not None else None,
            "macd_signal_calc_time": ts if macd_signal_val is not None else None,
            "macd_hist_calc_time": ts if macd_hist_val is not None else None,
            "ma20_calc_time": ts if ma20_val is not None else None,
            "ma50_calc_time": ts if ma50_val is not None else None,
            "sma_7_calc_time": ts if sma7_val is not None else None,
            "sma_25_calc_time": ts if sma25_val is not None else None,
            "ema_7_calc_time": ts if ema7_val is not None else None,
            "ema_25_calc_time": ts if ema25_val is not None else None,
            "bb_upper_calc_time": ts if bb_upper_val is not None else None,
            "bb_middle_calc_time": ts if bb_middle_val is not None else None,
            "bb_lower_calc_time": ts if bb_lower_val is not None else None,
            "atr_14_calc_time": ts if atr14_val is not None else None
        }
        data.append(item)

    if indicator_update_payload:
        db.execute(
            text(
                """
                UPDATE market_klines
                SET
                    rsi_14 = COALESCE(rsi_14, :rsi_14),
                    macd = COALESCE(macd, :macd),
                    macd_signal = COALESCE(macd_signal, :macd_signal),
                    macd_hist = COALESCE(macd_hist, :macd_hist),
                    sma_7 = COALESCE(sma_7, :sma_7),
                    sma_25 = COALESCE(sma_25, :sma_25),
                    ema_7 = COALESCE(ema_7, :ema_7),
                    ema_25 = COALESCE(ema_25, :ema_25),
                    bb_upper = COALESCE(bb_upper, :bb_upper),
                    bb_middle = COALESCE(bb_middle, :bb_middle),
                    bb_lower = COALESCE(bb_lower, :bb_lower),
                    atr_14 = COALESCE(atr_14, :atr_14)
                WHERE symbol = :symbol AND interval = :interval AND time = :time
                """
            ),
            indicator_update_payload,
        )
        db.commit()

    return data
