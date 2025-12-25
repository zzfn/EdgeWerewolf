from typing import Dict, List, Optional
from src.agent.state import GameState, Message
from src.agent.schema import NightAction

def settle_night(state: GameState) -> GameState:
    """
    结算夜晚行动逻辑 (上帝视角)
    """
    turn_type = state.get("turn_type")
    
    if turn_type == "night_settle":
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
                dead_ids.add(wolf_kill_id)
            elif not is_guarded and not is_saved:
                dead_ids.add(wolf_kill_id)
                
        # 2. 处理女巫毒药
        if witch_poison_id is not None:
            dead_ids.add(witch_poison_id)
            
        new_dead = list(dead_ids)
        current_alive = state["alive_players"]
        new_alive = [p_id for p_id in current_alive if p_id not in new_dead]
        
        return {
            **state,
            "alive_players": new_alive,
            "last_night_dead": new_dead,
            "phase": "day",
            "turn_type": "day_announcement",
            "night_actions": {},
            "queue": [],
            "current_speaker_id": None
        }
    
    elif turn_type == "day_announcement":
        # 发布公告
        dead_info = "昨晚是平安夜。" if not state["last_night_dead"] else f"昨晚死亡的是：{', '.join([str(d) for d in state['last_night_dead']])}号玩家。"
        msg = Message(role="system", content=f"【上帝公告】第{state['day_count']}天。{dead_info}")
        state["history"].append(msg)
        
        # 直接由 next_turn 接手填充队列，这里只负责清理
        return {
            **state,
            "turn_type": "discussion",
            "queue": [],
            "current_speaker_id": None
        }
        
    return state

def check_winner(state: GameState) -> GameState:
    """
    检查游戏是否结束。
    """
    players = state["players"]
    alive_ids = state["alive_players"]
    
    wolf_count = 0
    human_count = 0
    
    for p_id in alive_ids:
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
    状态机进度管理器。
    核心逻辑：如果一个环节的队列为空，则自动递归推进到下一个环节，直到找到有人的环节或结算点。
    """
    if state.get("game_over"):
        return state

    # 1. 优先消耗队列
    if state.get("queue"):
        next_id = state["queue"].pop(0)
        return {**state, "current_speaker_id": next_id}

    # 2. 队列为空，尝试推进环节
    phase = state["phase"]
    turn_type = state["turn_type"]
    players = state["players"]
    alive_ids = state["alive_players"]

    # 定义流程顺序
    flow = {
        "night": ["guard_protect", "wolf_kill", "seer_check", "witch_action", "night_settle"],
        "day": ["day_announcement", "discussion", "voting"]
    }

    # 找到当前环节在流程中的位置
    current_flow = flow[phase]
    try:
        idx = current_flow.index(turn_type)
    except ValueError:
        idx = -1

    # 尝试寻找下一个有人的环节
    while True:
        idx += 1
        # 如果当前阶段走完了，切换阶段
        if idx >= len(current_flow):
            if phase == "night":
                # 夜晚结束，虽然逻辑上 night_settle 应该已经把 phase 改成了 day
                # 但为了健壮性，这里做保底
                phase = "day"
                idx = 0
                current_flow = flow[phase]
            else:
                # 白天结束，进下一晚
                phase = "night"
                idx = 0
                current_flow = flow[phase]
                state["day_count"] += 1

        next_turn_type = current_flow[idx]
        
        # 特殊处理结算节点，它们在图中是独立存在的，直接返回让图去跳转
        if next_turn_type in ["night_settle", "day_announcement"]:
            return {**state, "phase": phase, "turn_type": next_turn_type, "queue": [], "current_speaker_id": None}

        # 计算下一个环节的队列
        new_queue = []
        if next_turn_type == "guard_protect":
            new_queue = [p.id for p in players if p.role == "guard" and p.is_alive]
        elif next_turn_type == "wolf_kill":
            new_queue = [p.id for p in players if p.role == "werewolf" and p.is_alive]
        elif next_turn_type == "seer_check":
            # 查验反馈 (如果是从 seer_check 推进走的，先补处理反馈)
            if turn_type == "seer_check":
                target_id = state["night_actions"].get("seer_check")
                if target_id:
                    target_p = next(p for p in players if p.id == target_id)
                    seer = next((p for p in players if p.role == "seer"), None)
                    if seer:
                        res = "狼人" if target_p.role == "werewolf" else "好人"
                        info = f"系统反馈：{target_id}号玩家({target_p.name})的身份是【{res}】。"
                        seer.private_history.append(Message(role="system", content=info))
            new_queue = [p.id for p in players if p.role == "seer" and p.is_alive]
        elif next_turn_type == "witch_action":
            new_queue = [p.id for p in players if p.role == "witch" and p.is_alive]
        elif next_turn_type == "discussion" or next_turn_type == "voting":
            new_queue = sorted(alive_ids)

        if new_queue:
            # 找到有人的环节了
            next_id = new_queue.pop(0)
            return {
                **state, 
                "phase": phase, 
                "turn_type": next_turn_type, 
                "queue": new_queue, 
                "current_speaker_id": next_id
            }
        
        # 如果该环节没人，继续 while 循环寻找下一个环节
        turn_type = next_turn_type
