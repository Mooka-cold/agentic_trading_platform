import json
import asyncio
import logging
from services.redis_stream import redis_stream

logger = logging.getLogger("watcher")

class WatcherService:
    def __init__(self, workflow_engine):
        self.workflow_engine = workflow_engine
        self.is_running = False
        self.task = None

    async def start(self):
        if self.is_running: return
        self.is_running = True
        logger.info("Watcher Service Started. Listening to 'market_signals'...")
        self.task = asyncio.create_task(self._listen())

    async def _listen(self):
        reconnect_delay = 2
        while self.is_running:
            try:
                logger.info("Subscribing to Redis channel: market_signals")
                stream = redis_stream.subscribe_channel("market_signals")
                async for message in stream:
                    if not self.is_running:
                        break
                    try:
                        data = json.loads(message)
                        symbol = data.get("symbol")
                        signals = data.get("signals")
                        if symbol and signals:
                            if not self.workflow_engine.is_running:
                                continue
                            logger.info(f"Watcher received signal for {symbol}: {signals}")
                            import time
                            session_id = f"signal-{symbol}-{int(time.time())}"
                            asyncio.create_task(self.workflow_engine.run_workflow(symbol, session_id))
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON in market_signals: {message}")
                    except Exception as e:
                        logger.error(f"Error processing signal: {e}")
                reconnect_delay = 2
            except Exception as e:
                logger.error(f"Redis stream error: {e}. Reconnecting in {reconnect_delay}s")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 30)

    async def stop(self):
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                logger.info("Watcher background task cancelled.")
        logger.info("Watcher Service Stopped.")
