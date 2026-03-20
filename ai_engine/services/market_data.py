from sqlalchemy import create_engine, text
import pandas as pd
from core.config import settings

class MarketDataService:
    def __init__(self):
        self.engine = create_engine(settings.DATABASE_MARKET_URL)

    def _fetch_ohlcv(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        query = text("""
            SELECT time, open, high, low, close, volume 
            FROM market_klines 
            WHERE symbol = :symbol AND interval = :interval
            ORDER BY time DESC
            LIMIT :limit
        """)
        try:
            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn, params={"symbol": symbol, "interval": interval, "limit": limit})
            if not df.empty:
                df = df.sort_values("time")
            return df
        except Exception:
            return pd.DataFrame()

    def get_current_price(self, symbol: str) -> float:
        """Fetch the latest close price for a symbol."""
        # Fetch 1 minute candle, limit 1
        df = self._fetch_ohlcv(symbol, "1m", 1)
        if df.empty:
            return 0.0
        return float(df.iloc[-1]['close'])

    def get_full_snapshot(self, symbol: str) -> dict:
        """
        Fetch a comprehensive snapshot of market data including:
        - Latest Price & Volume
        - Technical Indicators (RSI, MACD, etc. on 1m/5m)
        """
        import logging
        logger = logging.getLogger("ai_engine.market_data")
        
        # 1. Try to get latest pre-calculated indicators from DB (limit=1)
        query = text("""
            SELECT 
                time, close, volume,
                rsi_14, macd, macd_signal, macd_hist,
                bb_upper, bb_middle, bb_lower,
                atr_14, sma_7, sma_25, ma50, ema_7, ema_25
            FROM market_klines 
            WHERE symbol = :symbol AND interval = '1m'
            ORDER BY time DESC
            LIMIT 1
        """)
        
        try:
            with self.engine.connect() as conn:
                row = conn.execute(query, {"symbol": symbol}).fetchone()
                
            if row:
                last_ts = row.time.timestamp()
                now_ts = pd.Timestamp.now().timestamp()
                
                if now_ts - last_ts < 120:
                    logger.info(f"✅ [MarketData] Using DB indicators for {symbol} (Freshness: {now_ts - last_ts:.1f}s)")
                    return {
                        "price": float(row.close),
                        "volume": float(row.volume),
                        "indicators": {
                            "rsi": float(row.rsi_14) if row.rsi_14 is not None else 0.0,
                            "macd": {
                                "value": float(row.macd) if row.macd is not None else 0.0,
                                "signal": float(row.macd_signal) if row.macd_signal is not None else 0.0,
                                "hist": float(row.macd_hist) if row.macd_hist is not None else 0.0
                            },
                            "bb": {
                                "upper": float(row.bb_upper) if row.bb_upper is not None else 0.0,
                                "middle": float(row.bb_middle) if row.bb_middle is not None else 0.0,
                                "lower": float(row.bb_lower) if row.bb_lower is not None else 0.0
                            },
                            "ema": {
                                "fast": float(row.ema_7) if row.ema_7 is not None else 0.0,
                                "slow": float(row.ema_25) if row.ema_25 is not None else 0.0
                            },
                            "sma": {
                                "fast": float(row.sma_7) if row.sma_7 is not None else 0.0,
                                "medium": float(row.sma_25) if row.sma_25 is not None else 0.0,
                                "slow": float(row.ma50) if row.ma50 is not None else 0.0
                            },
                            "atr": float(row.atr_14) if row.atr_14 is not None else 0.0
                        },
                        "source": "database",
                        "timestamp": last_ts
                    }
                else:
                    logger.warning(f"⚠️ [MarketData] DB data stale for {symbol} ({now_ts - last_ts:.1f}s old). Triggering on-the-fly recalc.")
        except Exception as e:
            logger.error(f"⚠️ [MarketData] DB snapshot fetch failed: {e}")

        # 2. Fallback: On-the-fly calculation with 100 candles
        logger.info(f"🔄 [MarketData] Performing on-the-fly calculation for {symbol} (using last 100 candles)")
        limit = 100
        df = self._fetch_ohlcv(symbol, "1m", limit)
        
        if df.empty:
            return {
                "price": 0.0,
                "volume": 0.0,
                "indicators": {},
                "source": "empty",
                "timestamp": 0
            }
            
        # Calculate Indicators on 1m timeframe
        df['RSI'] = self.calculate_rsi(df['close'])
        macd, sig, hist = self.calculate_macd(df['close'])
        
        # Simple EMAs/SMAs for fallback
        df['EMA_7'] = df['close'].ewm(span=7, adjust=False).mean()
        df['EMA_25'] = df['close'].ewm(span=25, adjust=False).mean()
        
        last = df.iloc[-1]
        
        return {
            "price": float(last['close']),
            "volume": float(last['volume']),
            "indicators": {
                "rsi": float(last['RSI']) if not pd.isna(last['RSI']) else 0.0,
                "macd": {
                    "value": float(macd.iloc[-1]) if not pd.isna(macd.iloc[-1]) else 0.0,
                    "signal": float(sig.iloc[-1]) if not pd.isna(sig.iloc[-1]) else 0.0,
                    "hist": float(hist.iloc[-1]) if not pd.isna(hist.iloc[-1]) else 0.0
                },
                "ema": {
                    "fast": float(last['EMA_7']),
                    "slow": float(last['EMA_25'])
                },
                # Fallback ATR using percent of price
                "atr": float(last['close']) * 0.02 
            },
            "source": "calculated",
            "timestamp": last.name.timestamp() if hasattr(last.name, 'timestamp') else 0
        }

    def get_market_context(self, symbol: str, interval: str = "1m", limit: int = 50) -> str:
        """Legacy method: Fetch single timeframe context"""
        df = self._fetch_ohlcv(symbol, interval, limit)
        if df.empty:
            return "No market data available."
            
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        df['RSI'] = self.calculate_rsi(df['close'])
        
        return df.tail(10).to_string()

    def get_multi_timeframe_context(self, symbol: str) -> dict:
        """
        Fetch market data for multiple timeframes:
        - 1h: Trend Direction (Long-term)
        - 15m: Intermediate Structure (Support/Resistance)
        - 5m: Entry Signals (Momentum)
        """
        # Note: Ensure DB has these timeframes. If crawler only has 1m, we might need to resample 1m data.
        # For now, assuming crawler provides these or we request 1m and resample in pandas.
        # Given current setup, let's assume we have 1m data and we resample it if needed, 
        # or just use 1m, 5m, 15m if available.
        # TimescaleDB usually stores raw data. 
        # To be safe and robust, let's fetch 1m data and resample it here, 
        # because our crawler likely only pulls 1m or 5m raw klines.
        # Actually, standard crypto crawlers (CCXT) often pull specific timeframes.
        # My crawler implementation (which I haven't fully reviewed) probably pulls what's configured.
        # Let's assume for now we only have 1m data in DB (most granular).
        # We will resample 1m data to 5m, 15m, 1h.
        
        # Fetch enough 1m data for 1h indicators (e.g. 50 SMA on 1h = 50 hours = 3000 minutes)
        # That's a lot of data to pull.
        # Optimization: TimescaleDB has `time_bucket` for aggregation!
        # But `_fetch_ohlcv` uses raw query.
        # For MVP, let's stick to 1m, 5m (if available), or just use 1m and maybe a longer lookback on 1m to simulate trend.
        
        # Let's try to query distinct intervals if they exist. 
        # If not, I'll implement a fallback or just use 1m with longer smoothing.
        
        # Strategy: Fetch 1m data (limit 5000 to cover 1h SMA50)
        raw_df = self._fetch_ohlcv(symbol, "1m", 5000)
        
        if raw_df.empty:
            return {"error": "No data"}
            
        context = {}
        raw_df['time'] = pd.to_datetime(raw_df['time'])
        raw_df.set_index('time', inplace=True)
        
        resample_rules = {
            "5min": "5m (Entry)",
            "15min": "15m (Structure)", 
            "1h": "1h (Trend)"
        }
        
        for rule, label in resample_rules.items():
            # Resample OHLCV
            try:
                # Use 'ME' 'h' 'min' aliases for newer pandas, but '1h' '5min' usually works
                # Check raw_df index type
                if not isinstance(raw_df.index, pd.DatetimeIndex):
                    raw_df.index = pd.to_datetime(raw_df.index)
                
                df_resampled = raw_df.resample(rule).agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                }).dropna()
            except Exception as e:
                context[label] = f"Resample error: {e}"
                continue
            
            if len(df_resampled) < 20:
                context[label] = "Insufficient data (Need >20 candles)"
                continue
                
            # Calculate Indicators
            # Use minimal windows if data is short
            sma_fast_window = 20
            sma_slow_window = 50
            
            if len(df_resampled) < sma_slow_window:
                # Fallback for short history
                sma_slow_window = len(df_resampled) // 2
            
            df_resampled['SMA_20'] = df_resampled['close'].rolling(window=sma_fast_window).mean()
            df_resampled['SMA_50'] = df_resampled['close'].rolling(window=sma_slow_window).mean()
            df_resampled['EMA_20'] = df_resampled['close'].ewm(span=20, adjust=False).mean()
            
            # RSI
            try:
                rsi_series = self.calculate_rsi(df_resampled['close'])
                if rsi_series is not None and not rsi_series.empty:
                    df_resampled['RSI'] = rsi_series
                else:
                     df_resampled['RSI'] = 50.0
            except:
                df_resampled['RSI'] = 50.0

            # MACD
            try:
                m, s, h = self.calculate_macd(df_resampled['close'])
                df_resampled['MACD'], df_resampled['Signal'], df_resampled['Hist'] = m, s, h
            except:
                 df_resampled['MACD'], df_resampled['Signal'], df_resampled['Hist'] = 0, 0, 0

            # ATR
            try:
                df_resampled['ATR'] = self.calculate_atr(df_resampled)
            except:
                df_resampled['ATR'] = 0.0
            
            # Bollinger Bands
            bb_window = 20
            if len(df_resampled) >= bb_window:
                bb_std = df_resampled['close'].rolling(window=bb_window).std()
                df_resampled['BB_Upper'] = df_resampled['SMA_20'] + (bb_std * 2)
                df_resampled['BB_Lower'] = df_resampled['SMA_20'] - (bb_std * 2)
            else:
                 df_resampled['BB_Upper'] = df_resampled['close']
                 df_resampled['BB_Lower'] = df_resampled['close']

            # Summary
            if df_resampled.empty:
                 context[label] = "No data after calc"
                 continue

            last = df_resampled.iloc[-1]
            
            # Safe Access Helper
            def get_val(series, default=0.0):
                val = series
                if pd.isna(val): return default
                return val

            trend = "NEUTRAL"
            close = get_val(last['close'])
            sma20 = get_val(last.get('SMA_20', 0))
            sma50 = get_val(last.get('SMA_50', 0))
            
            if close > sma20 > sma50:
                trend = "BULLISH"
            elif close < sma20 < sma50:
                trend = "BEARISH"
                
            summary = (
                f"Trend: {trend}\n"
                f"Price: {close:.2f}\n"
                f"RSI(14): {get_val(last.get('RSI', 50)):.1f}\n"
                f"MACD: {get_val(last.get('MACD', 0)):.2f} (Hist: {get_val(last.get('Hist', 0)):.2f})\n"
                f"BB: {get_val(last.get('BB_Upper', 0)):.2f} / {get_val(last.get('BB_Lower', 0)):.2f}\n"
                f"ATR: {get_val(last.get('ATR', 0)):.2f}\n"
                f"SMA20: {sma20:.2f}, EMA20: {get_val(last.get('EMA_20', 0)):.2f}"
            )
            context[label] = summary
            
        return context

    def calculate_rsi(self, series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_macd(self, series, slow=26, fast=12, signal=9):
        exp1 = series.ewm(span=fast, adjust=False).mean()
        exp2 = series.ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        sig = macd.ewm(span=signal, adjust=False).mean()
        hist = macd - sig
        return macd, sig, hist

    def calculate_atr(self, df, period=14):
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        return true_range.rolling(window=period).mean()

market_data_service = MarketDataService()
