import random
from typing import List
from src.agent.state import PlayerState, GameState

def get_default_state() -> GameState:
    """获取 12 人经典局的初始状态，并随机分配身份"""
    # 定义 12 人标准局配置：4狼 4民 预女猎守
    roles = (
        ["werewolf"] * 4 + 
        ["villager"] * 4 + 
        ["seer", "witch", "hunter", "guard"]
    )
    
    # 随机打乱身份
    random.shuffle(roles)
    
    players = []
    for i, role in enumerate(roles):
        players.append(PlayerState(
            id=i + 1,
            role=role,
            is_alive=True,
            private_history=[],
            private_thoughts=[]
        ))
        
    return {
        "players": players,
        "alive_players": [p.id for p in players],
        "phase": "night",
        "turn_type": "guard_protect", 
        "day_count": 1,
        "current_player_id": None, 
        "discussion_queue": [],
        "history": [],
        "night_actions": {},
        "votes": {},
        "witch_potions": {"save": True, "poison": True},
        "last_guarded_id": None,
        "hunter_can_shoot": True,
        "pending_hunter_shoot": None,
        "last_night_dead": [],
        "last_execution_id": None,
        "sheriff_id": None,
        "election_candidates": [],
        "game_over": False,
        "winner_side": None
    }
