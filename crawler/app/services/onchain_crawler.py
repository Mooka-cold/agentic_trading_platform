import requests
from datetime import datetime
from sqlalchemy.orm import Session
from shared.models.onchain import OnChainMetric
import logging

logger = logging.getLogger(__name__)

class OnChainCrawlerService:
    def __init__(self, db: Session):
        self.db = db
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
        }

    def fetch_and_store_all(self):
        logger.info("Starting On-Chain Data Update...")
        self._fetch_oi("BTC")
        self._fetch_ls_ratio("BTC")
        self.db.commit()
        logger.info("On-Chain Update Complete.")

    def _fetch_oi(self, symbol):
        try:
            oi_url = f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}USDT"
            mark_url = f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}USDT"
            oi_res = requests.get(oi_url, headers=self.headers, timeout=5)
            mark_res = requests.get(mark_url, headers=self.headers, timeout=5)
            if oi_res.status_code == 200 and mark_res.status_code == 200:
                oi_payload = oi_res.json()
                mark_payload = mark_res.json()
                oi_contracts = float(oi_payload.get("openInterest", 0.0) or 0.0)
                mark_price = float(mark_payload.get("markPrice", 0.0) or 0.0)
                if oi_contracts > 0 and mark_price > 0:
                    latest_oi_usd = oi_contracts * mark_price
                    self._upsert_metric(f"{symbol}_OI", symbol, "OI", latest_oi_usd, "USD")
                    return
            logger.warning(f"Binance OI API failed for {symbol}: oi={oi_res.status_code}, mark={mark_res.status_code}")
        except Exception as e:
            logger.error(f"Failed to fetch OI for {symbol}: {e}")

    def _fetch_ls_ratio(self, symbol):
        try:
            url = f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}USDT&period=5m&limit=1"
            res = requests.get(url, headers=self.headers, timeout=5)
            if res.status_code == 200:
                data_list = res.json()
                if isinstance(data_list, list) and data_list:
                    latest = data_list[-1]
                    ls_ratio = float(latest.get("longShortRatio", 0.0) or 0.0)
                    if ls_ratio > 0:
                        self._upsert_metric(f"{symbol}_LS_RATIO", symbol, "LS_RATIO", ls_ratio, "Ratio")
                        return
            logger.warning(f"Binance LS Ratio API failed for {symbol}: status={res.status_code}")
        except Exception as e:
            logger.error(f"Failed to fetch LS Ratio for {symbol}: {e}")

    def _upsert_metric(self, uid, symbol, name, value, unit):
        obj = self.db.query(OnChainMetric).filter(OnChainMetric.id == uid).first()
        if not obj:
            obj = OnChainMetric(id=uid, symbol=symbol, metric_name=name)
            self.db.add(obj)
        
        obj.value = value
        obj.unit = unit
        obj.timestamp = datetime.utcnow()
