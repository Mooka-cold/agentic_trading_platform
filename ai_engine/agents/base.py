import asyncio
import httpx
from typing import Dict, Any, Optional
from model.state import AgentState, AgentLog
import redis.asyncio as redis
import json
import logging
from langchain_openai import ChatOpenAI
from core.config import settings
from core.prompt_loader import registry
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.messages import SystemMessage
from sqlalchemy import create_engine, text

# Configure Redis for SSE streaming
# Use settings from core.config which handles .env loading
REDIS_URL = settings.REDIS_URL

class BaseAgent:
    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name
        self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        self.logger = logging.getLogger(f"agent.{agent_id}")
        self.output_language = self._load_output_language()

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
            backend_url = settings.BACKEND_URL
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

    def _load_output_language(self) -> str:
        default_lang = "中文"
        try:
            user_engine = create_engine(settings.DATABASE_USER_URL)
            with user_engine.connect() as conn:
                result = conn.execute(text("SELECT value FROM system_configs WHERE key = :key"), {"key": "AGENT_OUTPUT_LANGUAGE"})
                row = result.fetchone()
                if row and row[0]:
                    raw = str(row[0]).strip()
                    lower = raw.lower()
                    if lower in ["zh", "zh-cn", "cn", "chinese", "中文"]:
                        return "中文"
                    if lower in ["en", "en-us", "english", "英文"]:
                        return "English"
                    return raw
        except Exception:
            return default_lang
        return default_lang

    async def call_llm(self, prompt_vars: Dict[str, Any], state: AgentState = None, output_model: type = None, prompt_name: str = None, extra_preamble: str = None) -> Any:
        """
        Loads the agent's prompt, injects variables, and calls the LLM.

        If `extra_preamble` is provided, it is appended to the system template
        AFTER loading the persona's normal prompt. This is used by Decision
        Agents in debate mode to inject a debate-specific output contract
        without having to mutate the persona YAMLs.
        """
        target_prompt = prompt_name if prompt_name else self.agent_id

        system_prompt_override = None
        if state and state.custom_prompts:
            system_prompt_override = state.custom_prompts.get(target_prompt)

        try:
            prompt = registry.get_agent_prompt(target_prompt, system_prompt_override=system_prompt_override)
        except FileNotFoundError:
            # Fallback to dynamic prompt if file doesn't exist
            from langchain_core.prompts import ChatPromptTemplate
            template = system_prompt_override if system_prompt_override else f"You are a trading agent ({target_prompt})."
            prompt = ChatPromptTemplate.from_template(template)

        # Add format instructions if output model is provided
        parser = None
        if output_model:
            parser = JsonOutputParser(pydantic_object=output_model)
            # Ensure format instructions are added if it's a dynamic template
            if "format_instructions" not in prompt.input_variables and "{format_instructions}" not in prompt.messages[0].prompt.template:
                prompt.messages[0].prompt.template += "\n\n{format_instructions}"

        # Inject extra preamble by wrapping template if needed.
        # This lets Decision agents in debate mode keep the persona's
        # tone and philosophy while gaining a strict debate output contract.
        if extra_preamble:
            try:
                prompt.messages[0].prompt.template = prompt.messages[0].prompt.template + "\n\n" + extra_preamble
                if "{format_instructions}" not in prompt.messages[0].prompt.template and parser:
                    prompt.messages[0].prompt.template += "\n\n{format_instructions}"
            except Exception:
                # If the prompt doesn't support mutation, fall through
                pass

        merged_vars = {**prompt_vars, "output_language": self.output_language}
        if parser:
            merged_vars["format_instructions"] = parser.get_format_instructions()
            
        prompt_value = await prompt.ainvoke(merged_vars)
        
        # 提取 user_id
        user_id = "default"
        if state and state.user_id:
            user_id = state.user_id
            
        language_guardrail = (
            f"Language requirement: all explanatory and narrative text must be in {self.output_language}. "
            "Keep JSON field names and enum tokens in English unless prompt explicitly requires otherwise."
        )
        
        # 构造网关请求 Payload
        raw_messages = [{"role": "system", "content": language_guardrail}]
        for msg in prompt_value.to_messages():
            role = "system" if isinstance(msg, SystemMessage) else "user"
            raw_messages.append({"role": role, "content": str(msg.content)})
            
        payload = {
            "user_id": user_id,
            "messages": raw_messages
        }
        
        # Call LLM Gateway
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            resp = await client.post(f"{settings.BACKEND_URL}/api/v1/system/llm/invoke", json=payload)
            if resp.status_code != 200:
                raise Exception(f"LLM Gateway failed: {resp.text}")
            resp_data = resp.json()
            content = resp_data.get("content", "")
            
        if parser:
            parsed_dict = parser.parse(content)
            if output_model:
                return output_model(**parsed_dict)
            return parsed_dict
        
        class DummyResponse:
            def __init__(self, content):
                self.content = content
        return DummyResponse(content)
