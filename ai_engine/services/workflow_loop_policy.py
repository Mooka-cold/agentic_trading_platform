import asyncio
import time
from typing import Callable


class WorkflowLoopPolicy:
    def build_cycle_session_id(self, symbol: str) -> str:
        return f"auto-{symbol}-{int(time.time())}"

    async def sleep_interval(self, seconds: int, should_stop: Callable[[], bool]) -> None:
        for _ in range(seconds):
            if should_stop():
                return
            await asyncio.sleep(1)


workflow_loop_policy = WorkflowLoopPolicy()
