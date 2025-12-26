import os
from typing import Dict, List, Any, Optional, Literal
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from src.agent.state import GameState, Message

# 加载环境变量
load_dotenv()

# 初始化用于总结的 LLM
summarizer_llm = ChatOpenAI(
    model="deepseek-chat", 
    openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
    openai_api_base="https://api.deepseek.com/v1",
    temperature=0.3 # 总结需要低随机性
)

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
    
    # 猎人反击环节优先级最高
    if turn_type == "hunter_shoot" and state.get("pending_hunter_shoot"):
        # 如果还没点名该猎人，则点名
        if state.get("current_player_id") != state["pending_hunter_shoot"]:
            return {"current_player_id": state["pending_hunter_shoot"]}
        else:
            # 已经点名过且执行完了（由 player_agent 返回了 night_actions 中对应的 shoot），
            # 这里的跳转逻辑由下面的 switch 处理
            pass

    # 通用点名逻辑
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
            # 如果夜晚有人死且满足猎人开枪条件
            if state.get("pending_hunter_shoot"):
                return {"turn_type": "hunter_shoot", "current_player_id": state["pending_hunter_shoot"]}
            
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
        
        elif turn_type == "hunter_shoot":
            return {"turn_type": "hunter_announcement", "current_player_id": None}
            
        elif turn_type == "hunter_announcement":
            # 回到之前的流程决策（比如本来要进讨论或者竞选）
            # 这里简化逻辑，默认认为猎人开枪后继续流程
            if state["day_count"] == 1 and state.get("sheriff_id") is None:
                 return {
                    "turn_type": "sheriff_nomination",
                    "discussion_queue": sorted(state["alive_players"]),
                    "current_player_id": None
                }
            return {
                "turn_type": "discussion",
                "discussion_queue": sorted(state["alive_players"]),
                "current_player_id": None
            }

        elif turn_type == "sheriff_nomination" and not state["discussion_queue"]:
            candidates = state.get("election_candidates", [])
            if not candidates:
                return {
                    "turn_type": "discussion",
                    "discussion_queue": sorted(state["alive_players"]),
                    "current_player_id": None
                }
            voters = [p_id for p_id in state["alive_players"] if p_id not in candidates]
            if not voters:
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
            return {"turn_type": "sheriff_settle", "current_player_id": None}

        elif turn_type == "sheriff_settle":
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
            return {"turn_type": "voting_settle", "current_player_id": None}
            
        elif turn_type == "voting_settle":
            # 如果被投走的是猎人，进入猎人环节
            if state.get("pending_hunter_shoot"):
                return {"turn_type": "hunter_shoot", "current_player_id": state["pending_hunter_shoot"]}
            return {"turn_type": "execution_announcement", "current_player_id": None}
            
        elif turn_type == "execution_announcement":
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
        
        pending_hunter = None
        for p in updated_players:
            if p.id in dead_ids:
                p.is_alive = False
                # 猎人判定
                if p.role == "hunter":
                    if p.id == witch_poison:
                        # 毒死不能开枪
                        pass
                    elif state.get("hunter_can_shoot"):
                        pending_hunter = p.id
        
        # 提炼对局总结 (长期记忆)
        history_str = "\n".join([f"【玩家 {m.player_id}】: {m.content}" if m.player_id else f"【系统】: {m.content}" for m in state["history"][-30:]])
        summary_prompt = f"请作为狼人杀上帝，对目前的对局进行极简总结（100字以内）。\n原有总结：{state.get('game_summary','')}\n最新进展：{history_str}\n请更新总结，重点记录谁死了、谁跳了身份、场上核心矛盾点。"
        try:
            new_summary = summarizer_llm.invoke(summary_prompt).content
        except Exception:
            new_summary = state.get("game_summary", "对局进行中...")

        return {
            "players": updated_players,
            "alive_players": new_alive,
            "last_night_dead": list(dead_ids),
            "pending_hunter_shoot": pending_hunter,
            "game_summary": new_summary,
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
        counts = {}
        for voter_id, target_id in votes.items():
            if target_id is not None:
                counts[target_id] = counts.get(target_id, 0) + 1
        
        if not counts:
            return {"sheriff_id": None, "votes": {}}
            
        max_votes = max(counts.values())
        winners = [p_id for p_id, v in counts.items() if v == max_votes]
        
        if len(winners) == 1:
            winner = winners[0]
            msg = Message(role="system", content=f"【上帝公告】玩家 {winner} 当选警长！")
            return {"history": [msg], "sheriff_id": winner, "votes": {}}
        return {"sheriff_id": None, "votes": {}}

    if turn_type == "voting_settle":
        votes = state.get("votes", {})
        counts = {}
        sheriff_id = state.get("sheriff_id")
        for voter_id, target_id in votes.items():
            if target_id is not None:
                weight = 1.5 if voter_id == sheriff_id else 1.0
                counts[target_id] = counts.get(target_id, 0) + weight
        
        if not counts:
            return {"last_execution_id": None, "votes": {}}
            
        max_votes = max(counts.values())
        winners = [p_id for p_id, v in counts.items() if v == max_votes]
        
        if len(winners) == 1:
            winner = winners[0]
            updated_players = state["players"]
            pending_hunter = None
            for p in updated_players:
                if p.id == winner:
                    p.is_alive = False
                    if p.role == "hunter" and state.get("hunter_can_shoot"):
                        pending_hunter = p.id
            new_alive = [p_id for p_id in state["alive_players"] if p_id != winner]
            return {
                "players": updated_players,
                "alive_players": new_alive,
                "last_execution_id": winner,
                "pending_hunter_shoot": pending_hunter,
                "votes": {}
            }
        return {"last_execution_id": None, "votes": {}}
        
    if turn_type == "execution_announcement":
        target_id = state.get("last_execution_id")
        if target_id is not None:
            msg = Message(role="system", content=f"【上帝公告】投票结束，玩家 {target_id} 被处决。")
        else:
            msg = Message(role="system", content="【上帝公告】投票结束，平票或全员弃票，无人被处决。")
        return {"history": [msg]}

    if turn_type == "hunter_announcement":
        shoot_target = state["night_actions"].get("hunter_shoot")
        if shoot_target:
            updated_players = state["players"]
            for p in updated_players:
                if p.id == shoot_target:
                    p.is_alive = False
            new_alive = [p_id for p_id in state["alive_players"] if p_id != shoot_target]
            msg = Message(role="system", content=f"【上帝公告】猎人发动反击，玩家 {shoot_target} 被射杀！")
            return {
                "players": updated_players,
                "alive_players": new_alive,
                "history": [msg],
                "pending_hunter_shoot": None, # 关闭环节
                "hunter_can_shoot": False      # 技能已用
            }
        else:
            msg = Message(role="system", content="【上帝公告】猎人选择放弃反击。")
            return {
                "history": [msg],
                "pending_hunter_shoot": None,
                "hunter_can_shoot": False
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
