
import asyncio
import ccxt.pro as ccxt
import logging
import time
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple
from app.services.redis_stream import redis_stream

logger = logging.getLogger("price_streamer")

class PriceStreamer:
    """
    Dedicated WebSocket Service for Real-Time Price & Depth.
    Maintains a single long-lived connection to the exchange.
    Syncs data to Redis for persistence and sharing.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PriceStreamer, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized: return
        
        self.exchange = None
        self.tickers: Dict[str, float] = {}
        self.order_books: Dict[str, dict] = {}
        self.second_series: Dict[str, Deque[dict]] = {}
        self.max_seconds_window = 600
        self.subscribed_symbols = set()
        self.is_running = False
        self.task = None
        self.initialized = True

    async def start(self, symbols: list):
        if self.is_running:
            # Just update subscriptions if already running
            await self.subscribe(symbols)
            return

        self.is_running = True
        self.subscribed_symbols.update(symbols)
        
        # Initialize Exchange
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        
        logger.info(f"🚀 PriceStreamer Started. Watching: {self.subscribed_symbols}")
        self.task = asyncio.create_task(self._loop())

    async def stop(self):
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        if self.exchange:
            await self.exchange.close()
            logger.info("🔌 PriceStreamer Disconnected.")

    async def subscribe(self, symbols: list):
        new_symbols = [s for s in symbols if s not in self.subscribed_symbols]
        if new_symbols:
            self.subscribed_symbols.update(new_symbols)
            logger.info(f"➕ PriceStreamer subscribed to new symbols: {new_symbols}")
            # The loop will pick up new symbols automatically in next iteration or restart?
            # CCXT watch_ticker needs explicit list. 
            # We might need to restart the loop or have the loop check subscribed_symbols dynamically.
            # But watch_tickers is blocking.
            # Best way: Cancel current loop and restart it with new symbols? 
            # Or use individual tasks per symbol (more robust but resource heavy).
            # For simplicity: We restart the loop logic.
            if self.task:
                self.task.cancel()
                self.task = asyncio.create_task(self._loop())

    async def _loop(self):
        retry_count = 0
        while self.is_running:
            try:
                if not self.subscribed_symbols:
                    await asyncio.sleep(1)
                    continue

                symbols_list = list(self.subscribed_symbols)
                
                # We need two concurrent tasks: Ticker and OrderBook
                await asyncio.gather(
                    self._watch_tickers(symbols_list),
                    self._watch_order_books(symbols_list)
                )
                
                retry_count = 0 # Reset on success

            except Exception as e:
                logger.error(f"❌ PriceStreamer Error: {e}")
                retry_count += 1
                wait_time = min(retry_count * 2, 60) # Exponential backoff
                logger.info(f"🔄 Reconnecting in {wait_time}s...")
                await asyncio.sleep(wait_time)
                
                # Re-initialize exchange instance on error (sometimes needed for stale connections)
                try:
                    await self.exchange.close()
                except:
                    pass
                self.exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})

    async def _watch_tickers(self, symbols):
        """Loop for Tickers"""
        try:
            while self.is_running:
                # watch_tickers might not be supported by all exchanges in one call, but Binance supports it.
                # If symbols list changes, this call needs to be refreshed. 
                # CCXT pro is stateful.
                tickers = await self.exchange.watch_tickers(symbols)
                
                for symbol, data in tickers.items():
                    last_price = data.get('last')
                    if last_price is None:
                        continue
                    self.tickers[symbol] = float(last_price)
                    ts = data.get("timestamp")
                    sec = int(ts / 1000) if ts else int(time.time())
                    bid = data.get("bid")
                    ask = data.get("ask")
                    point = {
                        "time": sec,
                        "price": float(last_price),
                        "bid": float(bid) if bid is not None else None,
                        "ask": float(ask) if ask is not None else None,
                    }
                    series = self.second_series.get(symbol)
                    if series is None:
                        series = deque(maxlen=self.max_seconds_window)
                        self.second_series[symbol] = series
                    if series and series[-1]["time"] == sec:
                        series[-1] = point
                    else:
                        series.append(point)
                    await redis_stream.set_cache(
                        f"market:ticker:{symbol}", 
                        data, 
                        ttl=60
                    )
                    # logger.debug(f"Tick: {symbol} @ {data['last']}")
        except Exception as e:
            logger.error(f"Ticker Watch Error: {e}")
            raise e

    async def _watch_order_books(self, symbols):
        """Loop for OrderBooks"""
        # For multiple symbols, we might need multiple tasks or a loop over watch_order_book(symbol)
        # watch_order_book usually takes one symbol.
        # So we create a task for each symbol.
        tasks = [self._watch_single_order_book(s) for s in symbols]
        await asyncio.gather(*tasks)

    async def _watch_single_order_book(self, symbol):
        try:
            while self.is_running:
                # limit=20 for speed
                order_book = await self.exchange.watch_order_book(symbol, limit=20)
                self.order_books[symbol] = order_book
                
                # Sync to Redis (TTL 30s)
                await redis_stream.set_cache(
                    f"market:orderbook:{symbol}", 
                    order_book, 
                    ttl=30
                )
        except Exception as e:
            logger.error(f"OrderBook Watch Error ({symbol}): {e}")
            # Don't raise here to keep other symbols alive? 
            # But if we don't raise, outer loop won't reconnect.
            # Let's log and retry locally or raise.
            raise e

    def get_latest(self, symbol: str) -> Tuple[Optional[float], Optional[dict]]:
        """
        Non-blocking retrieval of latest data.
        Returns: (price, order_book)
        """
        price = self.tickers.get(symbol)
        depth = self.order_books.get(symbol)
        return price, depth

    def get_recent_seconds(self, symbol: str, window: int = 600) -> List[dict]:
        series = self.second_series.get(symbol)
        if not series:
            return []
        size = max(1, min(window, self.max_seconds_window))
        return list(series)[-size:]

# Global Instance
price_streamer = PriceStreamer()
