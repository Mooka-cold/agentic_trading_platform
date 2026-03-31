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
from shared.core.symbols import get_schedule_symbols_from_env, get_schedule_timeframes_from_env

# Configuration
REDIS_URL = settings.REDIS_URL
STREAM_SYMBOLS = get_schedule_symbols_from_env("MARKET_STREAM_SYMBOLS")
TIMEFRAME = os.getenv("MARKET_STREAM_TIMEFRAME", get_schedule_timeframes_from_env()[0])
HISTORY_LIMIT = 100 # Need enough for EMA/RSI calculation

logger = logging.getLogger("market_streamer")

class MarketStreamer:
    def __init__(self):
        self.redis = redis.from_url(REDIS_URL, decode_responses=True)
        self.market_db = SessionLocalMarket
        self.symbols = STREAM_SYMBOLS
        self.timeframe = TIMEFRAME
        self.df_by_symbol: dict[str, pd.DataFrame] = {}
        self.exchange_symbols = {symbol: self._to_okx_inst_id(symbol) for symbol in self.symbols}
        self.last_ts = None

    @staticmethod
    def _to_okx_inst_id(symbol: str) -> str:
        base_quote = symbol.replace("/", "-")
        return f"{base_quote}-SWAP"

    @staticmethod
    def _to_okx_bar(timeframe: str) -> str:
        if timeframe.endswith("h"):
            return f"{timeframe[:-1]}H"
        if timeframe.endswith("d"):
            return f"{timeframe[:-1]}D"
        return timeframe
        
    async def warmup(self):
        logger.info(f"🔥 Warming up with {HISTORY_LIMIT} candles from DB for {self.symbols} @ {self.timeframe}")
        try:
            for symbol in self.symbols:
                query = select(MarketKline).where(
                    MarketKline.symbol == symbol,
                    MarketKline.interval == self.timeframe
                ).order_by(desc(MarketKline.time)).limit(HISTORY_LIMIT)
                session = self.market_db()
                try:
                    klines = session.execute(query).scalars().all()
                    if not klines:
                        logger.warning(f"⚠️ No history found in DB for {symbol}. Streamer starting cold.")
                        continue
                    last_kline = klines[0]
                    now = datetime.now(timezone.utc)
                    diff = now - last_kline.time
                    if diff.total_seconds() > 120:
                        logger.warning(f"⚠️ Data gap detected for {symbol}: {diff}. Last DB time: {last_kline.time}. Backfilling...")
                        await self.backfill_gap(symbol, last_kline.time)
                        klines = session.execute(query).scalars().all()
                finally:
                    session.close()
                if not klines:
                    continue
                klines = sorted(klines, key=lambda x: x.time)
                data = [{
                    "time": k.time,
                    "open": k.open,
                    "high": k.high,
                    "low": k.low,
                    "close": k.close,
                    "volume": k.volume
                } for k in klines]
                df = pd.DataFrame(data)
                df.set_index('time', inplace=True)
                self.df_by_symbol[symbol] = df
                logger.info(f"✅ Warmup complete for {symbol}. Last candle: {df.index[-1]}")
        except Exception as e:
            logger.error(f"Warmup failed: {e}")
            
    async def backfill_gap(self, symbol: str, last_db_time: datetime):
        import ccxt.async_support as ccxt
        
        exchange = ccxt.binance()
        try:
            since = int(last_db_time.timestamp() * 1000)
            
            logger.info(f"🔄 Backfilling {symbol} from {last_db_time} via CCXT...")
            
            ohlcv = await exchange.fetch_ohlcv(symbol, self.timeframe, since=since, limit=1000)
            
            if not ohlcv:
                logger.warning("Backfill returned no data.")
                return

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
            
            for c in new_candles:
                indicators = self.calculate_indicators(symbol, c)
                await self.save_to_db(symbol, c, indicators)
                
            logger.info("✅ Backfill complete.")
            
        except Exception as e:
            logger.error(f"Backfill failed: {e}")
        finally:
            await exchange.close()
            
    def calculate_indicators(self, symbol: str, new_candle: dict) -> dict:
        ts = pd.to_datetime(int(new_candle['ts']), unit='ms', utc=True)
        
        row = pd.Series({
            "open": float(new_candle['o']),
            "high": float(new_candle['h']),
            "low": float(new_candle['l']),
            "close": float(new_candle['c']),
            "volume": float(new_candle['vol'])
        }, name=ts)

        df = self.df_by_symbol.get(symbol)
        if df is None or df.empty:
            df = pd.DataFrame([row])
            df.index = [ts]
        elif ts == df.index[-1]:
            df.iloc[-1] = row
        else:
            df = pd.concat([df, pd.DataFrame([row])])
            
        if len(df) > HISTORY_LIMIT + 10:
            df = df.iloc[-HISTORY_LIMIT:]
        self.df_by_symbol[symbol] = df

        try:
            df = df.copy()

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

    async def save_to_redis(self, symbol: str, indicators: dict):
        if not indicators: return
        
        key = f"market:{symbol}:realtime"
        
        # Add timestamp for freshness check
        indicators['updated_at'] = datetime.now().timestamp()
        
        # Convert all to string for Redis
        mapping = {k: str(v) for k, v in indicators.items() if pd.notnull(v)}
        
        async with self.redis.pipeline() as pipe:
            await pipe.hset(key, mapping=mapping)
            await pipe.expire(key, 5) # 5s TTL
            await pipe.execute()
            
        # logger.debug(f"Pushed to Redis: RSI={indicators.get('rsi_14'):.2f}")

    async def save_to_db(self, symbol: str, candle_data: dict, indicators: dict):
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
                    symbol=symbol,
                    interval=self.timeframe,
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
                logger.info(f"💾 Saved closed candle {symbol} {ts} to DB")
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"DB Save failed: {e}")

    async def run(self):
        await self.warmup()
        import httpx
        bar = self._to_okx_bar(self.timeframe)
        logger.info(f"🚀 Starting Market Streamer for {self.symbols} @ {self.timeframe}")
        
        while True:
            try:
                current_prices = {}
                async with httpx.AsyncClient() as client:
                    for symbol in self.symbols:
                        inst_id = self.exchange_symbols.get(symbol, self._to_okx_inst_id(symbol))
                        url = f"https://www.okx.com/api/v5/market/candles?instId={inst_id}&bar={bar}&limit=1"
                        try:
                            resp = await client.get(url, timeout=5)
                            data = resp.json()
                            if data.get("code") != "0" or not data.get("data"):
                                continue
                            c = data["data"][0]
                            candle_map = {
                                "ts": c[0],
                                "o": c[1],
                                "h": c[2],
                                "l": c[3],
                                "c": c[4],
                                "vol": c[5],
                                "confirm": c[8],
                            }
                            indicators = self.calculate_indicators(symbol, candle_map)
                            await self.save_to_redis(symbol, indicators)
                            await self.save_to_db(symbol, candle_map, indicators)
                            current_prices[symbol] = float(candle_map["c"])
                            if candle_map["confirm"] == "1":
                                logger.info(f"💾 Candle Closed: {symbol} {pd.to_datetime(int(candle_map['ts']), unit='ms')}")
                        except Exception as req_err:
                            logger.error(f"Request failed for {symbol}: {req_err}")
                if current_prices:
                    try:
                        from app.services.paper_trading import PaperTradingService
                        user_session = SessionLocalUser()
                        try:
                            pt_service = PaperTradingService(user_session)
                            triggered = pt_service.check_and_trigger_pending_orders(current_prices)
                            if triggered > 0:
                                logger.info(f"⚡ Simulated Match Engine: Triggered {triggered} pending orders")
                        finally:
                            user_session.close()
                    except Exception as e:
                        logger.error(f"Failed to check pending orders: {e}")
                
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.error(f"Stream error: {e}. Retry in 5s...")
                await asyncio.sleep(5)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    streamer = MarketStreamer()
    asyncio.run(streamer.run())
