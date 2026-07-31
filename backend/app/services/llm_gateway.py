import json
import logging
from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.config import settings

logger = logging.getLogger("LLMGateway")

class LLMGateway:
    """
    无状态 LLM 网关：纯代理/路由/限流/计费
    所有 Agent Runtime 的请求都会在这里被拦截和代理。
    """
    def __init__(self):
        # Default global LLM fallback
        self.default_llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.OPENAI_API_BASE,
            temperature=0.2
        )

    def _get_llm_for_user(self, user_id: str) -> ChatOpenAI:
        """
        获取系统统一的 LLM 实例（SaaS 中心化模式）。
        所有用户统一使用系统的 Key。
        """
        return self.default_llm

    async def invoke(self, user_id: str, messages: List[dict], output_schema: dict = None) -> Any:
        """
        接收请求，计费与限流拦截，路由至对应模型并返回。
        """
        # 1. TODO: Rate Limiting Check (Redis)
        
        # 2. 构造 LangChain Messages
        langchain_messages = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            else:
                langchain_messages.append(HumanMessage(content=content))
                
        # 3. Model Routing
        llm = self._get_llm_for_user(user_id)
        
        # 4. Invoke LLM
        try:
            # TODO: 如果有 output_schema，可以使用 bind_tools 或者 JSON Mode
            response = await llm.ainvoke(langchain_messages)
            
            # 5. TODO: 计费统计 (Token 消耗)
            # tokens_used = response.response_metadata.get("token_usage")
            
            return {
                "content": response.content,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"LLM Gateway invocation failed for user {user_id}: {e}")
            raise e

llm_gateway = LLMGateway()