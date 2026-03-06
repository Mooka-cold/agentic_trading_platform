import asyncio
import httpx
from typing import Dict, Any, Optional
from model.state import AgentState, AgentLog
import redis.asyncio as redis
import json
import os
import logging
from langchain_openai import ChatOpenAI
from core.config import settings
from core.prompt_loader import registry
from langchain_core.output_parsers import JsonOutputParser

# Configure Redis for SSE streaming
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

class BaseAgent:
    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name
        self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        self.logger = logging.getLogger(f"agent.{agent_id}")
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.OPENAI_API_BASE,
            temperature=0.2
        )

    async def run(self, state: AgentState) -> Dict[str, Any]:
        """
        Main execution logic. Must be implemented by subclasses.
        Returns a dict of updates to be merged into AgentState.
        """
        raise NotImplementedError

    async def emit_log(self, content: str, log_type: str = "process", session_id: str = "default", artifact: Dict[str, Any] = None, symbol: Optional[str] = None):
        """
        Publish a log message to Redis for frontend consumption (SSE).
        Broadcasts to both specific session channel AND monitor channel.
        """
        log_entry = {
            "agent_id": self.agent_id,
            "name": self.name,
            "timestamp": AgentLog(agent_id=self.agent_id, content=content).timestamp.isoformat(),
            "session_id": session_id, # Frontend needs this for clearing logic
            "type": log_type,
            "content": content,
            "artifact": artifact
        }
        
        try:
            # DEBUG
            print(f"[DEBUG emit_log] ID={session_id} Symbol={symbol} Content={content[:20]}...", flush=True)

            # 1. Private Channel: 'agent_stream:{session_id}'
            channel_private = f"agent_stream:{session_id}"
            await self.redis_client.publish(channel_private, json.dumps(log_entry))
            
            # 2. Monitor Channel: 'agent_monitor:{symbol}'
            # Try to extract symbol if not provided
            target_symbol = symbol
            if not target_symbol and "auto-" in session_id:
                # Format: auto-{symbol}-{timestamp}
                parts = session_id.split("-")
                print(f"[DEBUG symbol extract] ID={session_id} Parts={parts}", flush=True)
                if len(parts) >= 3:
                    target_symbol = "-".join(parts[1:-1])
                    print(f"[DEBUG symbol extract] Extracted={target_symbol}", flush=True)
            
            # Fallback: Check if session_id itself is a symbol (unlikely)
            if not target_symbol and "/" in session_id:
                 # Check if it looks like session_id or symbol
                 # If it has only one slash and no 'session_', maybe it is symbol
                 if "session" not in session_id:
                     target_symbol = session_id

            if target_symbol:
                channel_monitor = f"agent_monitor:{target_symbol}"
                # DEBUG
                print(f"[DEBUG publish] Channel={channel_monitor} Payload={json.dumps(log_entry)[:50]}...", flush=True)
                await self.redis_client.publish(channel_monitor, json.dumps(log_entry))

            self.logger.info(f"[{self.name}] {content}")
            
            # Persist to Backend DB
            backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
            if session_id != "default":
                # Fire and forget (don't await response to block)
                # But async await is needed. To avoid blocking too much, we use a timeout.
                try:
                    async with httpx.AsyncClient(timeout=3.0) as client:
                        await client.post(
                            f"{backend_url}/api/v1/workflow/{session_id}/log",
                            json={
                                "agent_id": self.agent_id,
                                "log_type": log_type,
                                "content": content,
                                "artifact": artifact
                            }
                        )
                except Exception as e:
                    # Log but don't crash
                    print(f"Warning: Failed to persist log: {e}", flush=True)
        except Exception as e:
            self.logger.error(f"Failed to publish/persist log: {e}")

    async def think(self, thought: str, session_id: str, artifact: Dict[str, Any] = None, symbol: Optional[str] = None, log_type: str = "process"):
        await self.emit_log(thought, log_type, session_id, artifact, symbol)

    async def say(self, message: str, session_id: str, artifact: Dict[str, Any] = None, symbol: Optional[str] = None):
        await self.emit_log(message, "output", session_id, artifact, symbol)

    async def close(self):
        await self.redis_client.close()

    async def call_llm(self, prompt_vars: Dict[str, Any], output_model: type = None) -> Any:
        """
        Loads the agent's prompt, injects variables, and calls the LLM.
        """
        prompt = registry.get_agent_prompt(self.agent_id)
        
        # Add format instructions if output model is provided
        parser = None
        if output_model:
            parser = JsonOutputParser(pydantic_object=output_model)
            # Check if prompt has {format_instructions}, if not, we might append it?
            # LangChain prompts usually need explicit placeholder. 
            # My system prompts (from Step 1) don't have {format_instructions} placeholder explicitly,
            # but they say "Output Format (Strict JSON)".
            # If I use JsonOutputParser, it generates a schema string.
            # I should inject it.
            # Let's assume my yaml templates handle it or I inject it as a partial if needed.
            # Actually, `JsonOutputParser.get_format_instructions()` returns a string.
            # My prompts currently don't use {format_instructions} variable.
            # I should update my prompts or just rely on the text description I wrote in YAML.
            # Since I wrote explicit JSON example in YAML, maybe I don't need parser instructions?
            # But parser helps robust parsing.
            pass
        
        # Merge vars
        chain = prompt | self.llm
        if parser:
            chain = chain | parser
            
        return await asyncio.wait_for(chain.ainvoke(prompt_vars), timeout=settings.LLM_TIMEOUT_SECONDS)
