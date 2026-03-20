from fastapi import APIRouter, HTTPException
import subprocess
import os
import signal
import sys
from pathlib import Path

router = APIRouter()

STREAMER_PID_FILE = Path("/tmp/market_streamer.pid")

def is_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

@router.post("/health")
def check_streamer_health():
    """
    Check if streamer process is running. If not, restart it.
    This is called by Scheduler.
    """
    pid = None
    if STREAMER_PID_FILE.exists():
        try:
            pid = int(STREAMER_PID_FILE.read_text().strip())
        except:
            pass
            
    if pid and is_process_running(pid):
        return {"status": "running", "pid": pid}
        
    # Not running, start it
    return start_streamer()

@router.post("/start")
def start_streamer():
    """Start the Streamer process"""
    pid = None
    if STREAMER_PID_FILE.exists():
        try:
            pid = int(STREAMER_PID_FILE.read_text().strip())
            if is_process_running(pid):
                return {"status": "already_running", "pid": pid}
        except:
            pass
            
    # Start process
    try:
        # Assuming we are in backend/app/api/v1/endpoints
        # We need to run: python -m app.services.streamer.main
        # Working directory should be backend root
        backend_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        project_root = backend_root.parent
        
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{str(project_root)}:{str(backend_root)}"
        
        # Redirect stdout/stderr to log file for debugging
        log_file = open(backend_root / "streamer.log", "a")
        
        proc = subprocess.Popen(
            [sys.executable, "-m", "app.services.streamer.main"],
            cwd=str(backend_root),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True # Detach
        )
        
        STREAMER_PID_FILE.write_text(str(proc.pid))
        
        return {"status": "started", "pid": proc.pid}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start streamer: {e}")

@router.post("/stop")
def stop_streamer():
    """Stop the Streamer process"""
    if not STREAMER_PID_FILE.exists():
        return {"status": "not_running"}
        
    try:
        pid = int(STREAMER_PID_FILE.read_text().strip())
        if is_process_running(pid):
            os.kill(pid, signal.SIGTERM)
            return {"status": "stopped", "pid": pid}
        else:
            return {"status": "not_running_zombie_pid"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop streamer: {e}")
