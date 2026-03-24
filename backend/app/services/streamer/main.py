import asyncio
import json
import logging
import os
import pandas as pd
import redis.asyncio as redis
import websockets
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from app.db.session import SessionLocalUser, SessionLocalMarket
from shared.models.market import MarketKline
from app.core.config import settings

# Configuration
REDIS_URL = settings.REDIS_URL
SYMBOL = "BTC/USDT"
EXCHANGE_SYMBOL = "BTC-USDT-SWAP" # OKX Format
TIMEFRAME = "1m"
HISTORY_LIMIT = 100 # Need enough for EMA/RSI calculation

logger = logging.getLogger("market_streamer")

class MarketStreamer:
    def __init__(self):
        self.redis = redis.from_url(REDIS_URL, decode_responses=True)
        self.market_db = SessionLocalMarket
        self.df = pd.DataFrame()
        self.last_ts = None
        
    async def warmup(self):
        """
        Load historical klines from DB to initialize indicators
        """
        logger.info(f"🔥 Warming up with {HISTORY_LIMIT} candles from DB...")
        try:
            # Use raw SQL or ORM to fetch recent klines
            # Assuming MarketKline table stores 1m data
            query = select(MarketKline).where(
                MarketKline.symbol == SYMBOL,
                MarketKline.interval == TIMEFRAME
            ).order_by(desc(MarketKline.time)).limit(HISTORY_LIMIT)
            
            session = self.market_db()
            try:
                klines = session.execute(query).scalars().all()
                if not klines:
                    logger.warning("⚠️ No history found in DB. Streamer starting cold.")
                    return
                
                # Check for gap
                last_kline = klines[0] # desc order, so first is latest
                now = datetime.now(timezone.utc)
                diff = now - last_kline.time
                
                # If gap > 2 minutes (allow some latency), backfill
                if diff.total_seconds() > 120:
                    logger.warning(f"⚠️ Data gap detected: {diff}. Last DB time: {last_kline.time}. Backfilling...")
                    await self.backfill_gap(last_kline.time)
                    # Re-fetch after backfill
                    klines = session.execute(query).scalars().all()
                    
            finally:
                session.close()

            if not klines:
                return

            # Sort ascending for calculation
            klines = sorted(klines, key=lambda x: x.time)
            
            data = [{
                "time": k.time,
                "open": k.open,
                "high": k.high,
                "low": k.low,
                "close": k.close,
                "volume": k.volume
            } for k in klines]
            
            self.df = pd.DataFrame(data)
            self.df.set_index('time', inplace=True)
            logger.info(f"✅ Warmup complete. Last candle: {self.df.index[-1]}")
        except Exception as e:
            logger.error(f"Warmup failed: {e}")
            
    async def backfill_gap(self, last_db_time: datetime):
        """
        Use CCXT to fetch missing candles between last_db_time and NOW.
        Calculate indicators for them and save to DB.
        """
        import ccxt.async_support as ccxt
        
        exchange = ccxt.binance()
        try:
            # Calculate number of missing candles
            now = datetime.now(timezone.utc)
            # Binance limit is 1000
            # Timeframe is 1m
            since = int(last_db_time.timestamp() * 1000)
            
            logger.info(f"🔄 Backfilling from {last_db_time} via CCXT...")
            
            ohlcv = await exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, since=since, limit=1000)
            
            if not ohlcv:
                logger.warning("Backfill returned no data.")
                return

            # Filter out already existing (first one usually overlaps)
            new_candles = []
            for candle in ohlcv:
                ts = pd.to_datetime(candle[0], unit='ms', utc=True)
                if ts > last_db_time:
                    new_candles.append({
                        'ts': candle[0],
                        'o': candle[1],
                        'h': candle[2],
                        'l': candle[3],
                        'c': candle[4],
                        'vol': candle[5]
                    })
            
            if not new_candles:
                logger.info("No new candles to backfill.")
                return

            logger.info(f"📥 Found {len(new_candles)} missing candles. Processing...")
            
            # Process each candle sequentially to update DF and Indicators
            for c in new_candles:
                # Update DF and calculate indicators (this updates self.df state)
                indicators = self.calculate_indicators(c)
                # Save to DB
                await self.save_to_db(c, indicators)
                
            logger.info("✅ Backfill complete.")
            
        except Exception as e:
            logger.error(f"Backfill failed: {e}")
        finally:
            await exchange.close()
            
    def calculate_indicators(self, new_candle: dict) -> dict:
        """
        Append new candle (or update current), calc indicators, return latest values
        """
        # Convert new_candle to Series
        ts = pd.to_datetime(int(new_candle['ts']), unit='ms', utc=True)
        
        row = pd.Series({
            "open": float(new_candle['o']),
            "high": float(new_candle['h']),
            "low": float(new_candle['l']),
            "close": float(new_candle['c']),
            "volume": float(new_candle['vol'])
        }, name=ts)

        # Update DataFrame
        # If timestamp exists (update current unclosed candle), replace it
        # If new timestamp, append
        if not self.df.empty and ts == self.df.index[-1]:
            self.df.iloc[-1] = row
        else:
            self.df = pd.concat([self.df, pd.DataFrame([row])])
            
        # Keep fixed window size to prevent memory leak
        if len(self.df) > HISTORY_LIMIT + 10:
            self.df = self.df.iloc[-HISTORY_LIMIT:]

        try:
            df = self.df.copy()

            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).abs().rolling(window=14).mean()
            rs = gain / loss
            df['rsi_14'] = 100 - (100 / (1 + rs))

            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            macd = exp1 - exp2
            macd_signal = macd.ewm(span=9, adjust=False).mean()
            df['macd'] = macd
            df['macd_signal'] = macd_signal
            df['macd_hist'] = macd - macd_signal

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

            df['sma_7'] = df['close'].rolling(window=7).mean()
            df['sma_25'] = df['close'].rolling(window=25).mean()
            df['ma50'] = df['close'].rolling(window=50).mean()
            df['ema_7'] = df['close'].ewm(span=7, adjust=False).mean()
            df['ema_25'] = df['close'].ewm(span=25, adjust=False).mean()

            latest = df.iloc[-1]
            return {
                "price": float(latest['close']),
                "rsi_14": latest.get('rsi_14'),
                "macd": latest.get('macd'),
                "macd_signal": latest.get('macd_signal'),
                "macd_hist": latest.get('macd_hist'),
                "bb_upper": latest.get('bb_upper'),
                "bb_middle": latest.get('bb_middle'),
                "bb_lower": latest.get('bb_lower'),
                "atr_14": latest.get('atr_14'),
                "sma_7": latest.get('sma_7'),
                "sma_25": latest.get('sma_25'),
                "ma50": latest.get('ma50'),
                "ema_7": latest.get('ema_7'),
                "ema_25": latest.get('ema_25'),
                "ts": ts.timestamp()
            }
        except Exception as e:
            logger.error(f"Indicator calc failed: {e}")
            return {}

    async def save_to_redis(self, indicators: dict):
        if not indicators: return
        
        key = f"market:{SYMBOL}:realtime"
        
        # Add timestamp for freshness check
        indicators['updated_at'] = datetime.now().timestamp()
        
        # Convert all to string for Redis
        mapping = {k: str(v) for k, v in indicators.items() if pd.notnull(v)}
        
        async with self.redis.pipeline() as pipe:
            await pipe.hset(key, mapping=mapping)
            await pipe.expire(key, 5) # 5s TTL
            await pipe.execute()
            
        # logger.debug(f"Pushed to Redis: RSI={indicators.get('rsi_14'):.2f}")

    async def save_to_db(self, candle_data: dict, indicators: dict):
        """
        Persist CLOSED candle with indicators to DB
        """
        try:
            def _sanitize(value):
                if value is None:
                    return None
                if isinstance(value, float) and (pd.isna(value)):
                    return None
                if isinstance(value, (int, float)):
                    return float(value)
                try:
                    if pd.isna(value):
                        return None
                except Exception:
                    pass
                return float(value) if isinstance(value, (int, float)) else value

            ts = pd.to_datetime(int(candle_data['ts']), unit='ms', utc=True)
            
            session = self.market_db()
            try:
                kline = MarketKline(
                    time=ts,
                    symbol=SYMBOL,
                    interval=TIMEFRAME,
                    source="okx",
                    open=float(candle_data['o']),
                    high=float(candle_data['h']),
                    low=float(candle_data['l']),
                    close=float(candle_data['c']),
                    volume=float(candle_data['vol']),
                    rsi_14=_sanitize(indicators.get('rsi_14')),
                    macd=_sanitize(indicators.get('macd')),
                    macd_signal=_sanitize(indicators.get('macd_signal')),
                    macd_hist=_sanitize(indicators.get('macd_hist')),
                    bb_upper=_sanitize(indicators.get('bb_upper')),
                    bb_middle=_sanitize(indicators.get('bb_middle')),
                    bb_lower=_sanitize(indicators.get('bb_lower')),
                    atr_14=_sanitize(indicators.get('atr_14')),
                    sma_7=_sanitize(indicators.get('sma_7')),
                    sma_25=_sanitize(indicators.get('sma_25')),
                    ma50=_sanitize(indicators.get('ma50')),
                    ema_7=_sanitize(indicators.get('ema_7')),
                    ema_25=_sanitize(indicators.get('ema_25'))
                )
                session.merge(kline)
                session.commit()
                logger.info(f"💾 Saved closed candle {ts} to DB")
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"DB Save failed: {e}")

    async def run(self):
        await self.warmup()
        
        # Fallback: Use REST API polling if WebSocket fails
        # OKX REST Endpoint
        import httpx
        
        logger.info(f"� Starting Market Streamer for {EXCHANGE_SYMBOL}...")
        
        while True:
            try:
                # Polling Interval (3s)
                async with httpx.AsyncClient() as client:
                    # Get latest candle (limit=1)
                    # OKX API: GET /api/v5/market/candles
                    url = f"https://www.okx.com/api/v5/market/candles?instId={EXCHANGE_SYMBOL}&bar=1m&limit=1"
                    
                    try:
                        resp = await client.get(url, timeout=5)
                        data = resp.json()
                        
                        if data.get("code") == "0" and data.get("data"):
                            c = data['data'][0]
                            # [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
                            
                            candle_map = {
                                'ts': c[0], 
                                'o': c[1], 
                                'h': c[2], 
                                'l': c[3], 
                                'c': c[4], 
                                'vol': c[5],
                                'confirm': c[8] 
                            }
                            
                            # 1. Calculate
                            indicators = self.calculate_indicators(candle_map)
                            
                            # 2. Redis
                            await self.save_to_redis(indicators)
                            
                            # 3. DB (Upsert latest)
                            await self.save_to_db(candle_map, indicators)
                            
                            # 4. Check Pending Orders (Simulated Matching Engine)
                            try:
                                from app.services.paper_trading import PaperTradingService
                                user_session = SessionLocalUser()
                                try:
                                    pt_service = PaperTradingService(user_session)
                                    current_prices = {SYMBOL: float(candle_map['c'])}
                                    triggered = pt_service.check_and_trigger_pending_orders(current_prices)
                                    if triggered > 0:
                                        logger.info(f"⚡ Simulated Match Engine: Triggered {triggered} pending orders at price {candle_map['c']}")
                                finally:
                                    user_session.close()
                            except Exception as e:
                                logger.error(f"Failed to check pending orders: {e}")
                            
                            if candle_map['confirm'] == "1":
                                logger.info(f"💾 Candle Closed: {pd.to_datetime(int(candle_map['ts']), unit='ms')}")
                            else:
                                # logger.debug(f"Tick: {candle_map['c']}")
                                pass
                                
                    except Exception as req_err:
                        logger.error(f"Request failed: {req_err}")
                
                await asyncio.sleep(3) # Poll every 3 seconds
                
            except Exception as e:
                logger.error(f"Stream error: {e}. Retry in 5s...")
                await asyncio.sleep(5)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    streamer = MarketStreamer()
    asyncio.run(streamer.run())
