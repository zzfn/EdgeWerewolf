from typing import Literal, Union
from langgraph.graph import StateGraph, END, START
from langchain_core.runnables import RunnableConfig
from src.agent.state import GameState
from src.agent.nodes.engine import game_master_node, action_handler_node
from src.agent.nodes.roles import player_agent_node
from src.utils.helpers import get_default_state

def init_node(state: GameState, config: RunnableConfig) -> GameState:
    """初始化节点：如果状态缺失，加载默认对局"""
    if not state or "players" not in state or not state["players"]:
        return get_default_state()
    return state

def routing_logic(state: GameState):
    """
    中控路由逻辑 (GM 的指挥棒)。
    """
    if state.get("game_over"):
        return END
        
    turn_type = state.get("turn_type")
    current_id = state.get("current_player_id")
    
    if current_id is not None:
        return "player_agent"
        
    if turn_type in ["night_settle", "day_announcement", "sheriff_settle", "voting_settle"]:
        return "action_handler"
        
    return "game_master"

# 构建图
workflow = StateGraph(GameState)

# 添加节点
workflow.add_node("init", init_node)
workflow.add_node("game_master", game_master_node)
workflow.add_node("player_agent", player_agent_node)
workflow.add_node("action_handler", action_handler_node)

# 设置边
workflow.add_edge(START, "init")
workflow.add_edge("init", "game_master")
workflow.add_edge("player_agent", "game_master")
workflow.add_edge("action_handler", "game_master")

workflow.add_conditional_edges(
    "game_master",
    routing_logic,
    {
        "player_agent": "player_agent",
        "action_handler": "action_handler",
        "game_master": "game_master",
        END: END
    }
)

# 编译并设置默认配置
graph = workflow.compile().with_config({"recursion_limit": 100})
