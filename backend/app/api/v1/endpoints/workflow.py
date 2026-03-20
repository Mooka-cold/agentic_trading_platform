from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_user_db
from shared.models.workflow import WorkflowSession, AgentLog, WorkflowStatus
from pydantic import BaseModel
from typing import Optional, Any, List
from datetime import datetime

router = APIRouter()

class LogCreate(BaseModel):
    agent_id: str
    log_type: str
    content: str
    artifact: Optional[Any] = None

class WorkflowCreate(BaseModel):
    session_id: str
    symbol: str

class WorkflowRunRequest(BaseModel):
    symbol: str
    session_id: Optional[str] = None

@router.get("/status")
def get_workflow_runner_status():
    """
    Proxy status check to AI Engine
    """
    import httpx
    import os
    from app.core.config import settings
    
    try:
        # We need synchronous call here or async refactor. 
        # Since this is sync endpoint, use sync client or convert to async.
        # FastAPI supports async def natively.
        # Let's assume this function can be async
        return {"error": "Use async endpoint"} 
    except Exception as e:
        return {"is_running": False, "error": str(e)}

@router.get("/runner/status")
async def get_runner_status():
    """
    Check if the continuous workflow loop is running in AI Engine.
    """
    import httpx
    from app.core.config import settings
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{settings.AI_ENGINE_URL}/workflow/status")
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        print(f"Error checking AI status: {e}")
        return {"is_running": False, "error": "AI Engine Unreachable"}
    
    return {"is_running": False}

@router.post("/run")
async def run_workflow(req: WorkflowRunRequest):
    import httpx
    from app.core.config import settings
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{settings.AI_ENGINE_URL}/workflow/run", json=req.dict())
            if resp.status_code == 200:
                return resp.json()
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI Engine Unreachable: {e}")

@router.post("/stop")
async def stop_workflow():
    import httpx
    from app.core.config import settings
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{settings.AI_ENGINE_URL}/workflow/stop")
            if resp.status_code == 200:
                return resp.json()
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI Engine Unreachable: {e}")

class WorkflowUpdate(BaseModel):
    status: Optional[str] = None
    end_time: Optional[datetime] = None
    action: Optional[str] = None
    review_status: Optional[str] = None
    periodic_review_status: Optional[str] = None # Added missing field

@router.patch("/session/{session_id:path}")
def update_session(session_id: str, update: WorkflowUpdate, db: Session = Depends(get_user_db)):
    # print(f"DEBUG: Updating session {session_id} with {update.dict(exclude_unset=True)}", flush=True)
    session = db.query(WorkflowSession).filter(WorkflowSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if update.status:
        try:
            session.status = WorkflowStatus(update.status.upper())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")
        
    if update.end_time:
        session.end_time = update.end_time
    elif update.status == "COMPLETED" and not session.end_time:
        session.end_time = datetime.utcnow()
        
    if update.action:
        session.action = update.action
        
    if update.review_status:
        session.review_status = update.review_status
        
    if update.periodic_review_status:
        session.periodic_review_status = update.periodic_review_status
        
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"ERROR: Failed to commit session update: {e}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))
        
    return {"status": "updated"}

@router.post("/session")
def create_session(wf: WorkflowCreate, db: Session = Depends(get_user_db)):
    # Check if exists
    existing = db.query(WorkflowSession).filter(WorkflowSession.id == wf.session_id).first()
    if existing:
        return {"status": "exists"}
        
    session = WorkflowSession(id=wf.session_id, symbol=wf.symbol, status=WorkflowStatus.RUNNING)
    db.add(session)
    db.commit()
    return {"status": "created"}

@router.get("/session/{session_id:path}/logs")
def get_session_logs(session_id: str, db: Session = Depends(get_user_db)):
    """
    Get raw logs for a specific session to be used as context for Reflector.
    """
    session = db.query(WorkflowSession).filter(WorkflowSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    logs = db.query(AgentLog).filter(AgentLog.session_id == session.id).order_by(AgentLog.created_at.asc()).all()
    
    # Return simplified log structure for LLM consumption
    return {
        "logs": [
            {
                "agent": l.agent_id,
                "type": l.log_type,
                "content": l.content,
                "timestamp": l.created_at.isoformat()
            }
            for l in logs
        ]
    }

@router.get("/session/{session_id:path}")
def get_workflow_session(session_id: str, db: Session = Depends(get_user_db)):
    """
    Get detailed logs for a specific session (for tuning/debugging).
    Includes extracted trade_plan if available.
    """
    from app.services.paper_trading import PaperOrder, SessionReflection
    import json
    
    session = db.query(WorkflowSession).filter(WorkflowSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    logs = db.query(AgentLog).filter(AgentLog.session_id == session.id).order_by(AgentLog.created_at.asc()).all()
    
    # Try to extract trade plan from Strategist log
    trade_plan = None
    for log in logs:
        if log.agent_id == "strategist" and log.log_type == "output" and log.artifact:
            # Assuming the last strategist output is the final plan
            try:
                # If artifact is string, parse it. If dict, use directly.
                artifact_data = log.artifact
                if isinstance(artifact_data, str):
                    artifact_data = json.loads(artifact_data)
                
                # Check if it has the plan structure
                if "action" in artifact_data:
                    stop_loss = artifact_data.get("stop_loss")
                    if stop_loss is None:
                        stop_loss = artifact_data.get("sl")
                    take_profit = artifact_data.get("take_profit")
                    if take_profit is None:
                        take_profit = artifact_data.get("tp")
                    normalized_plan = dict(artifact_data)
                    normalized_plan["stop_loss"] = stop_loss
                    normalized_plan["take_profit"] = take_profit
                    trade_plan = normalized_plan
            except:
                pass

    # Fetch Reflections
    # 1. Fetch reflections directly by session_id
    reflections = db.query(SessionReflection).filter(SessionReflection.session_id == session.id).all()
    
    # Convert logs to list
    log_list = [
        {
            "id": l.id,
            "agent_id": l.agent_id,
            "type": l.log_type,
            "content": l.content,
            "artifact": l.artifact,
            "timestamp": l.created_at
        }
        for l in logs
    ]
    
    # Append Reflections as "Virtual Logs" from Reflector
    # Deduplicate reflections if multiple exist for same stage (keep latest)
    # Actually, let's just show all, but we might want to sort them.
    for r in reflections:
        # Check if this reflection is already in logs (unlikely if we use virtual IDs)
        log_list.append({
            "id": f"ref-{r.id}", # Virtual ID
            "agent_id": "reflector",
            "type": "output",
            "content": f"[{r.stage}] {r.content}",
            "artifact": {
                "type": "REFLECTION",
                "stage": r.stage,
                "content": r.content, # JSON string
                "score": float(r.score) if r.score else 0
            },
            "timestamp": r.created_at
        })
        
    # Re-sort by timestamp
    def get_timestamp(x):
        ts = x['timestamp']
        # Normalize to naive UTC if it has timezone info
        if ts.tzinfo is not None:
            return ts.replace(tzinfo=None)
        return ts
    
    log_list.sort(key=get_timestamp)

    return {
        "session": {
            "id": session.id,
            "symbol": session.symbol,
            "status": session.status.value,
            "start_time": session.start_time,
            "trade_plan": trade_plan, # Expose trade plan
            "logs": log_list
        }
    }
@router.post("/{session_id:path}/log")
def add_log(session_id: str, log: LogCreate, db: Session = Depends(get_user_db)):
    # session_id might contain slashes if using :path.
    # But wait, if we have /log at the end, Starlette's path converter works differently.
    # Actually, path parameters cannot contain the separator character (/) unless they are at the end?
    # No, {path:path} captures everything.
    # If we have /{session_id:path}/log, it might be ambiguous.
    # Starlette/FastAPI usually supports it if it's distinguishable.
    # Let's try.
    
    session = db.query(WorkflowSession).filter(WorkflowSession.id == session_id).first()
    if not session:
        # Create ad-hoc session if missing (e.g. legacy logs)
        session = WorkflowSession(id=session_id, symbol="UNKNOWN", status=WorkflowStatus.RUNNING)
        db.add(session)
        db.commit()
        
    db_log = AgentLog(
        session_id=session_id,
        agent_id=log.agent_id,
        log_type=log.log_type,
        content=log.content,
        artifact=log.artifact
    )
    db.add(db_log)
    db.commit()
    return {"status": "logged"}

@router.get("/latest")
def get_latest_workflow(symbol: str = "BTC/USDT", db: Session = Depends(get_user_db)):
    session = db.query(WorkflowSession).filter(WorkflowSession.symbol == symbol).order_by(WorkflowSession.start_time.desc()).first()
    if not session:
        return {"session": None}
    
    logs = db.query(AgentLog).filter(AgentLog.session_id == session.id).order_by(AgentLog.created_at.asc()).all()
    
    return {
        "session": {
            "id": session.id,
            "status": session.status.value,
            "start_time": session.start_time,
            "logs": [
                {
                    "id": l.id,
                    "agent_id": l.agent_id,
                    "type": l.log_type,
                    "content": l.content,
                    "artifact": l.artifact,
                    "timestamp": l.created_at
                }
                for l in logs
            ]
        }
    }

@router.get("/history")
def get_workflow_history(
    symbol: Optional[str] = None,
    session_id: Optional[str] = None,
    status: Optional[str] = None,
    action: Optional[str] = None,
    review_status: Optional[str] = None,
    has_profit: Optional[bool] = None,
    limit: int = 10,
    db: Session = Depends(get_user_db)
):
    from app.services.paper_trading import PaperOrder, SessionReflection
    from sqlalchemy import or_, and_

    query = db.query(WorkflowSession)
    
    # 1. Session ID Filter (Highest Priority)
    if session_id:
        # Prefix match (Utilize B-Tree Index)
        query = query.filter(WorkflowSession.id.startswith(session_id))
    
    # 2. Other Filters
    if symbol:
        query = query.filter(WorkflowSession.symbol == symbol)
    if status:
        try:
             s_enum = WorkflowStatus(status.upper())
             query = query.filter(WorkflowSession.status == s_enum)
        except ValueError:
             pass # Invalid status enum, ignore filter
             
    if action:
        query = query.filter(WorkflowSession.action == action.upper())
    if review_status:
        query = query.filter(WorkflowSession.review_status == review_status.upper())
            
    # Profit Filter (Keep existing or optimize later)
    # ...
    
    sessions = query.order_by(WorkflowSession.start_time.desc()).limit(limit).all()
    
    history = []
    for s in sessions:
        end_time = s.end_time or datetime.utcnow()
        duration_seconds = int(max((end_time - s.start_time).total_seconds(), 0))
        log_count = db.query(AgentLog).filter(AgentLog.session_id == s.id).count()
        
        history.append({
            "id": s.id,
            "symbol": s.symbol,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "status": s.status.value,
            "action": s.action,          # New field
            "review_status": s.review_status, # New field
            "duration_seconds": duration_seconds,
            "log_count": log_count,
            "has_profit": False # TODO
        })
        
    return {"history": history}

@router.delete("/session/{session_id:path}")
def delete_session(session_id: str, db: Session = Depends(get_user_db)):
    session = db.query(WorkflowSession).filter(WorkflowSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Cascade delete logs
    db.query(AgentLog).filter(AgentLog.session_id == session.id).delete()
    
    # Cascade delete reflections
    from app.services.paper_trading import SessionReflection
    db.query(SessionReflection).filter(SessionReflection.session_id == session.id).delete()
    
    db.delete(session)
    db.commit()
    return {"status": "deleted"}

@router.delete("/sessions/cleanup")
def cleanup_failed_sessions(db: Session = Depends(get_user_db)):
    """
    Delete all sessions with status FAILED.
    Also mark STALE RUNNING sessions (>10 mins) as FAILED.
    """
    from datetime import datetime, timedelta
    
    # 1. Mark Stale Sessions as FAILED
    stale_threshold = datetime.utcnow() - timedelta(minutes=10)
    stale_sessions = db.query(WorkflowSession).filter(
        WorkflowSession.status == WorkflowStatus.RUNNING,
        WorkflowSession.start_time < stale_threshold
    ).all()
    
    marked_count = 0
    for s in stale_sessions:
        s.status = WorkflowStatus.FAILED
        s.end_time = datetime.utcnow()
        # Add a system log to explain why
        db_log = AgentLog(
            session_id=s.id,
            agent_id="system",
            log_type="error",
            content="Session marked as FAILED due to timeout (Zombie Session cleanup).",
            artifact={"reason": "timeout_10m"}
        )
        db.add(db_log)
        marked_count += 1
    
    if marked_count > 0:
        db.commit()

    # 2. Delete FAILED Sessions
    failed_sessions = db.query(WorkflowSession).filter(WorkflowSession.status == WorkflowStatus.FAILED).all()
    count = 0
    for s in failed_sessions:
        # Delete logs first
        db.query(AgentLog).filter(AgentLog.session_id == s.id).delete()
        
        # Delete reflections
        from app.services.paper_trading import SessionReflection
        db.query(SessionReflection).filter(SessionReflection.session_id == s.id).delete()
        
        db.delete(s)
        count += 1
    
    db.commit()
    return {"status": "cleaned", "deleted_count": count, "marked_failed_count": marked_count}

@router.get("/list")
def list_workflow_sessions(limit: int = 20, db: Session = Depends(get_user_db)):
    """
    List recent workflow sessions
    """
    sessions = db.query(WorkflowSession).order_by(WorkflowSession.start_time.desc()).limit(limit).all()
    
    return [
        {
            "id": s.id,
            "symbol": s.symbol,
            "status": s.status.value,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "action": s.action,
            "review_status": s.review_status
        }
        for s in sessions
    ]
