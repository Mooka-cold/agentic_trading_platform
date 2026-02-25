from fastapi import FastAPI
from pydantic import BaseModel
from core.prompt_loader import registry

app = FastAPI(title="AI Engine", version="0.1.0")

class AnalysisRequest(BaseModel):
    symbol: str
    market_context: str
    news_context: str

@app.post("/analyze")
async def analyze_market(req: AnalysisRequest):
    # Example: Loading prompt from registry
    # In real implementation, this would invoke LangChain agent
    prompt = registry.get("strategist/generation")
    
    # Mock response
    return {
        "decision": "HOLD", 
        "reason": "Market is volatile",
        "prompt_used": prompt.messages[0].prompt.template[:50] + "..."
    }

@app.get("/health")
async def health():
    return {"status": "ok", "service": "ai-engine"}
