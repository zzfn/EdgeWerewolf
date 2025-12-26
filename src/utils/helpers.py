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
    
    # 定义个性和风格池，用于增加 AI 的多样性
    personalities = ["逻辑严密", "直觉敏锐", "谨慎稳重", "容易冲动", "深沉冷静", "言语犀利", "温和中立", "富有正义感", "多疑狡黠", "随和跟风"]
    styles = ["简明扼要，直指核心", "富有煽动性，擅长带动情绪", "爱讲冷笑话，语气幽默", "说话文绉绉，逻辑性极强", "语气坚定，不容怀疑", "谦逊低调，多用疑问句", "直白坦诚，不绕弯子", "喜欢复述他人观点并进行补充", "神秘莫测，话里有话", "积极表现，语速较快"]

    players = []
    for i, role in enumerate(roles):
        players.append(PlayerState(
            id=i + 1,
            role=role,
            is_alive=True,
            personality=random.choice(personalities),
            style=random.choice(styles),
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
        "game_summary": "游戏刚刚开始，暂无历史总结。",
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
