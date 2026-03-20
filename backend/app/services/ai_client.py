import httpx
from sqlalchemy.orm import Session
from app.db.session import SessionLocalUser
from shared.models.signal import Signal

from app.core.config import settings

# Use docker service name or config
AI_ENGINE_URL = f"{settings.AI_ENGINE_URL}/analyze"

async def analyze_and_store(symbol: str):
    print(f"🧠 Asking AI Engine to analyze {symbol}...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(AI_ENGINE_URL, json={"symbol": symbol}, timeout=30.0)
            
            if response.status_code == 200:
                data = response.json()
                # data = { "action": "HOLD", "confidence": 0.65, "reasoning": "..." }
                
                db = SessionLocalUser()
                try:
                    signal = Signal(
                        symbol=symbol,
                        action=data.get("action", "HOLD"),
                        confidence=data.get("confidence", 0.0),
                        reasoning=data.get("reasoning", ""),
                        model_used="qwen-plus"
                    )
                    db.add(signal)
                    db.commit()
                    print(f"✅ Saved signal for {symbol}: {signal.action} ({signal.confidence})")
                except Exception as e:
                    print(f"❌ DB Error saving signal: {e}")
                    db.rollback()
                finally:
                    db.close()
            else:
                print(f"❌ AI Engine Error: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"❌ Failed to call AI Engine: {e}")

async def run_analysis_cycle(symbols: list):
    for symbol in symbols:
        await analyze_and_store(symbol)
