import os
from typing import List

DEFAULT_SCHEDULE_SYMBOLS: List[str] = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "BNB/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "DOGE/USDT",
    "TRX/USDT",
]


def get_schedule_symbols_from_env(env_var: str = "SCHEDULE_SYMBOLS") -> List[str]:
    raw = os.getenv(env_var, "")
    symbols = [item.strip() for item in raw.split(",") if item.strip()]
    return symbols or list(DEFAULT_SCHEDULE_SYMBOLS)


def get_default_symbol() -> str:
    return DEFAULT_SCHEDULE_SYMBOLS[0]


def get_schedule_timeframes_from_env(env_var: str = "SCHEDULE_TIMEFRAMES") -> List[str]:
    raw = os.getenv(env_var, "")
    timeframes = [item.strip() for item in raw.split(",") if item.strip()]
    return timeframes or ["1m", "1h", "1d"]
