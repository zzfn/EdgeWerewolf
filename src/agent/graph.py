from typing import Literal, Union
from langgraph.graph import StateGraph, END, START
from src.agent.state import GameState
from src.agent.nodes.engine import settle_night, check_winner, next_turn
from src.agent.nodes.roles import player_node
from src.utils.helpers import get_default_state

def init_node(state: GameState) -> GameState:
    """如果状态缺失关键信息，则进行初始化"""
    if not state or "players" not in state or not state["players"]:
        return get_default_state()
    return state

def game_router(state: GameState) -> str:
    """
    核心路由器，决定下一步是进行玩家行动还是上帝结算。
    """
    if state.get("game_over"):
        return END
    
    turn_type = state.get("turn_type")
    
    # 需要由 engine 执行的结算/公告节点
    if turn_type in ["night_settle", "day_announcement"]:
        return "engine_settle_node"
            
    # 其余所有涉及玩家决策或队列消耗的环节
    return "player_node"

# 构建图
workflow = StateGraph(GameState)

# 添加节点
workflow.add_node("init_node", init_node)
workflow.add_node("engine_settle_node", settle_night)
workflow.add_node("engine_check_node", check_winner)
workflow.add_node("engine_manager_node", next_turn)
workflow.add_node("player_node", player_node)

# 设置入口与初始循环
workflow.add_edge(START, "init_node")
workflow.add_edge("init_node", "engine_check_node")

# 核心判定循环：每次行动前先检查胜负
workflow.add_conditional_edges(
    "engine_check_node",
    game_router,
    {
        "player_node": "player_node",
        "engine_settle_node": "engine_settle_node",
        END: END
    }
)

# 动作执行完后，必须经过 manager 节点来推进 turn_type
workflow.add_edge("player_node", "engine_manager_node")
workflow.add_edge("engine_settle_node", "engine_manager_node")

# manager 推进后，回到 check_node 进行下一轮判定
workflow.add_edge("engine_manager_node", "engine_check_node")

# 编译
graph = workflow.compile()
