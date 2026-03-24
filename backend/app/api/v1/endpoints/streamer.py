from fastapi import APIRouter

router = APIRouter()

@router.post("/health")
def check_streamer_health():
    return {
        "status": "external_managed",
        "managed_by": "docker_compose_service:market-streamer",
        "autostart_enabled": False
    }

@router.post("/start")
def start_streamer():
    return {
        "status": "disabled",
        "reason": "managed_externally",
        "managed_by": "docker_compose_service:market-streamer"
    }

@router.post("/stop")
def stop_streamer():
    return {
        "status": "disabled",
        "reason": "managed_externally",
        "managed_by": "docker_compose_service:market-streamer"
    }
