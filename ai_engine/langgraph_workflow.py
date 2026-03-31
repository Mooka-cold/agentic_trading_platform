import asyncio
import operator
from typing import Annotated, Any, Dict, List, TypedDict, Union, Literal

from langgraph.graph import StateGraph, END, START
from model.state import AgentState, AnalystOutput, SentimentOutput, MacroOutput, OnChainOutput
from agents import Analyst, Reviewer, Reflector, SentimentAgent
from agents.bull_strategist import BullStrategist
from agents.bear_strategist import BearStrategist
from agents.portfolio_manager import PortfolioManager
from agents.macro import MacroAgent
from agents.onchain import OnChainAgent
from model.policies import OrchestrationConfig

def reduce_agent_state(left: AgentState | None, right: AgentState | None) -> AgentState:
    """合并 AgentState 的并行更新"""
    if left is None:
        return right
    if right is None:
        return left
        
    # 这是一个简单的合并策略，假设并行节点修改不同的字段
    # 注意：这修改了 left 对象（原地修改）
    
    if right.analyst_report:
        left.analyst_report = right.analyst_report
    if right.sentiment_report:
        left.sentiment_report = right.sentiment_report
    if right.macro_report:
        left.macro_report = right.macro_report
    if right.onchain_report:
        left.onchain_report = right.onchain_report
    if right.bull_proposal:
        left.bull_proposal = right.bull_proposal
    if right.bear_proposal:
        left.bear_proposal = right.bear_proposal
    if right.strategy_proposal:
        left.strategy_proposal = right.strategy_proposal
    if right.risk_verdict:
        left.risk_verdict = right.risk_verdict
    if right.review_feedback:
        left.review_feedback = right.review_feedback
    if right.debate_notes:
        left.debate_notes = right.debate_notes
    if right.execution_result:
        left.execution_result = right.execution_result
    if right.market_regime:
        left.market_regime = right.market_regime
    if right.microstructure:
        left.microstructure = right.microstructure
    if right.portfolio_context:
        left.portfolio_context = right.portfolio_context
    if right.execution_constraints:
        left.execution_constraints = right.execution_constraints
    if right.unresolved_todos:
        left.unresolved_todos = list({*(left.unresolved_todos or []), *right.unresolved_todos})
    
    # 简单的版本号/轮次同步
    if right.strategy_revision_round > left.strategy_revision_round:
        left.strategy_revision_round = right.strategy_revision_round
        
    return left

# 定义图状态
class GraphState(TypedDict):
    # 核心业务状态，使用 reduce_agent_state 处理并行写入
    agent_state: Annotated[AgentState, reduce_agent_state]
    # 并行任务完成计数（用于 Join）
    completed_analysis: Annotated[int, operator.add]
    # 全局元数据
    session_id: str
    symbol: str

# --- 节点定义 ---

async def analyst_node(state: GraphState):
    """分析师节点：执行技术面分析"""
    agent = Analyst()
    
    # 运行 Agent 逻辑
    updates = await agent.run(state["agent_state"])
    
    # 返回一个新的 AgentState 对象，仅包含更新的字段
    # 这对 reducer 很重要
    current_state = state["agent_state"]
    # 创建一个空的 state 对象作为 update payload
    # 注意：我们不能直接返回 dict，必须返回 AgentState 对象
    # 因为 reducer 的签名是 (AgentState, AgentState) -> AgentState
    
    # 为了避免全量复制带来的混淆，我们可以在 reducer 里只检查特定字段。
    # 这里我们返回原对象更新后的副本
    
    # 实际上，Analyst.run() 返回的是一个 dict
    if updates:
        for k, v in updates.items():
            setattr(current_state, k, v)
            
    return {"agent_state": current_state, "completed_analysis": 1}

async def sentiment_node(state: GraphState):
    """情绪分析节点：执行基本面/新闻分析"""
    agent = SentimentAgent()
    updates = await agent.run(state["agent_state"])
    
    current_state = state["agent_state"]
    if updates:
        for k, v in updates.items():
            setattr(current_state, k, v)
            
    return {"agent_state": current_state, "completed_analysis": 1}

async def macro_node(state: GraphState):
    """宏观分析节点：执行全球宏观与Risk Regime判断"""
    agent = MacroAgent()
    updates = await agent.run(state["agent_state"])
    
    current_state = state["agent_state"]
    if updates:
        for k, v in updates.items():
            setattr(current_state, k, v)
            
    return {"agent_state": current_state, "completed_analysis": 1}

async def onchain_node(state: GraphState):
    """链上分析节点：分析资金流向与持仓情绪"""
    agent = OnChainAgent()
    updates = await agent.run(state["agent_state"])
    
    current_state = state["agent_state"]
    if updates:
        for k, v in updates.items():
            setattr(current_state, k, v)
            
    return {"agent_state": current_state, "completed_analysis": 1}

async def bull_strategist_node(state: GraphState):
    """多头策略师节点"""
    agent = BullStrategist()
    updates = await agent.run(state["agent_state"])
    
    current_state = state["agent_state"]
    if updates:
        for k, v in updates.items():
            setattr(current_state, k, v)
            
    return {"agent_state": current_state}

async def bear_strategist_node(state: GraphState):
    """空头策略师节点"""
    agent = BearStrategist()
    updates = await agent.run(state["agent_state"])
    
    current_state = state["agent_state"]
    if updates:
        for k, v in updates.items():
            setattr(current_state, k, v)
            
    return {"agent_state": current_state}

async def cross_examiner_node(state: GraphState):
    """交叉质询节点：对多空提案进行轻量互审，生成PM裁决补充上下文"""
    current_state = state["agent_state"]
    bull = current_state.bull_proposal
    bear = current_state.bear_proposal
    if not bull or not bear:
        return {"agent_state": current_state}

    policy = (current_state.execution_constraints or {}).get("cross_examiner_policy", {}) or {}
    cts_floor = float(policy.get("cts_floor", 0.35) or 0.35)
    confidence_weight = float(policy.get("confidence_weight", 1.0) or 1.0)
    weakness_penalty = float(policy.get("weakness_penalty", 0.12) or 0.12)
    ruin_high_penalty = float(policy.get("ruin_high_penalty", 0.2) or 0.2)
    score_gap_hold_threshold = float(policy.get("score_gap_hold_threshold", 0.1) or 0.1)
    high_conflict_hold_bias = bool(policy.get("high_conflict_hold_bias", True))

    def _proposal_weakness(name: str, proposal) -> tuple[list[str], float]:
        issues = []
        penalty = 0.0
        try:
            cts = float(getattr(proposal, "counter_thesis_strength", 0.5) or 0.5)
            if cts < cts_floor:
                issues.append(f"{name}: counter_thesis_strength偏低({cts:.2f})")
                penalty += weakness_penalty
        except Exception:
            issues.append(f"{name}: counter_thesis_strength缺失或不可解析")
            penalty += weakness_penalty
        fc = list(getattr(proposal, "failure_conditions", []) or [])
        if len(fc) < 2:
            issues.append(f"{name}: failure_conditions不足(<2)")
            penalty += weakness_penalty
        dr = list(getattr(proposal, "decision_rationale_compact", []) or [])
        if len(dr) != 3:
            issues.append(f"{name}: decision_rationale_compact应为3条")
            penalty += weakness_penalty
        roh = str(getattr(proposal, "risk_of_ruin_hint", "medium") or "medium").lower()
        conf = float(getattr(proposal, "confidence", 0.0) or 0.0)
        if roh == "high" and conf >= 0.75:
            issues.append(f"{name}: 高置信但risk_of_ruin_hint=high")
            penalty += ruin_high_penalty
        return issues, penalty

    bull_action = str(getattr(bull, "action", "HOLD") or "HOLD").upper()
    bear_action = str(getattr(bear, "action", "HOLD") or "HOLD").upper()
    directional_conflict = (
        bull_action in {"LONG", "BUY"} and bear_action in {"SHORT"}
    ) or (
        bull_action in {"HOLD"} and bear_action in {"SHORT"}
    ) or (
        bull_action in {"LONG", "BUY"} and bear_action in {"HOLD"}
    )
    conflict_level = "high" if directional_conflict else "medium"
    if bull_action == "HOLD" and bear_action == "HOLD":
        conflict_level = "low"
    bull_issues, bull_penalty = _proposal_weakness("bull", bull)
    bear_issues, bear_penalty = _proposal_weakness("bear", bear)
    bull_conf = float(getattr(bull, "confidence", 0.0) or 0.0)
    bear_conf = float(getattr(bear, "confidence", 0.0) or 0.0)
    bull_score = max(0.0, confidence_weight * bull_conf - bull_penalty)
    bear_score = max(0.0, confidence_weight * bear_conf - bear_penalty)
    score_gap = abs(bull_score - bear_score)
    if bull_score > bear_score:
        recommended_preference = "bull"
    elif bear_score > bull_score:
        recommended_preference = "bear"
    else:
        recommended_preference = "hold"
    hold_bias = bool(
        (conflict_level == "high" and high_conflict_hold_bias and score_gap <= score_gap_hold_threshold)
        or (recommended_preference == "hold")
    )
    notes = {
        "conflict_level": conflict_level,
        "bull_action": bull_action,
        "bear_action": bear_action,
        "bull_weaknesses": bull_issues,
        "bear_weaknesses": bear_issues,
        "bull_score": round(bull_score, 4),
        "bear_score": round(bear_score, 4),
        "score_gap": round(score_gap, 4),
        "recommended_preference": "hold" if hold_bias else recommended_preference,
        "hold_bias": hold_bias,
        "policy": {
            "cts_floor": cts_floor,
            "confidence_weight": confidence_weight,
            "weakness_penalty": weakness_penalty,
            "ruin_high_penalty": ruin_high_penalty,
            "score_gap_hold_threshold": score_gap_hold_threshold,
            "high_conflict_hold_bias": high_conflict_hold_bias,
        },
        "suggestion": "prefer_hold_on_high_conflict" if hold_bias else "normal_arbitration",
    }
    current_state.debate_notes = notes
    return {"agent_state": current_state}

async def portfolio_manager_node(state: GraphState):
    """基金经理裁判节点"""
    agent = PortfolioManager()
    updates = await agent.run(state["agent_state"])
    
    current_state = state["agent_state"]
    if updates:
        for k, v in updates.items():
            setattr(current_state, k, v)
            
    return {"agent_state": current_state}

async def reviewer_node(state: GraphState):
    """风控节点：审查策略方案"""
    agent = Reviewer()
    updates = await agent.run(state["agent_state"])
    
    current_state = state["agent_state"]
    if updates:
        for k, v in updates.items():
            setattr(current_state, k, v)
            
    return {"agent_state": current_state}

from redis import Redis
from core.config import settings

async def reflector_node(state: GraphState):
    """反思节点：记录并学习本次决策过程"""
    # Initialize Redis client here as it's needed for Reflector
    # In a real production environment, we should inject this or use a singleton service
    # For now, create a new connection or reuse a global one if available
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        agent = Reflector(redis_client)
        # Reflector 通常不返回更新，而是执行副作用（写 DB/日志）
        await agent.run(state["agent_state"])
    finally:
        # Close connection to avoid leaks?
        # Standard redis-py client manages connection pool, so closing might not be strictly necessary per request
        # But good practice if we create it here.
        redis_client.close()
        
    return {"agent_state": state["agent_state"]}

# --- 条件边逻辑 ---

def check_strategist_feedback(state: GraphState) -> Literal["analyst", "reviewer"]:
    """
    检查策略师是否请求更多信息
    """
    agent_state = state["agent_state"]
    
    # 策略师请求了反馈，且我们还没有收到反馈（或者这是一个新的请求）
    # 但由于 Analyst 会在处理后清除 feedback (返回 None)，
    # 所以如果这里 feedback 存在，说明是 Strategist 刚刚提出的。
    if agent_state.analyst_feedback:
        return "analyst"
        
    return "reviewer"

def should_continue_negotiation(state: GraphState) -> Literal["revise", "reflect", "end"]:
    """判断是否需要继续策略修订循环"""
    agent_state = state["agent_state"]
    verdict = agent_state.risk_verdict
    proposal = agent_state.strategy_proposal

    # 1. 如果没有 Proposal (例如 Analyst 失败)，直接结束
    if not proposal:
        return "reflect"

    # 2. 如果是 HOLD 或 已通过，进入反思并结束
    if proposal.action == "HOLD":
        return "reflect"
        
    if verdict and verdict.approved:
        return "reflect"
    
    constraints = agent_state.execution_constraints or {}
    max_revision_rounds = 2
    try:
        max_revision_rounds = max(0, int(constraints.get("max_revision_rounds", 2)))
    except Exception:
        max_revision_rounds = 2
    if agent_state.strategy_revision_round < max_revision_rounds:
        # 增加修订计数
        agent_state.strategy_revision_round += 1
        
        # 重新辩论：打回给两位策略师
        return "revise"
    
    # 4. 超过重试次数，直接反思结束
    return "reflect"

def check_analysis_completion(state: GraphState) -> Literal["strategist", "wait"]:
    """
    检查并行分析是否全部完成。
    """
    return "strategist"

# --- 图构建 ---

def _normalize_orchestration_config(orchestration_config: Dict[str, Any] | None) -> OrchestrationConfig:
    if isinstance(orchestration_config, dict):
        return OrchestrationConfig(**orchestration_config)
    return OrchestrationConfig()


def create_trading_workflow(orchestration_config: Dict[str, Any] | None = None):
    cfg = _normalize_orchestration_config(orchestration_config)
    enabled_analysis_nodes = [n for n in cfg.enabled_analysis_nodes if n in {"analyst", "sentiment", "macro", "onchain"}]
    if not enabled_analysis_nodes:
        enabled_analysis_nodes = ["analyst"]
    # 初始化图
    workflow = StateGraph(GraphState)

    # 添加节点
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("sentiment", sentiment_node)
    workflow.add_node("macro", macro_node)
    workflow.add_node("onchain", onchain_node)
    
    workflow.add_node("bull_strategist", bull_strategist_node)
    workflow.add_node("bear_strategist", bear_strategist_node)
    workflow.add_node("cross_examiner", cross_examiner_node)
    workflow.add_node("portfolio_manager", portfolio_manager_node)
    
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("reflector", reflector_node)

    # 构建结构
    for node in enabled_analysis_nodes:
        workflow.add_edge(START, node)

    for node in enabled_analysis_nodes:
        workflow.add_edge(node, "bull_strategist")
        workflow.add_edge(node, "bear_strategist")

    # 3. 策略辩论汇聚到基金经理
    if cfg.enable_cross_examiner:
        workflow.add_edge("bull_strategist", "cross_examiner")
        workflow.add_edge("bear_strategist", "cross_examiner")
        workflow.add_edge("cross_examiner", "portfolio_manager")
    else:
        workflow.add_edge("bull_strategist", "portfolio_manager")
        workflow.add_edge("bear_strategist", "portfolio_manager")
    
    # 4. 基金经理裁决后交给风控
    workflow.add_edge("portfolio_manager", "reviewer")

    # 5. 风控条件分支（循环）
    workflow.add_conditional_edges(
        "reviewer",
        should_continue_negotiation,
        {
            "revise": "portfolio_manager", # 如果只是简单参数问题，PM 直接修改，或者也可以退回给策略师
            "reflect": "reflector", # 通过或最终拒绝，进入反思
            "end": "reflector"      # 异常情况
        }
    )

    # 6. 反思后结束
    workflow.add_edge("reflector", END)

    return workflow.compile()

if __name__ == "__main__":
    from model.state import MarketData
    from services.market_data import market_data_service
    from dotenv import load_dotenv
    import os
    
    # Load .env manually for local test
    # Assuming run from ai_engine directory, .env is in ../.env or current
    # Try current first, then parent
    if os.path.exists(".env"):
        load_dotenv(".env")
    elif os.path.exists("../.env"):
        load_dotenv("../.env")
    
    async def main():
        print("Starting LangGraph Workflow Test...")
        app = create_trading_workflow()
        
        # Mock Initial State
        symbol = "BTC/USDT"
        session_id = "test-graph-session-1"
        
        # Mock Market Data (Avoid calling real API if possible, or use real one)
        # For test, we fetch real snapshot if possible, or mock it.
        try:
            snapshot = market_data_service.get_full_snapshot(symbol)
            price = snapshot.get("price", 65000.0)
        except:
            price = 65000.0
            snapshot = {"price": price, "volume": 1000, "indicators": {}}

        state = AgentState(
            session_id=session_id,
            market_data=MarketData(
                symbol=symbol, 
                timeframe="1m", 
                price=price, 
                volume=snapshot.get("volume", 0), 
                indicators=snapshot.get("indicators", {})
            ),
            account_balance=10000.0,
            positions=[]
        )
        
        inputs = {
            "agent_state": state,
            "session_id": session_id,
            "symbol": symbol,
            "completed_analysis": 0
        }
        
        config = {"configurable": {"thread_id": session_id}}
        
        print(f"Graph Structure: {app.get_graph().nodes.keys()}")
        
        try:
            async for event in app.astream(inputs, config):
                for node_name, output in event.items():
                    print(f"--- Finished Node: {node_name} ---")
                    # print(f"Output keys: {output.keys()}")
        except Exception as e:
            print(f"Graph Execution Error: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(main())
