from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, AsyncGenerator, List

@dataclass
class MarketTick:
    symbol: str
    price: float
    volume: float
    timestamp: datetime
    source: str
    raw_data: Dict[str, Any] = None

@dataclass
class NewsItem:
    title: str
    summary: str
    url: str
    source: str
    timestamp: datetime
    sentiment_score: float = 0.0
    tags: List[str] = None

class DataSourceAdapter(ABC):
    """Abstract interface for all market data connectors"""
    
    @abstractmethod
    async def connect(self):
        """Establish connection to the data source"""
        pass

    @abstractmethod
    async def subscribe(self, symbols: List[str]):
        """Subscribe to specific symbols"""
        pass

    @abstractmethod
    async def listen(self) -> AsyncGenerator[MarketTick, None]:
        """Yields MarketTick objects in real-time"""
        pass

    @abstractmethod
    async def disconnect(self):
        """Clean up resources"""
        pass

class NewsSourceAdapter(ABC):
    """Abstract interface for news data sources"""
    
    @abstractmethod
    async def connect(self):
        """Initialize connection or API client"""
        pass

    @abstractmethod
    async def fetch_latest(self, limit: int = 10) -> AsyncGenerator[NewsItem, None]:
        """Fetch latest news items"""
        pass
    
    @abstractmethod
    async def listen(self) -> AsyncGenerator[NewsItem, None]:
        """Stream new news items in real-time (if supported)"""
        pass
