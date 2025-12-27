import random
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
    

    # 定义可选的性格特质
    personalities = [
        "逻辑严密、冷静分析票型，不容易被煽动",
        "直觉敏锐、关注发言者的语气细节，敢于质疑",
        "激进博弈、倾向于带节奏进行对抗，不怕被针对",
        "稳健慎重、在信息不足时倾向于保守观察，不轻易站边",
        "强势领导、喜欢作为警长带队，对不一致的逻辑零容忍",
        "感性共情、容易信任表态诚恳的玩家，但也可能被欺骗"
    ]

    players = []
    for i, role in enumerate(roles):
        players.append(PlayerState(
            id=i + 1,
            role=role,
            personality=random.choice(personalities),
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
