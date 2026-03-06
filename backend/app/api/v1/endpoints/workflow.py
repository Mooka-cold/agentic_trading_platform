from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_user_db
from app.models.workflow import WorkflowSession, AgentLog, WorkflowStatus
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

@router.patch("/session/{session_id:path}")
def update_session(session_id: str, update: WorkflowUpdate, db: Session = Depends(get_user_db)):
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
        
    db.commit()
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

@router.get("/session/{session_id:path}")
def get_workflow_session(session_id: str, db: Session = Depends(get_user_db)):
    """
    Get detailed logs for a specific session (for tuning/debugging).
    """
    # If session_id comes in URL-encoded, FastAPI/Starlette might decode it or not depending on server.
    # But using :path captures everything.
    # Note: If there are other routes after this, :path might shadow them.
    # Currently this is the last route (or close to last).
    # But wait, we have /{session_id}/log below.
    # If session_id contains slashes, we must be careful.
    
    from app.services.paper_trading import PaperOrder, TradeReflection
    
    session = db.query(WorkflowSession).filter(WorkflowSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    logs = db.query(AgentLog).filter(AgentLog.session_id == session.id).order_by(AgentLog.created_at.asc()).all()
    
    # Fetch Reflections
    # 1. Find orders in this session
    orders = db.query(PaperOrder).filter(PaperOrder.session_id == session.id).all()
    reflections = []
    if orders:
        reflections = db.query(TradeReflection).filter(TradeReflection.order_id.in_([o.id for o in orders])).all()
    
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
    for r in reflections:
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
    log_list.sort(key=lambda x: x['timestamp'])

    return {
        "session": {
            "id": session.id,
            "symbol": session.symbol,
            "status": session.status.value,
            "start_time": session.start_time,
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
    status: Optional[str] = None,
    action: Optional[str] = None,
    review_status: Optional[str] = None,
    has_profit: Optional[bool] = None,
    limit: int = 10,
    db: Session = Depends(get_user_db)
):
    from app.services.paper_trading import PaperOrder, TradeReflection
    
    query = db.query(WorkflowSession)
    if symbol:
        query = query.filter(WorkflowSession.symbol == symbol)
    if status:
        query = query.filter(WorkflowSession.status == WorkflowStatus(status.upper()))
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
