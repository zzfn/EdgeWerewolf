from src.agent.state import PlayerState, GameState

def get_default_state() -> GameState:
    """获取 12 人经典局的默认初始状态"""
    roles = (
        ["werewolf"] * 4 + 
        ["villager"] * 4 + 
        ["seer", "witch", "hunter", "guard"]
    )
    
    players = []
    names = [
        "阿尔法", "贝塔", "伽玛", "德尔塔", 
        "艾普西隆", "泽塔", "艾塔", "西塔", 
        "约塔", "卡帕", "兰姆达", "缪"
    ]
    
    for i, role in enumerate(roles):
        players.append(PlayerState(
            id=i + 1,
            name=names[i],
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
        "current_speaker_id": None,
        "history": [],
        "night_actions": {},
        "witch_potions": {"save": True, "poison": True},
        "last_guarded_id": None,
        "hunter_can_shoot": True,
        "last_night_dead": [],
        "game_over": False,
        "winner_side": None
    }
