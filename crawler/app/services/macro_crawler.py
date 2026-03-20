import yfinance as yf
import requests
import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session
from shared.models.macro import MacroMetric
import logging

logger = logging.getLogger(__name__)

class MacroCrawlerService:
    def __init__(self, db: Session):
        self.db = db
        self.session = requests.Session()

    def fetch_and_store_all(self):
        """
        Crawler function: Fetches data from external APIs and stores to DB.
        """
        logger.info("Starting Macro Data Update...")
        self._fetch_tradfi()
        self._fetch_crypto()
        self._fetch_sentiment()
        self.db.commit()
        logger.info("Macro Data Update Complete.")

    def _fetch_tradfi(self):
        tickers = {
            "NASDAQ": "^IXIC",
            "US_10Y_BOND": "^TNX",
            "DXY": "DX-Y.NYB",
            "GOLD": "GC=F",
            "VIX": "^VIX"
        }
        try:
            df = yf.download(list(tickers.values()), period="5d", progress=False)['Close']
            today_str = datetime.utcnow().strftime("%Y-%m-%d")
            
            for name, ticker in tickers.items():
                if ticker in df.columns:
                    val = df[ticker].iloc[-1]
                    if pd.isna(val): continue
                    
                    self._upsert_metric(
                        name=name,
                        category="TRADFI",
                        value=float(val),
                        unit="Index/USD"
                    )
        except Exception as e:
            logger.error(f"Failed to fetch TradFi data: {e}")

    def _fetch_crypto(self):
        try:
            # Stablecoins
            res = self.session.get("https://stablecoins.llama.fi/stablecoins?includePrices=true", timeout=10)
            if res.status_code == 200:
                coins = res.json().get("peggedAssets", [])
                total_mcap = 0
                for coin in coins:
                    if coin['symbol'] in ['USDT', 'USDC', 'DAI', 'FDUSD', 'USDe']:
                        total_mcap += coin.get('circulating', {}).get('peggedUSD', 0)
                
                self._upsert_metric("TOTAL_STABLECOIN_MCAP", "CRYPTO", float(total_mcap), "USD")

            # TVL
            res_tvl = self.session.get("https://api.llama.fi/v2/chains", timeout=10)
            if res_tvl.status_code == 200:
                total_tvl = sum([c.get('tvl', 0) for c in res_tvl.json()])
                self._upsert_metric("TOTAL_TVL", "CRYPTO", float(total_tvl), "USD")
                
        except Exception as e:
            logger.error(f"Failed to fetch Crypto data: {e}")

    def _fetch_sentiment(self):
        try:
            res = self.session.get("https://api.alternative.me/fng/", timeout=10)
            if res.status_code == 200:
                val = int(res.json()['data'][0]['value'])
                self._upsert_metric("FEAR_AND_GREED", "SENTIMENT", float(val), "Index")
        except Exception as e:
            logger.error(f"Failed to fetch Sentiment data: {e}")

    def _upsert_metric(self, name: str, category: str, value: float, unit: str):
        # ID strategy: metric_name (overwrite latest)
        obj = self.db.query(MacroMetric).filter(MacroMetric.id == name).first()
        if not obj:
            obj = MacroMetric(id=name, metric_name=name, category=category)
            self.db.add(obj)
        
        obj.value = value
        obj.unit = unit
        obj.timestamp = datetime.utcnow()
