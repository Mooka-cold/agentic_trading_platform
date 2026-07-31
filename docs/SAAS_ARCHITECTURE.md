# 中心化 SaaS 版本架构设计

## 一、 整体系统架构图 (Architecture Diagram)

该架构图展示了系统各模块的层级关系以及中心化改造后引入的新组件（如 Trigger Engine 和多租户上下文）。

```mermaid
graph TD
    subgraph ClientLayer [用户与控制层 Client Layer]
        UI[Web 前端面板]
        AS[Agent Studio <br> 专属提示词配置]
        AB[Automation Builder <br> 自动化触发规则配置]
    end

    subgraph APISession [API 与上下文管理层 API & Context]
        API[FastAPI 网关]
        SM[上下文与状态管理器 State & Session Manager <br> 用户隔离/运行时状态/决策上下文]
    end

    subgraph TriggerRouting [信号与触发层 Trigger Layer]
        direction LR
        CS[定时调度器 <br> Cron]
        MR[行情/指标匹配器]
        NR[新闻/情绪匹配器]
    end

    subgraph AgentRuntime [智能体运行环境 Agent Runtime]
        WE[工作流编排器 <br> 动态实例化任务]
        PE[Prompt 引擎 <br> 注入用户专属提示词]
        LG[LangGraph 运行实例 <br> 执行短周期决策工作流]
        WE --> PE
        PE --> LG
    end

    subgraph LLMGateway [无状态 LLM 网关 LLM Gateway]
        LLM_GW[LLM 同步网关 <br> 纯代理/计费/限流/路由]
    end

    subgraph ExecutionRisk [执行与风控层 Execution & Risk]
        RK[风控内核 <br> 资金与纪律硬约束]
        ES[交易执行服务]
    end

    subgraph Infrastructure [基础设施与数据层 Infrastructure]
        UDB[(用户数据库 <br> 租户/提示词/规则)]
        MDB[(行情数据库 <br> TimescaleDB)]
        REDIS[(Redis <br> 信号总线)]
        EXC((交易所/券商))
        LLM((大语言模型 <br> OpenAI/DeepSeek))
    end

    %% 连接关系
    UI --> API
    AS --> API
    AB --> API
    
    API --> SM
    SM --> UDB

    %% 触发逻辑
    REDIS --> MR
    REDIS --> NR
    CS -- 触发信号 --> SM
    MR -- 触发信号 --> SM
    NR -- 触发信号 --> SM
    
    %% 会话管理与 Agent Runtime
    SM -- 构建并传递完整决策上下文 <br> (Session/State/Rules) --> WE
    
    %% Agent 与无状态网关
    LG -- 发送无状态推断请求 --> LLM_GW
    LLM_GW --> LLM
    LLM_GW -- 返回推断结果 --> LG
    
    %% 状态回写
    LG -- 更新决策状态 --> SM

    LG --> RK
    RK --> ES
    ES <--> EXC
```

---

## 二、 核心数据流程图 (Data Flow Diagram)

该数据流图详细描述了从信号产生、匹配用户规则，到 AI 团队动态加载提示词并最终执行交易的完整闭环。

```mermaid
sequenceDiagram
    autonumber
    actor User as 用户
    participant Frontend as 前端 (Web UI)
    participant SM as 状态与会话管理器 (State/Session Mgr)
    participant DB as 用户数据库 (DB)
    participant Trigger as 信号与触发层 (Cron/Market/News)
    participant Agents as 智能体运行环境 (Agent Runtime)
    participant LLMGW as 无状态 LLM 网关
    participant Risk as 风控内核 (Risk Kernel)

    %% 阶段 1：用户隔离与规则配置
    rect rgb(240, 248, 255)
    Note over User, DB: 阶段 1: 用户隔离与配置
    User->>Frontend: 配置 Agent 提示词与触发规则
    Frontend->>SM: 提交用户配置 (含 User Session)
    SM->>DB: 持久化隔离配置 (`user_prompts`, `user_rules`)
    end

    %% 阶段 2：信号触发与上下文构建
    rect rgb(255, 250, 240)
    Note over Trigger, Agents: 阶段 2: 信号触发与状态托管
    Trigger-->>SM: 捕获市场信号 (例如: RSI < 30 或 定时到达)
    SM->>DB: 提取命中该信号的用户隔离上下文 (Session, State, Rules)
    SM->>SM: 构建单次决策上下文 (Decision Context)
    SM->>Agents: 唤醒 Agent Runtime 执行短任务 (注入 Context)
    end

    %% 阶段 3：无状态 LLM 推断与状态回写
    rect rgb(245, 255, 250)
    Note over Agents, Risk: 阶段 3: 短周期推断与无状态网关交互
    Agents->>LLMGW: 某个节点发起推断请求 (纯 Prompt 载荷, 无状态)
    LLMGW->>LLMGW: 计费、限流与模型路由
    LLMGW-->>Agents: 返回推断结果
    Agents->>SM: 回写中间状态 (更新 State Mgr 中的会话进度)
    
    Agents->>LLMGW: 下一个节点发起推断请求 (无状态)
    LLMGW-->>Agents: 返回推断结果
    Agents->>SM: 回写中间状态
    
    Agents-->>SM: 工作流结束，产出最终策略提案
    
    SM->>Risk: 携带用户资金状态提交风控校验
    Risk-->>SM: 批准 / 驳回
    end
```