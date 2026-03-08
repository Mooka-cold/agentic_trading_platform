import asyncio
import operator
from typing import Annotated, Any, Dict, List, TypedDict, Union, Literal

from langgraph.graph import StateGraph, END, START
from model.state import AgentState
from agents.core import Analyst, Strategist, Reviewer, Reflector, SentimentAgent

# 定义图状态
class GraphState(TypedDict):
    # 核心业务状态
    agent_state: AgentState
    # 并行任务完成计数（用于 Join）
    completed_analysis: Annotated[int, operator.add]
    # 全局元数据
    session_id: str
    symbol: str

# --- 节点定义 ---

async def analyst_node(state: GraphState):
    """分析师节点：执行技术面分析"""
    # 重新实例化 Agent 以避免状态残留，或者使用单例池
    # 这里直接实例化，因为 Agent 本身是无状态的 (State 通过参数传递)
    agent = Analyst()
    
    # 运行 Agent 逻辑
    # 注意：Agent.run() 通常返回一个 dict 用于更新 State
    # 我们需要确保 agent_state 对象被正确更新
    updates = await agent.run(state["agent_state"])
    
    # 将更新应用到 agent_state 对象
    # 注意：LangGraph 的 State 是不可变的，通常建议返回新的 State
    # 但由于 AgentState 是 Pydantic 对象，我们可以修改它，或者返回新的对象
    # 这里我们修改对象属性
    current_agent_state = state["agent_state"]
    if updates:
        for k, v in updates.items():
            setattr(current_agent_state, k, v)
            
    return {"agent_state": current_agent_state, "completed_analysis": 1}

async def sentiment_node(state: GraphState):
    """情绪分析节点：执行基本面/新闻分析"""
    agent = SentimentAgent()
    updates = await agent.run(state["agent_state"])
    
    current_agent_state = state["agent_state"]
    if updates:
        for k, v in updates.items():
            setattr(current_agent_state, k, v)
            
    return {"agent_state": current_agent_state, "completed_analysis": 1}

async def strategist_node(state: GraphState):
    """策略师节点：根据分析结果生成交易方案"""
    agent = Strategist()
    updates = await agent.run(state["agent_state"])
    
    current_agent_state = state["agent_state"]
    if updates:
        for k, v in updates.items():
            setattr(current_agent_state, k, v)
            
    return {"agent_state": current_agent_state}

async def reviewer_node(state: GraphState):
    """风控节点：审查策略方案"""
    agent = Reviewer()
    updates = await agent.run(state["agent_state"])
    
    current_agent_state = state["agent_state"]
    if updates:
        for k, v in updates.items():
            setattr(current_agent_state, k, v)
            
    return {"agent_state": current_agent_state}

async def reflector_node(state: GraphState):
    """反思节点：记录并学习本次决策过程"""
    agent = Reflector()
    # Reflector 通常不返回更新，而是执行副作用（写 DB/日志）
    await agent.run(state["agent_state"])
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
    workflow.add_node("strategist", strategist_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("reflector", reflector_node)

    # 构建结构
    # 1. 并行启动分析
    workflow.add_edge(START, "analyst")
    workflow.add_edge(START, "sentiment")

    # 2. 汇聚到策略师 (Wait for both)
    # LangGraph 会自动等待所有指向 strategist 的节点完成
    workflow.add_edge("analyst", "strategist")
    workflow.add_edge("sentiment", "strategist")

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
