from typing import Literal, Union
from langgraph.graph import StateGraph, END, START
from src.agent.state import GameState
from src.agent.nodes.engine import game_master_node, action_handler_node
from src.agent.nodes.roles import player_agent_node
from src.utils.helpers import get_default_state

def init_node(state: GameState) -> GameState:
    """初始化节点：如果状态缺失，加载默认对局"""
    if not state or "players" not in state or not state["players"]:
        return get_default_state()
    return state

def routing_logic(state: GameState):
    """
    中控路由逻辑 (GM 的指挥棒)。
    决定从 GM 节点出来后，是去执行玩家决策、物理结算，还是结束游戏。
    """
    if state.get("game_over"):
        return END
        
    turn_type = state.get("turn_type")
    current_id = state.get("current_player_id")
    
    # 1. 如果 GM 已经点名了某个玩家 (current_player_id 不为空)，去玩家节点
    if current_id is not None:
        return "player_agent"
        
    # 2. 如果 GM 判定需要进行物理结算 (如夜晚结束或公告环节)，去行动处理器
    if turn_type in ["night_settle", "day_announcement"]:
        return "action_handler"
        
    # 3. 兜底逻辑：回到 GM 继续调度 (理论上 GM 节点会自动推进状态直到产生上述两种输出)
    return "game_master"

# 构建图
workflow = StateGraph(GameState)

# 添加核心三节点及初始化节点
workflow.add_node("init", init_node)
workflow.add_node("game_master", game_master_node)
workflow.add_node("player_agent", player_agent_node)
workflow.add_node("action_handler", action_handler_node)

# 设置入口
workflow.add_edge(START, "init")
workflow.add_edge("init", "game_master")

# 核心环形流转：所有节点执行完后必须回到 GM 报到
workflow.add_edge("player_agent", "game_master")
workflow.add_edge("action_handler", "game_master")

# GM 的环形指挥逻辑
workflow.add_conditional_edges(
    "game_master",
    routing_logic,
    {
        "player_agent": "player_agent",
        "action_handler": "action_handler",
        "game_master": "game_master", # 内部自循环探测有效环节
        END: END
    }
)

# 编译
graph = workflow.compile()
