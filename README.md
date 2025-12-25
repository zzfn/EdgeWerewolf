# LangGraph 狼人杀（AI 自跑）

本项目使用 [LangGraph](https://github.com/langchain-ai/langgraph) 实现「经典 12 人狼人杀」的纯 AI 自跑对局。目标是用图结构驱动游戏流程，并可在 LangGraph Studio 中可视化与调试。

## 经典局配置

- 总人数：12
- 阵营与角色：
  - 狼人阵营：4 狼人
  - 村民阵营：4 村民、1 预言家、1 女巫、1 猎人、1 守卫

## 核心目标

- 用 LangGraph 构建完整的夜晚/白天流程
- 多 Agent 协作决策（每个玩家一个 Agent）
- 自动结算与胜负判定
- 可视化调试与对局复盘

## 技术亮点

### 1. 双重状态系统 (Public vs Private State)

- **公共记忆**：场上所有人的发言历史
- **私有推理**：狼人知道队友身份，预言家知道验人结果
- **实现方式**：在 State 中区分 `shared_history` 和每个玩家的 `private_thoughts`

### 2. 条件跳转 (Conditional Edges)

- 女巫救人 → 平安夜流程
- 投票平票 → PK 发言阶段
- 使用 `add_conditional_edges` 控制游戏走向

### 3. 多 Agent 编排

- **并发与顺序**：多个 Agent 依次发言，保持上下文连贯
- **权限控制**：不同角色的数据隔离（狼人看不到预言家的私有状态）
- **非线性逻辑**：技能打断、死后遗言等复杂流程处理

## 玩法流程（简化）

1. 夜晚阶段
   - 狼人共同选择击杀目标
   - 预言家查验一名玩家身份
   - 女巫选择救人/毒人（各一次）
   - 守卫选择守护目标（常规限制可选）
2. 白天阶段
   - 公布夜晚死亡
   - 依次发言
   - 投票出局
3. 胜负判断
   - 狼人阵营人数 ≥ 村民阵营人数：狼人胜
   - 狼人全部出局：村民胜

## 代码入口

- `src/agent/graph.py`：LangGraph 主流程与状态机

## 开发与运行

安装依赖（需要 LangGraph CLI）：

```bash
pip install -e . "langgraph-cli[inmem]"
```

运行开发服务器：

```bash
langgraph dev
```

## 后续可扩展方向

- 发言生成与投票理由（LLM 驱动）
- 角色记忆与推理（LangChain Memory/Store）
- 狼人私聊与协作策略
- 对局日志/回放与胜率统计

## Agent 实现指南

### 核心架构

每个 Agent = **LLM 大脑 + 记忆状态 + 角色规则**

```python
from pydantic import BaseModel, Field

class AgentOutput(BaseModel):
    thought: str = Field(description="内心的真实逻辑推理，不公开")
    speech: str = Field(description="对场上其他玩家说的话")
    action: str = Field(description="具体的游戏操作，如：投票给某人或杀死某人")
```

### 角色 Agent 示例

#### 狼人 Agent

- **核心逻辑**：伪装、煽动、寻找神职
- **私有信息**：知道队友，知道谁是好人

```python
def werewolf_node(state: GameState):
    prompt = f"""
    你是狼人{state['current_player_id']}。
    场上存活：{state['alive_players']}
    你的队友：{state['werewolf_teams']}
    公共发言历史：{state['history']}

    请输出你的策略：
    - 如果你想跳预言家，请编造合理的验人信息。
    - 如果你想深水倒钩，请表现得像个平民。
    """
    response = llm.with_structured_output(AgentOutput).invoke(prompt)
    return {"history": [{"role": "wolf", "content": response.speech}],
            "last_thought": response.thought}
```

#### 预言家 Agent

- **核心逻辑**：存活、获取信任、传递关键信息
- **私有信息**：历史验人的结果（金水/查杀）

#### 平民 Agent

- **核心逻辑**：逻辑推理、辨别真假预言家
- **私有信息**：无（全靠逻辑）

### 多 Agent 编排

```python
from langgraph.graph import StateGraph

builder = StateGraph(GameState)

# 添加不同的玩家节点
builder.add_node("player_1_wolf", werewolf_node)
builder.add_node("player_2_seer", seer_node)
builder.add_node("player_3_villager", villager_node)

# 定义流程控制：发言顺序
def speaker_router(state: GameState):
    curr = state['order'][state['turn_index']]
    return f"player_{curr['id']}_{curr['role']}"

builder.add_conditional_edges("game_manager", speaker_router)
```

### 进阶优化方向

1.  **推理节点**：在发言前整理场上所有人的发言，构建逻辑链矩阵
2.  **模拟节点**：狼人 Agent 模拟"如果我跳预言家，可能会被谁质疑？"
3.  **状态持久化**：利用 LangGraph 的 `checkpointer` 实现游戏中断续玩
4.  **记忆系统**：存储每个玩家对其他人的"好感度/怀疑度"矩阵
