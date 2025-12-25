from typing import Dict, List, Any, Optional, Literal
from src.agent.state import GameState, Message

def game_master_node(state: GameState) -> GameState:
    """
    逻辑中心 (GM)：硬编码。
    职责：判定胜负、切换昼夜、决定下一个行动者或环节。
    """
    # 1. 判定胜负
    players = state["players"]
    alive_ids = state["alive_players"]
    
    wolf_count = 0
    human_count = 0
    for p_id in alive_ids:
        p = next(player for player in players if player.id == p_id)
        if p.role == "werewolf":
            wolf_count += 1
        else:
            human_count += 1
            
    if wolf_count == 0:
        return {**state, "game_over": True, "winner_side": "villager"}
    if wolf_count >= human_count:
        return {**state, "game_over": True, "winner_side": "werewolf"}

    # 2. 调度逻辑
    phase = state["phase"]
    turn_type = state["turn_type"]
    
    # 如果讨论环节还有人没发言
    if turn_type == "discussion" and state.get("discussion_queue"):
        new_queue = list(state["discussion_queue"])
        next_id = new_queue.pop(0)
        return {**state, "discussion_queue": new_queue, "current_player_id": next_id}
        
    # 如果投票环节还有人没投
    if turn_type == "voting" and state.get("discussion_queue"): # 复用队列
        new_queue = list(state["discussion_queue"])
        next_id = new_queue.pop(0)
        return {**state, "discussion_queue": new_queue, "current_player_id": next_id}

    # 环节自动推进逻辑 (GM 作为指挥棒)
    if phase == "night":
        # 夜晚流程点名顺序：守卫 -> 狼人 -> 预言家 -> 女巫
        order = ["guard_protect", "wolf_kill", "seer_check", "witch_action"]
        try:
            current_idx = order.index(turn_type)
        except ValueError:
            current_idx = -1
            
        # 确定搜索起点：如果当前还没点名或点名人不在当前环节，从当前环节开始搜；
        # 如果当前人刚行动完，从下一个环节开始搜。
        start_idx = current_idx if state.get("current_player_id") is None else current_idx + 1
        
        # 寻找下一个有人参与的夜晚环节
        for i in range(start_idx, len(order)):
            next_type = order[i]
            # 检查对应角色是否存活
            role_map = {
                "guard_protect": "guard",
                "wolf_kill": "werewolf",
                "seer_check": "seer",
                "witch_action": "witch"
            }
            target_role = role_map[next_type]
            actor = next((p for p in players if p.role == target_role and p.is_alive), None)
            
            if actor:
                return {**state, "turn_type": next_type, "current_player_id": actor.id}
        
        # 如果走完所有夜晚角色，进入结算
        return {**state, "turn_type": "night_settle", "current_player_id": None}
        
    if phase == "day":
        if turn_type == "day_announcement":
            # 公告完自动进讨论，准备队列
            return {
                **state, 
                "turn_type": "discussion", 
                "discussion_queue": sorted(state["alive_players"]),
                "current_player_id": None # 准备进入 Player_Agent 循环
            }
        elif turn_type == "discussion" and not state["discussion_queue"]:
            # 讨论完进投票，准备队列
            return {
                **state, 
                "turn_type": "voting", 
                "discussion_queue": sorted(state["alive_players"]), # 复用
                "current_player_id": None 
            }
        elif turn_type == "voting" and not state["discussion_queue"]:
            # 投票完进夜晚，天数+1
            return {
                **state,
                "phase": "night",
                "day_count": state["day_count"] + 1,
                "turn_type": "guard_protect", # 重置为夜晚起点
                "current_player_id": None
            }

    return state

def action_handler_node(state: GameState) -> GameState:
    """
    行动节点 (Action)：硬编码。
    职责：处理具体的结算逻辑（杀人、验人结果同步、公告产生）。
    """
    turn_type = state["turn_type"]
    
    if turn_type == "night_settle":
        actions = state.get("night_actions", {})
        wolf_kill = actions.get("wolf_kill")
        guard_protect = actions.get("guard_protect")
        witch_save = actions.get("witch_save")
        witch_poison = actions.get("witch_poison")
        
        dead_ids = set()
        if wolf_kill is not None:
            is_guarded = (wolf_kill == guard_protect)
            is_saved = (wolf_kill == witch_save)
            if (is_guarded and is_saved) or (not is_guarded and not is_saved):
                dead_ids.add(wolf_kill)
        
        if witch_poison is not None:
            dead_ids.add(witch_poison)
            
        new_alive = [p_id for p_id in state["alive_players"] if p_id not in dead_ids]
        
        # 物理状态更新
        for player in state["players"]:
            if player.id in dead_ids:
                player.is_alive = False
                
        return {
            **state,
            "alive_players": new_alive,
            "last_night_dead": list(dead_ids),
            "phase": "day",
            "turn_type": "day_announcement",
            "night_actions": {}, # 清空
            "votes": {}
        }
        
    if turn_type == "day_announcement":
        dead_info = "平安夜" if not state["last_night_dead"] else f"玩家 {', '.join(map(str, state['last_night_dead']))} 死亡"
        msg = Message(role="system", content=f"【上帝公告】第{state['day_count']}天。昨晚是{dead_info}。")
        state["history"].append(msg)
        return state

    if turn_type == "seer_check":
        # 将验人结果物理同步给预言家 (在 Player_Agent 行动后)
        target_id = state["night_actions"].get("seer_check")
        if target_id:
            target_p = next(p for p in state["players"] if p.id == target_id)
            seer = next(p for p in state["players"] if p.role == "seer")
            res = "狼人" if target_p.role == "werewolf" else "好人"
            msg = f"查验反馈：{target_id}号玩家的身份是【{res}】。"
            seer.private_history.append(Message(role="system", content=msg))
            
    return state
