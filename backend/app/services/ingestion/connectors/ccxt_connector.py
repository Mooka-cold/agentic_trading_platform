import asyncio
import ccxt.pro as ccxt
from datetime import datetime
from typing import AsyncGenerator, List, Dict
from app.core.interfaces import DataSourceAdapter, MarketTick

class CCXTConnector(DataSourceAdapter):
    def __init__(self, exchange_id: str, config: Dict = None):
        self.exchange_id = exchange_id
        self.config = config or {'enableRateLimit': True}
        
        if not hasattr(ccxt, exchange_id):
            raise ValueError(f"Exchange {exchange_id} not supported by CCXT Pro")
            
        exchange_class = getattr(ccxt, exchange_id)
        self.exchange = exchange_class(self.config)
        self.subscribed_symbols = []

    async def connect(self):
        # CCXT Pro connects lazily on watch_*, but we can verify here
        if self.exchange.has['watchTicker']:
            print(f"Connected to {self.exchange_id} (WebSocket enabled)")
        else:
            raise NotImplementedError(f"{self.exchange_id} does not support WebSocket tickers")

    async def subscribe(self, symbols: List[str]):
        self.subscribed_symbols.extend(symbols)
        print(f"Subscribed to {symbols} on {self.exchange_id}")

    async def listen(self) -> AsyncGenerator[MarketTick, None]:
        # Simple implementation using watch_tickers loop
        # In production, this should handle reconnections and errors robustly
        try:
            while True:
                # Watch multiple tickers at once if supported
                tickers = await self.exchange.watch_tickers(self.subscribed_symbols)
                
                for symbol, ticker in tickers.items():
                    yield MarketTick(
                        symbol=symbol,
                        price=ticker['last'],
                        volume=ticker['baseVolume'],
                        timestamp=datetime.fromtimestamp(ticker['timestamp'] / 1000),
                        source=self.exchange_id,
                        raw_data=ticker
                    )
        except Exception as e:
            print(f"Error in CCXT listener: {e}")
            # Re-raise or handle reconnect logic here
            raise e

    async def disconnect(self):
        await self.exchange.close()
