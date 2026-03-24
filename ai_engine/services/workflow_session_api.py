import asyncio
from typing import Any, Dict
import httpx
from datetime import datetime, timezone

from core.config import settings


class WorkflowSessionAPI:
    def __init__(self, backend_url: str):
        self.backend_url = backend_url.rstrip("/")

    async def create_session_with_retry(
        self,
        session_id: str,
        symbol: str,
        retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 5.0,
    ) -> bool:
        last_error = None
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    await client.post(
                        f"{self.backend_url}/api/v1/workflow/session",
                        json={"session_id": session_id, "symbol": symbol},
                    )
                return True
            except Exception as exc:
                last_error = exc
                if attempt < retries - 1:
                    await asyncio.sleep(retry_delay)
        print(f"Warning: Failed to create session after {retries} attempts: {last_error}", flush=True)
        return False

    async def patch_session(
        self,
        session_id: str,
        payload: Dict[str, Any],
        timeout: float = 5.0,
    ) -> bool:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                await client.patch(
                    f"{self.backend_url}/api/v1/workflow/session/{session_id}",
                    json=payload,
                )
            return True
        except Exception as exc:
            print(f"Warning: Failed to patch session {session_id}: {exc}", flush=True)
            return False

    async def mark_failed(self, session_id: str) -> bool:
        return await self.patch_session(session_id=session_id, payload={"status": "FAILED"})

    async def mark_rejected(self, session_id: str, failed: bool = True) -> bool:
        payload = {"review_status": "REJECTED"}
        if failed:
            payload["status"] = "FAILED"
        return await self.patch_session(session_id=session_id, payload=payload)

    async def mark_completed(self, session_id: str, payload: Dict[str, Any] | None = None) -> bool:
        base_payload: Dict[str, Any] = {
            "status": "COMPLETED",
            "end_time": datetime.now(timezone.utc).isoformat(),
        }
        if payload:
            base_payload.update(payload)
        return await self.patch_session(session_id=session_id, payload=base_payload)


workflow_session_api = WorkflowSessionAPI(settings.BACKEND_URL)
