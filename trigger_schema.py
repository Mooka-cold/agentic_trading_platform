import asyncio
from ai_engine.services.sentiment import sentiment_service

async def main():
    sentiment_service._ensure_interpretation_schema()
    print("Schema initialized.")

if __name__ == "__main__":
    asyncio.run(main())
