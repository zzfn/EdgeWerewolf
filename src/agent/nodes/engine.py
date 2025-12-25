from typing import Dict, List, Any, Optional, Literal
from langchain_core.runnables import RunnableConfig
from src.agent.state import GameState, Message

def game_master_node(state: GameState, config: RunnableConfig) -> Dict[str, Any]:
    """
    逻辑中心 (GM)：硬编码。
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
        return {"game_over": True, "winner_side": "villager"}
    if wolf_count >= human_count:
        return {"game_over": True, "winner_side": "werewolf"}

    # 2. 调度逻辑
    phase = state["phase"]
    turn_type = state["turn_type"]
    
    # 通用点名逻辑：讨论、投票、竞选上警、投警长
    if turn_type in ["discussion", "voting", "sheriff_nomination", "sheriff_voting"] and state.get("discussion_queue"):
        new_queue = list(state["discussion_queue"])
        next_id = new_queue.pop(0)
        return {
            "discussion_queue": new_queue, 
            "current_player_id": next_id
        }

    # 环节自动推进逻辑
    if phase == "night":
        order = ["guard_protect", "wolf_kill", "seer_check", "witch_action"]
        try:
            current_idx = order.index(turn_type)
        except ValueError:
            current_idx = -1
            
        start_idx = current_idx if state.get("current_player_id") is None else current_idx + 1
        
        for i in range(start_idx, len(order)):
            next_type = order[i]
            role_map = {"guard_protect": "guard", "wolf_kill": "werewolf", "seer_check": "seer", "witch_action": "witch"}
            target_role = role_map[next_type]
            actor = next((p for p in players if p.role == target_role and p.is_alive), None)
            
            if actor:
                return {"turn_type": next_type, "current_player_id": actor.id}
        
        return {"turn_type": "night_settle", "current_player_id": None}
        
    if phase == "day":
        if turn_type == "day_announcement":
            # 如果是第一天且没有警长，进入警长竞选环节
            if state["day_count"] == 1 and state.get("sheriff_id") is None:
                return {
                    "turn_type": "sheriff_nomination",
                    "discussion_queue": sorted(state["alive_players"]),
                    "current_player_id": None
                }
            else:
                return {
                    "turn_type": "discussion", 
                    "discussion_queue": sorted(state["alive_players"]),
                    "current_player_id": None 
                }
        
        elif turn_type == "sheriff_nomination" and not state["discussion_queue"]:
            # 报名结束，进入投票环节
            candidates = state.get("election_candidates", [])
            if not candidates:
                # 没人上警，直接进讨论
                return {
                    "turn_type": "discussion",
                    "discussion_queue": sorted(state["alive_players"]),
                    "current_player_id": None
                }
            # 没参加竞选的人投票
            voters = [p_id for p_id in state["alive_players"] if p_id not in candidates]
            if not voters:
                # 全员上警，警徽流失（简化逻辑）
                return {
                    "turn_type": "discussion",
                    "discussion_queue": sorted(state["alive_players"]),
                    "current_player_id": None
                }
            return {
                "turn_type": "sheriff_voting",
                "discussion_queue": sorted(voters),
                "current_player_id": None
            }
            
        elif turn_type == "sheriff_voting" and not state["discussion_queue"]:
            # 投完票，进行警长结算
            return {
                "turn_type": "sheriff_settle",
                "current_player_id": None
            }

        elif turn_type == "sheriff_settle":
            # 警长诞生后，进入正式讨论
            return {
                "turn_type": "discussion",
                "discussion_queue": sorted(state["alive_players"]),
                "current_player_id": None
            }
            
        elif turn_type == "discussion" and not state["discussion_queue"]:
            return {
                "turn_type": "voting", 
                "discussion_queue": sorted(state["alive_players"]),
                "current_player_id": None 
            }
        elif turn_type == "voting" and not state["discussion_queue"]:
            # 投票结束，进入结算
            return {
                "turn_type": "voting_settle",
                "current_player_id": None 
            }
        elif turn_type == "voting_settle":
            # 结算完进夜晚，天数+1
            return {
                "phase": "night",
                "day_count": state["day_count"] + 1,
                "turn_type": "guard_protect",
                "current_player_id": None
            }

    return {}

def action_handler_node(state: GameState, config: RunnableConfig) -> Dict[str, Any]:
    """
    行动节点 (Action)：硬编码。
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
        updated_players = state["players"]
        for p in updated_players:
            if p.id in dead_ids:
                p.is_alive = False
        
        # 警长死亡处理 (简化：暂不考虑由于死亡移交警徽)
                
        return {
            "players": updated_players,
            "alive_players": new_alive,
            "last_night_dead": list(dead_ids),
            "phase": "day",
            "turn_type": "day_announcement",
            "night_actions": {},
            "votes": {}
        }
        
    if turn_type == "day_announcement":
        dead_info = "平安夜" if not state["last_night_dead"] else f"玩家 {', '.join(map(str, state['last_night_dead']))} 死亡"
        msg = Message(role="system", content=f"【上帝公告】第{state['day_count']}天。昨晚是{dead_info}。")
        return {"history": [msg]}

    if turn_type == "sheriff_settle":
        votes = state.get("votes", {})
        if not votes:
            msg = Message(role="system", content="【上帝公告】无人投票，警徽流失。")
            return {"history": [msg], "sheriff_id": None, "votes": {}}
        
        # 统计票数
        counts = {}
        for voter_id, target_id in votes.items():
            if target_id is not None:
                counts[target_id] = counts.get(target_id, 0) + 1
        
        if not counts:
            msg = Message(role="system", content="【上帝公告】所有选票均为空，警徽流失。")
            return {"history": [msg], "sheriff_id": None, "votes": {}}
            
        # 找到最高票
        max_votes = max(counts.values())
        winners = [p_id for p_id, v in counts.items() if v == max_votes]
        
        if len(winners) > 1:
            msg = Message(role="system", content=f"【上帝公告】玩家 {', '.join(map(str, winners))} 平票，警徽流失。")
            return {"history": [msg], "sheriff_id": None, "votes": {}}
        else:
            winner = winners[0]
            msg = Message(role="system", content=f"【上帝公告】玩家 {winner} 当选警长！")
            return {"history": [msg], "sheriff_id": winner, "votes": {}}

    if turn_type == "voting_settle":
        votes = state.get("votes", {})
        if not votes:
            msg = Message(role="system", content="【上帝公告】无人投票，无人被处决。")
            return {"history": [msg], "votes": {}}
            
        counts = {}
        sheriff_id = state.get("sheriff_id")
        for voter_id, target_id in votes.items():
            if target_id is not None:
                # 警长 1.5 票，其他人 1 票
                weight = 1.5 if voter_id == sheriff_id else 1.0
                counts[target_id] = counts.get(target_id, 0) + weight
        
        if not counts:
            msg = Message(role="system", content="【上帝公告】全员弃票，无人被处决。")
            return {"history": [msg], "votes": {}}
            
        max_votes = max(counts.values())
        winners = [p_id for p_id, v in counts.items() if v == max_votes]
        
        if len(winners) > 1:
            msg = Message(role="system", content=f"【上帝公告】玩家 {', '.join(map(str, winners))} 平票，无人被处决。")
            return {"history": [msg], "votes": {}}
        else:
            winner = winners[0]
            msg = Message(role="system", content=f"【上帝公告】玩家 {winner} 被投票处决。")
            updated_players = state["players"]
            for p in updated_players:
                if p.id == winner:
                    p.is_alive = False
            new_alive = [p_id for p_id in state["alive_players"] if p_id != winner]
            return {
                "players": updated_players,
                "alive_players": new_alive,
                "history": [msg],
                "votes": {}
            }

    if turn_type == "seer_check":
        target_id = state["night_actions"].get("seer_check")
        if target_id:
            target_p = next(p for p in state["players"] if p.id == target_id)
            updated_players = state["players"]
            seer = next(p for p in updated_players if p.role == "seer")
            res = "狼人" if target_p.role == "werewolf" else "好人"
            msg = Message(role="system", content=f"查验反馈：{target_id}号玩家的身份是【{res}】。")
            seer.private_history.append(msg)
            return {"players": updated_players}
            
    return {}
