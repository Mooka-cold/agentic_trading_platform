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
        logger.info("Subscribing to Redis channel: market_signals")
        stream = redis_stream.subscribe_channel("market_signals")
        
        try:
            async for message in stream:
                if not self.is_running: break
                
                try:
                    # message is already a JSON string from Redis
                    data = json.loads(message)
                    symbol = data.get("symbol")
                    signals = data.get("signals")
                    
                    if symbol and signals:
                        logger.info(f"Watcher received signal for {symbol}: {signals}")
                        
                        # Trigger Workflow
                        # Use a unique session ID for this trigger
                        # We use 'signal-' prefix to distinguish from 'continuous-' sessions
                        import time
                        session_id = f"signal-{symbol}-{int(time.time())}"
                        
                        # Run workflow asynchronously
                        # Note: run_workflow checks for locks, so it's safe to call concurrently
                        asyncio.create_task(
                            self.workflow_engine.run_workflow(symbol, session_id)
                        )
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in market_signals: {message}")
                except Exception as e:
                    logger.error(f"Error processing signal: {e}")
        except Exception as e:
            logger.error(f"Redis stream error: {e}")
            # Retry logic could be added here

    async def stop(self):
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Watcher Service Stopped.")
