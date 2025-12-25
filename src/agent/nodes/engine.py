from typing import Dict, List, Optional
from src.agent.state import GameState, Message
from src.agent.schema import NightAction

def settle_night(state: GameState) -> GameState:
    """
    结算夜晚行动逻辑 (上帝视角)
    规则：
    1. 守卫先守：如果被守，狼人杀不死。
    2. 女巫救人：如果被救，狼人杀不死。
    3. 同守同救：如果同时被守且被救，目标仍然死亡。
    4. 狼人杀人：最终确定死亡名单。
    """
    actions = state.get("night_actions", {})
    wolf_kill_id = actions.get("wolf_kill")
    guard_id = actions.get("guard_protect")
    witch_save_id = actions.get("witch_save")
    witch_poison_id = actions.get("witch_poison")
    
    dead_ids = set()
    
    # 1. 处理狼人击杀
    if wolf_kill_id is not None:
        is_guarded = (wolf_kill_id == guard_id)
        is_saved = (wolf_kill_id == witch_save_id)
        
        if is_guarded and is_saved:
            # 同守同救，目标死亡
            dead_ids.add(wolf_kill_id)
        elif not is_guarded and not is_saved:
            # 没守没救，目标死亡
            dead_ids.add(wolf_kill_id)
        # 其他情况（单守或单救）目标存活
            
    # 2. 处理女巫毒药
    if witch_poison_id is not None:
        dead_ids.add(witch_poison_id)
        
    # 更新存活状态
    new_dead = list(dead_ids)
    current_alive = state["alive_players"]
    new_alive = [p_id for p_id in current_alive if p_id not in new_dead]
    
    # 更新状态
    return {
        **state,
        "alive_players": new_alive,
        "last_night_dead": new_dead,
        "phase": "day",
        "turn_type": "day_announcement",
        "night_actions": {} # 清空缓冲区
    }

def check_winner(state: GameState) -> GameState:
    """
    检查游戏是否结束。
    规则：
    - 狼人全部出局 -> 村民胜
    - 狼人人数 >= 好人人数 -> 狼人胜
    """
    players = state["players"]
    alive_ids = state["alive_players"]
    
    wolf_count = 0
    human_count = 0
    
    for p_id in alive_ids:
        # 找到对应的玩家角色
        player = next(p for p in players if p.id == p_id)
        if player.role == "werewolf":
            wolf_count += 1
        else:
            human_count += 1
            
    if wolf_count == 0:
        return {**state, "game_over": True, "winner_side": "villager"}
    
    if wolf_count >= human_count:
        return {**state, "game_over": True, "winner_side": "werewolf"}
        
    return state

def next_turn(state: GameState) -> GameState:
    """
    推进游戏轮次逻辑 (上帝视角的流程指挥官)。
    """
    phase = state["phase"]
    turn_type = state["turn_type"]
    
    # 夜晚流程转换
    if phase == "night":
        if turn_type == "guard_protect":
            return {**state, "turn_type": "wolf_kill"}
        elif turn_type == "wolf_kill":
            return {**state, "turn_type": "seer_check"}
        elif turn_type == "seer_check":
            return {**state, "turn_type": "witch_action"}
        elif turn_type == "witch_action":
            return {**state, "turn_type": "night_settle"}
        elif turn_type == "night_settle":
            # settle_night 节点会处理 night -> day 的转换，所以这里通常不触发
            pass
            
    # 白天流程转换
    if phase == "day":
        if turn_type == "day_announcement":
            return {**state, "turn_type": "discussion"}
        elif turn_type == "discussion":
            return {**state, "turn_type": "voting"}
        elif turn_type == "voting":
            # 投票结束，准备进入夜晚
            return {
                **state,
                "phase": "night",
                "day_count": state["day_count"] + 1,
                "turn_type": "guard_protect"
            }
            
    return state
