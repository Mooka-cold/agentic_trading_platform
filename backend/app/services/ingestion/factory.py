from typing import Dict, Any, Type
from app.core.interfaces import DataSourceAdapter
from app.services.ingestion.connectors.ccxt_connector import CCXTConnector

class DataConnectorFactory:
    _instances: Dict[str, DataSourceAdapter] = {}

    @classmethod
    def get_connector(cls, source_type: str, exchange_id: str, config: Dict[str, Any] = None) -> DataSourceAdapter:
        """
        Create or retrieve a cached connector instance.
        
        Args:
            source_type: 'ccxt' or 'alpaca' (extensible)
            exchange_id: 'binance', 'okx', etc.
            config: Optional config dict
        """
        key = f"{source_type}_{exchange_id}"
        
        if key in cls._instances:
            return cls._instances[key]
        
        if source_type == 'ccxt':
            connector = CCXTConnector(exchange_id, config)
            cls._instances[key] = connector
            return connector
            
        # Extensible point for other sources (e.g., Alpaca)
        
        raise ValueError(f"Unknown source type: {source_type}")

    @classmethod
    def get_all_connectors(cls) -> Dict[str, DataSourceAdapter]:
        return cls._instances
