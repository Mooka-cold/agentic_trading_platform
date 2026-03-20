import asyncio
import operator
from typing import Annotated, Any, Dict, List, TypedDict, Union, Literal

from langgraph.graph import StateGraph, END, START
from model.state import AgentState, AnalystOutput, SentimentOutput, MacroOutput, OnChainOutput
from agents import Analyst, Strategist, Reviewer, Reflector, SentimentAgent
from agents.macro import MacroAgent
from agents.onchain import OnChainAgent

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
    if right.strategy_proposal:
        left.strategy_proposal = right.strategy_proposal
    if right.risk_verdict:
        left.risk_verdict = right.risk_verdict
    if right.review_feedback:
        left.review_feedback = right.review_feedback
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

async def strategist_node(state: GraphState):
    """策略师节点：根据分析结果生成交易方案"""
    agent = Strategist()
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
    
    # 3. 如果被拒绝且未超过修订次数，返回策略师
    # 这里的 2 是最大重试次数
    if agent_state.strategy_revision_round < 2:
        # 增加修订计数
        agent_state.strategy_revision_round += 1
        
        # 设置反馈信息 (模拟 Reviewer 的反馈逻辑)
        # 注意：Reviewer Agent 已经在 run() 中设置了 review_feedback，这里只需确认
        # 如果 Reviewer 没有设置 feedback，我们手动补全？
        # Reviewer.run() 应该处理这个逻辑。
        
        return "revise"
    
    # 4. 超过重试次数，直接反思结束
    return "reflect"

def check_analysis_completion(state: GraphState) -> Literal["strategist", "wait"]:
    """
    检查并行分析是否全部完成。
    LangGraph 的 Parallel 机制通常会自动等待所有分支完成再汇聚，
    但如果我们使用自定义的汇聚逻辑，可以用这个函数。
    目前 LangGraph 默认行为是等待所有入边，所以这个函数可能不需要，
    直接在图定义中连接即可。
    """
    return "strategist"

# --- 图构建 ---

def create_trading_workflow():
    # 初始化图
    workflow = StateGraph(GraphState)

    # 添加节点
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("sentiment", sentiment_node)
    workflow.add_node("macro", macro_node)
    workflow.add_node("onchain", onchain_node)
    workflow.add_node("strategist", strategist_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("reflector", reflector_node)

    # 构建结构
    # 1. 并行启动分析
    workflow.add_edge(START, "analyst")
    workflow.add_edge(START, "sentiment")
    workflow.add_edge(START, "macro")
    workflow.add_edge(START, "onchain")

    # 2. 汇聚到策略师 (Wait for all)
    # LangGraph 会自动等待所有指向 strategist 的节点完成
    workflow.add_edge("analyst", "strategist")
    workflow.add_edge("sentiment", "strategist")
    workflow.add_edge("macro", "strategist")
    workflow.add_edge("onchain", "strategist")

    # 3. 策略到风控
    workflow.add_edge("strategist", "reviewer")

    # 4. 风控条件分支（循环）
    workflow.add_conditional_edges(
        "reviewer",
        should_continue_negotiation,
        {
            "revise": "strategist", # 回到策略师重写
            "reflect": "reflector", # 通过或最终拒绝，进入反思
            "end": "reflector"      # 异常情况
        }
    )

    # 5. 反思后结束
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
