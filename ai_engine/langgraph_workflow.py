import asyncio
import operator
from typing import Annotated, Any, Dict, List, TypedDict, Union, Literal

from langgraph.graph import StateGraph, END, START
from model.state import AgentState
from agents.generic import GenericMarketAgent, GenericDecisionAgent, GenericArbitratorAgent, GenericRiskAgent
from agents import Reflector
from model.policies import OrchestrationConfig
import asyncio

def reduce_agent_state(left: AgentState | None, right: AgentState | None) -> AgentState:
    """合并 AgentState 的并行更新"""
    if left is None:
        return right
    if right is None:
        return left
        
    # 这是一个简单的合并策略，假设并行节点修改不同的字段
    # 注意：这修改了 left 对象（原地修改）
    
    if right.market_reports:
        left.market_reports.update(right.market_reports)
    if right.decision_proposals:
        left.decision_proposals.update(right.decision_proposals)
        
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

    # 辩论 thread：合并所有 turn，按 (round, agent_id) 去重保留最后一条
    if right.debate_thread:
        merged = {(t.round, t.agent_id): t for t in (left.debate_thread or [])}
        for t in right.debate_thread:
            merged[(t.round, t.agent_id)] = t
        left.debate_thread = [merged[k] for k in sorted(merged.keys())]

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

async def news_stage_node(state: GraphState):
    """
    新闻上下文节点：加载 LLM 压缩后的新闻摘要，注入 state.news_digest。

    这是新闻→压缩→决策链路的最后一环。sentiment_news_interpreter 已把每条原始
    新闻（100-300 token）压缩为高密度中文摘要（30-60 token），这里只负责把
    已压缩的结果加载进 state，让 Market/Decision Agent 通过 extra_preamble 消费。

    设计要点：
    - 不做二次 LLM 调用（零额外 token 成本），纯 DB 读取。
    - 不按 symbol 硬过滤（filter_by_symbol=False），宏观/监管类新闻对策略
      辩论同样有价值；asset_mentions 已在压缩阶段提取，下游可自行判断相关性。
    - 失败时降级为空列表，不阻塞主流程（新闻是增强信号，不是硬依赖）。
    """
    agent_state = state["agent_state"]
    try:
        from services.sentiment import sentiment_service
        symbol = state.get("symbol") or agent_state.market_data.symbol
        # 拉取最近 24h 已压缩的新闻，上限 10 条（约 400-600 token，成本可控）
        items = sentiment_service.load_interpreted_news(
            target_symbol=symbol,
            limit=10,
            lookback_hours=24,
            filter_by_symbol=False,
        )
        # 只保留下游需要的轻量字段，剔除原始 summary 等大字段，进一步控制 token
        digest = []
        for it in items:
            digest.append({
                "source": it.get("source"),
                "title": it.get("title"),
                "summary_cn": it.get("summary_cn"),
                "asset_mentions": it.get("assets") or it.get("asset_mentions") or [],
                "is_noise": bool(it.get("noise_flags")),
                "published_at": str(it.get("published_at") or ""),
            })
        agent_state.news_digest = digest
        print(f"[Graph] News stage: loaded {len(digest)} compressed news items for {symbol}.", flush=True)
    except Exception as e:
        # 新闻加载失败不应阻塞交易决策主流程
        agent_state.news_digest = []
        print(f"[Graph] News stage degraded (empty digest): {e}", flush=True)
    return {"agent_state": agent_state}


async def market_stage_node(state: GraphState):
    """行情阶段节点：并行运行所有行情Agent"""
    agent_state = state["agent_state"]
    team_config = agent_state.team_config or {}
    agent_ids = team_config.get("market_agent_ids", [])
    
    if not agent_ids:
        # 新系统要求：用户必须显式在 Agent Studio 配置交易团队。
        # 旧系统遗留的 default_analyst 兜底已被移除，未配置团队的用户应保持空转。
        print(f"[Graph] Market stage skipped: no market_agent_ids configured for user.", flush=True)
        return {"agent_state": state["agent_state"], "completed_analysis": 0}
        
    agents = [GenericMarketAgent(aid) for aid in agent_ids]
    
    # 并行执行所有行情Agent
    results = await asyncio.gather(*(agent.run(agent_state) for agent in agents), return_exceptions=True)
    
    current_state = state["agent_state"]
    for res in results:
        if isinstance(res, dict) and "market_reports" in res:
            current_state.market_reports.update(res["market_reports"])
        elif isinstance(res, Exception):
            print(f"Error in market agent: {res}")
            
    # Make sure to close Redis connections
    for agent in agents:
        await agent.close()
            
    return {"agent_state": current_state, "completed_analysis": len(agent_ids)}

async def decision_stage_node(state: GraphState):
    """
    策略大师阶段节点：多轮辩论机制 (异人格观点碰撞)

    Round 1: 所有策略 Agent 在同一份原始数据上独立形成 thesis。
    Round 2: 每个策略 Agent 读到他人的 thesis，产出 rebuttal 与可能的动作调整。
    Finalizer 在 arbitration 阶段读取完整 debate_thread。
    """
    agent_state = state["agent_state"]
    team_config = agent_state.team_config or {}
    agent_ids = team_config.get("strategy_agent_ids", [])

    if not agent_ids:
        # 新系统要求：策略大师需要显式配置；旧 decision_agent_ids 字段已重命名。
        print(f"[Graph] Strategy stage skipped: no strategy_agent_ids configured for user.", flush=True)
        return {"agent_state": state["agent_state"]}

    # Number of debate rounds — start with 2 (independent + rebuttal) for v1.
    # Could be made configurable per user later.
    total_rounds = 2

    current_state = state["agent_state"]
    agents = [GenericDecisionAgent(aid) for aid in agent_ids]

    for round_index in range(1, total_rounds + 1):
        prior_turns = list(current_state.debate_thread)
        results = await asyncio.gather(
            *(agent.run_debate_round(current_state, round_index, prior_turns) for agent in agents),
            return_exceptions=True,
        )

        for res in results:
            if isinstance(res, dict) and "debate_turn" in res:
                turn = res["debate_turn"]
                current_state.debate_thread.append(turn)
                # Keep decision_proposals in sync with the LATEST turn of each persona
                # so the Arbitrator (and downstream Risk Officer) can read what each
                # persona currently believes after all rebuttal rounds.
                latest = current_state.decision_proposals.get(turn.agent_id)
                if latest is None or turn.confidence >= 0:
                    # Convert the DebateTurn into a StrategyProposal-shaped object
                    # so existing serialization paths keep working.
                    from model.state import StrategyProposal
                    current_state.decision_proposals[turn.agent_id] = StrategyProposal(
                        action=turn.action,
                        order_type="MARKET",
                        reasoning=turn.thesis + (" | Rebuttals: " + " | ".join(turn.rebuttals) if turn.rebuttals else ""),
                        confidence=turn.confidence,
                        assumptions=[],
                        decision_rationale_compact=[turn.thesis] + turn.rebuttals,
                        failure_conditions=[],
                    )
            elif isinstance(res, Exception):
                print(f"Error in strategy agent (round {round_index}): {res}", flush=True)

    for agent in agents:
        await agent.close()

    return {"agent_state": current_state}

async def arbitration_stage_node(state: GraphState):
    """终极拍板阶段节点"""
    agent_state = state["agent_state"]
    team_config = agent_state.team_config or {}
    agent_id = team_config.get("finalizer_agent_id")

    if not agent_id:
        # 新系统要求：必须显式指定终极拍板人。旧 arbitrator_agent_id 字段已重命名。
        print(f"[Graph] Finalizer stage skipped: no finalizer_agent_id configured for user.", flush=True)
        return {"agent_state": state["agent_state"]}

    agent = GenericArbitratorAgent(agent_id)
    updates = await agent.run(agent_state)

    current_state = state["agent_state"]
    if updates and "strategy_proposal" in updates:
        current_state.strategy_proposal = updates["strategy_proposal"]

    await agent.close()
    return {"agent_state": current_state}

async def risk_stage_node(state: GraphState):
    """风控阶段节点：多风控官共识"""
    agent_state = state["agent_state"]
    team_config = agent_state.team_config or {}
    agent_ids = team_config.get("risk_agent_ids", [])

    if not agent_ids:
        # 新系统要求：必须显式配置至少 1 个风控官（推荐 ≥2 形成多签共识）。旧 risk_agent_id 字段已重命名。
        print(f"[Graph] Risk stage skipped: no risk_agent_ids configured for user.", flush=True)
        return {"agent_state": state["agent_state"]}

    if len(agent_ids) < 2:
        print(f"[Graph] Risk stage warning: only {len(agent_ids)} risk agent configured. Recommend ≥2 for multi-signature consensus.", flush=True)

    # 多风控官独立判断，结果合并到 risk_verdict
    current_state = state["agent_state"]
    agents = [GenericRiskAgent(aid) for aid in agent_ids]
    results = await asyncio.gather(*(agent.run(agent_state) for agent in agents), return_exceptions=True)

    for res in results:
        if isinstance(res, dict) and "risk_verdict" in res:
            current_state.risk_verdict = res["risk_verdict"]
        elif isinstance(res, Exception):
            print(f"Error in risk agent: {res}")

    for agent in agents:
        await agent.close()
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

# --- 图构建 ---

def _normalize_orchestration_config(orchestration_config: Dict[str, Any] | None) -> OrchestrationConfig:
    if isinstance(orchestration_config, dict):
        return OrchestrationConfig(**orchestration_config)
    return OrchestrationConfig()


def create_trading_workflow(orchestration_config: Dict[str, Any] | None = None):
    cfg = _normalize_orchestration_config(orchestration_config)
    
    # 初始化图
    workflow = StateGraph(GraphState)

    # 添加节点
    workflow.add_node("news_stage", news_stage_node)
    workflow.add_node("market_stage", market_stage_node)
    workflow.add_node("decision_stage", decision_stage_node)
    workflow.add_node("arbitration_stage", arbitration_stage_node)
    workflow.add_node("risk_stage", risk_stage_node)
    workflow.add_node("reflector", reflector_node)

    # 构建结构：先加载压缩新闻，再做行情/决策分析，使下游 Agent 拿到新闻上下文
    workflow.add_edge(START, "news_stage")
    workflow.add_edge("news_stage", "market_stage")
    workflow.add_edge("market_stage", "decision_stage")
    workflow.add_edge("decision_stage", "arbitration_stage")
    workflow.add_edge("arbitration_stage", "risk_stage")

    # 风控条件分支（循环）
    workflow.add_conditional_edges(
        "risk_stage",
        should_continue_negotiation,
        {
            "revise": "arbitration_stage", # 退回重新拍板或重新决策？先退回拍板
            "reflect": "reflector", # 通过或最终拒绝，进入反思
            "end": "reflector"      # 异常情况
        }
    )

    # 反思后结束
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
