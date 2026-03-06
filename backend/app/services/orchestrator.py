import asyncio
import json
import logging
from typing import List, Dict, Any

from app.core.interfaces import MarketTick, NewsItem
from app.services.ingestion.factory import DataConnectorFactory
from app.services.calculation.engine import IndicatorEngine
from app.services.news.sources.cryptopanic import CryptoPanicFetcher
from app.services.redis_stream import redis_stream
from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

class MarketOrchestrator:
    def __init__(self):
        self.indicator_engine = IndicatorEngine()
        self.news_fetcher = CryptoPanicFetcher(api_key=settings.CRYPTOPANIC_API_KEY)
        
        # Initialize connectors
        self.market_connector = DataConnectorFactory.get_connector(
            source_type='ccxt', 
            exchange_id='binance'
        )
        
        # In-memory buffer for AI context
        self.news_buffer: List[NewsItem] = []
        self.latest_market_snapshot: Dict[str, Any] = {}

    async def start(self):
        logger.info("Starting Market Orchestrator...")
        
        # 1. Connect to sources
        await self.market_connector.connect()
        await self.news_fetcher.connect()
        
        # 2. Register indicators (Example for BTC/USDT)
        # Note: In production, these should be loaded from config/DB
        from talipp.indicators import SMA, RSI, MACD, BB
        
        symbol = "BTC/USDT"
        self.indicator_engine.register_indicator(symbol, "sma_20", SMA, period=20)
        self.indicator_engine.register_indicator(symbol, "rsi_14", RSI, period=14)
        self.indicator_engine.register_indicator(symbol, "macd", MACD, fast_period=12, slow_period=26, signal_period=9)
        self.indicator_engine.register_indicator(symbol, "bb_20", BB, period=20, std_dev_multiplier=2)
        
        # 3. Start loops
        await asyncio.gather(
            self._market_loop([symbol]),
            self._news_loop(),
            self._ai_decision_loop()
        )

    async def _market_loop(self, symbols: List[str]):
        await self.market_connector.subscribe(symbols)
        async for tick in self.market_connector.listen():
            # 1. Update indicators
            signals = self.indicator_engine.on_tick(tick.symbol, tick.price)
            
            # 2. Update snapshot
            self.latest_market_snapshot[tick.symbol] = {
                "price": tick.price,
                "volume": tick.volume,
                "indicators": self.indicator_engine.get_snapshot(tick.symbol),
                "signals": signals
            }
            
            # Log significant signals
            if signals:
                logger.info(f"SIGNALS DETECTED [{tick.symbol}]: {signals}")
                
                # Publish to Redis for AI Engine
                await redis_stream.publish_message("market_signals", {
                    "symbol": tick.symbol,
                    "signals": signals,
                    "price": tick.price,
                    "timestamp": tick.timestamp.isoformat()
                })

    async def _news_loop(self):
        async for news_item in self.news_fetcher.listen():
            logger.info(f"NEWS: {news_item.title}")
            self.news_buffer.append(news_item)
            # Keep buffer size manageable
            if len(self.news_buffer) > 20:
                self.news_buffer.pop(0)

    async def _ai_decision_loop(self):
        """
        Periodically trigger AI analysis
        """
        import aiohttp
        
        while True:
            await asyncio.sleep(60) # Analyze every minute (or 5m/1h)
            
            symbol = "BTC/USDT"
            snapshot = self.latest_market_snapshot.get(symbol)
            
            if not snapshot:
                continue
                
            # Prepare payload for AI Engine
            payload = {
                "symbol": symbol,
                "market_context": json.dumps(snapshot, default=str),
                "news_context": json.dumps([n.__dict__ for n in self.news_buffer[-5:]], default=str)
            }
            
            try:
                # Call AI Engine Microservice
                async with aiohttp.ClientSession() as session:
                    async with session.post(f"{settings.AI_ENGINE_URL}/analyze", json=payload) as resp:
                        if resp.status == 200:
                            decision = await resp.json()
                            logger.info(f"AI DECISION [{symbol}]: {decision}")
                            # TODO: Execute trade based on decision
                        else:
                            logger.error(f"AI Engine Error: {resp.status}")
            except Exception as e:
                logger.error(f"Failed to call AI Engine: {e}")

