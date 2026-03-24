import asyncio
from typing import Any, List
import httpx

from core.config import settings


class WorkflowRuntimeAPI:
    def __init__(self, backend_url: str):
        self.backend_url = backend_url.rstrip("/")

    async def fetch_account_balance_with_retry(self, retries: int = 3, retry_delay: float = 1.0) -> float:
        last_error = None
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    res = await client.get(f"{self.backend_url}/api/v1/trade/paper/account")
                if res.status_code != 200:
                    raise RuntimeError(f"paper account api status={res.status_code}, body={res.text[:200]}")
                payload = res.json() if isinstance(res.json(), dict) else {}
                if "balance" not in payload:
                    raise RuntimeError("paper account api missing balance field")
                return float(payload["balance"])
            except Exception as exc:
                last_error = exc
                if attempt < retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
        raise RuntimeError(f"failed to fetch account balance after {retries} attempts: {last_error}")

    async def fetch_positions(self) -> List[Any]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.backend_url}/api/v1/trade/positions")
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, list):
                        return data
        except Exception as exc:
            print(f"Warning: Failed to fetch positions: {exc}", flush=True)
        return []


workflow_runtime_api = WorkflowRuntimeAPI(settings.BACKEND_URL)
