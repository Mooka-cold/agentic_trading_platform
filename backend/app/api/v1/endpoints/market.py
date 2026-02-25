from fastapi import APIRouter

router = APIRouter()

@router.get("/klines")
async def get_klines(symbol: str = "BTC/USDT", interval: str = "1h"):
    # TODO: Fetch from TimescaleDB
    return {"symbol": symbol, "data": []}
