import uuid
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import select
from shared.models.user import UserPrompt, UserAutomationRule, SystemPersona, UserTeamConfig

class SessionManager:
    """
    负责提取用户隔离上下文（Session, State, Rules, Team Config）
    为 AI 工作流的实例化提供上下文环境
    """
    def __init__(self, db: Session):
        self.db = db

    def get_user_prompts(self, user_id: uuid.UUID) -> Dict[str, str]:
        """
        获取用户的所有自定义 Prompt (旧版兼容或用作 Persona 额外补丁)
        """
        prompts = self.db.execute(
            select(UserPrompt)
            .where(UserPrompt.user_id == user_id)
            .where(UserPrompt.is_active == True)
        ).scalars().all()
        
        return {p.agent_role: p.system_prompt_override for p in prompts if p.system_prompt_override}

    def get_active_automation_rules(self, rule_type: str = None) -> List[UserAutomationRule]:
        """
        扫描生效的自动化规则 (供 Trigger Engine 使用)
        """
        query = select(UserAutomationRule).where(UserAutomationRule.is_active == True)
        if rule_type:
            query = query.where(UserAutomationRule.rule_type == rule_type)
        return self.db.execute(query).scalars().all()

    def get_team_config(self, user_id: uuid.UUID) -> Dict[str, Any]:
        config = self.db.execute(select(UserTeamConfig).where(UserTeamConfig.user_id == user_id)).scalar_one_or_none()

        # 新系统要求：未配置交易天团时返回空骨架，而不是退化到旧的 default_* 团队。
        if not config:
            print(f"[SessionMgr] Initialized empty team skeleton for new user {user_id}", flush=True)
            return {
                "market_agent_ids": [],
                "strategy_agent_ids": [],
                "risk_agent_ids": [],
                "finalizer_agent_id": None
            }

        return {
            "market_agent_ids": config.market_agent_ids or [],
            "strategy_agent_ids": getattr(config, "strategy_agent_ids", None) or [],
            "risk_agent_ids": getattr(config, "risk_agent_ids", None) or [],
            "finalizer_agent_id": getattr(config, "finalizer_agent_id", None)
        }
        
    def get_personas_dict(self) -> Dict[str, str]:
        personas = self.db.execute(select(SystemPersona).where(SystemPersona.is_active == True)).scalars().all()
        return {p.id: p.prompt_template for p in personas}

    def build_decision_context(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """
        构建单次决策上下文，包含专属配置
        这部分上下文将在工作流触发时传递给 WorkflowEngine
        """
        prompts = self.get_user_prompts(user_id)
        team_config = self.get_team_config(user_id)
        personas_dict = self.get_personas_dict()
        
        # 组装最终需要使用的 Prompt 列表
        # 对 TeamConfig 中用到的 Persona ID，把其模板和用户的 custom_prompts (如果有覆盖) 合并
        team_prompts = {}
        
        all_ids = list(team_config.get("market_agent_ids", [])) + list(team_config.get("strategy_agent_ids", []))
        for k in ["finalizer_agent_id"]:
            if team_config.get(k):
                all_ids.append(team_config[k])
        for rid in team_config.get("risk_agent_ids", []):
            if rid:
                all_ids.append(rid)
                
        for pid in all_ids:
            base_prompt = personas_dict.get(pid, f"You are a generic trading agent ({pid}).")
            override = prompts.get(pid)
            if override:
                team_prompts[pid] = f"{base_prompt}\n\n# User Specific Rules:\n{override}"
            else:
                team_prompts[pid] = base_prompt
        
        return {
            "user_id": str(user_id),
            "custom_prompts": prompts, # Legacy fallback
            "team_config": team_config,
            "team_prompts": team_prompts
        }