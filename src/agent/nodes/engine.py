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
    # 0. 基础清理：如果当前状态中有并行的残留，先尝试清理标记
    # 但由于 GM 需要判定下一步，我们可以在返回 updates 时统一处理
    updates = {}
    
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
    
    # --- 流程优先级逻辑 ---

    # A. 遗言环节 (优先级高)
    if turn_type == "last_words" and state.get("pending_last_words"):
        if state.get("current_player_id") is None:
            new_list = list(state["pending_last_words"])
            next_id = new_list.pop(0)
            return {"current_player_id": next_id, "pending_last_words": new_list, "parallel_player_ids": None}
        else:
            # 当前玩家说完遗言了（由 action_handler 触发流转到这里，或者 player_agent 返回了）
            # 这里的流转由 action_handler 触发，或者在 player_agent 结束后回到 GM
            pass

    # B. 警徽移交环节 (仅警长死亡时)
    if turn_type == "sheriff_transfer" and state.get("pending_sheriff_transfer"):
        if state.get("current_player_id") != state.get("sheriff_id"):
            return {"current_player_id": state.get("sheriff_id"), "parallel_player_ids": None}

    # C. 猎人反击环节
    if turn_type == "hunter_shoot" and state.get("pending_hunter_shoot"):
        if state.get("current_player_id") != state["pending_hunter_shoot"]:
            return {"current_player_id": state["pending_hunter_shoot"], "parallel_player_ids": None}

    # D. 并行阶段判定 (处决投票、警长投票、上警报名)
    # 注意：PK 讨论完进 PK 投票也是并行的
    parallel_types = ["voting", "pk_voting", "sheriff_nomination", "sheriff_voting"]
    if turn_type in parallel_types and state.get("discussion_queue"):
        # 如果队列中有成员，且是并行环节，直接全量并行
        p_ids = list(state["discussion_queue"])
        return {
            "parallel_player_ids": p_ids,
            "discussion_queue": [], # 清空队列，表示已派发
            "current_player_id": None
        }

    # E. 通用点名/队列逻辑 (自由讨论、PK 讨论、上警发言)
    q_types = ["discussion", "pk_discussion", "sheriff_discussion"]
    if turn_type in q_types and state.get("discussion_queue"):
        new_queue = list(state["discussion_queue"])
        next_id = new_queue.pop(0)
        return {
            "discussion_queue": new_queue, 
            "current_player_id": next_id,
            "parallel_player_ids": None
        }

    # --- 环节自动推进逻辑 (状态机入口) ---
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
            # 1. 如果夜晚有人死且有遗言 (仅首夜有遗言)
            if state.get("pending_last_words"):
                return {"turn_type": "last_words", "current_player_id": None}
            
            # 2. 如果夜晚有人死且满足猎人开枪条件
            if state.get("pending_hunter_shoot"):
                return {"turn_type": "hunter_shoot", "current_player_id": state["pending_hunter_shoot"]}
            
            # 3. 警长移交 (如果昨晚死的是警长)
            if state.get("pending_sheriff_transfer"):
                return {"turn_type": "sheriff_transfer", "current_player_id": state.get("sheriff_id")}

            # 4. 进入正常流程 (直接讨论，竞选已在公告前完成)
            return {
                "turn_type": "discussion", 
                "discussion_queue": get_ordered_queue(state),
                "current_player_id": None,
                "parallel_player_ids": None 
            }
        
        elif turn_type == "last_words":
            # 遗言结束后的后续
            if state.get("pending_hunter_shoot"):
                return {"turn_type": "hunter_shoot", "current_player_id": state["pending_hunter_shoot"]}
            if state.get("pending_sheriff_transfer"):
                return {"turn_type": "sheriff_transfer", "current_player_id": state.get("sheriff_id")}
            # 回到主流程
            return {"turn_type": "discussion", "discussion_queue": get_ordered_queue(state), "current_player_id": None}

        elif turn_type == "hunter_shoot":
            return {"turn_type": "hunter_announcement", "current_player_id": None}
            
        elif turn_type == "hunter_announcement":
            # 如果是白天被投出去的猎人开枪后，应该可能还有警徽移交流程（如果猎人是警长）
            if state.get("pending_sheriff_transfer"):
                return {"turn_type": "sheriff_transfer", "current_player_id": state.get("sheriff_id")}
            
            # 继续原本流程
            if state["day_count"] == 1 and state.get("sheriff_id") is None:
                 return {"turn_type": "sheriff_nomination", "discussion_queue": sorted(state["alive_players"]), "current_player_id": None}
            
            # 注意：如果是由于投票死而触发的猎人公告，应该进夜晚前的结算，而非回讨论
            if state.get("last_execution_id") is not None:
                return {"turn_type": "execution_announcement", "current_player_id": None}
            
            return {"turn_type": "discussion", "discussion_queue": get_ordered_queue(state), "current_player_id": None}

        elif turn_type == "sheriff_nomination" and not state["discussion_queue"]:
            candidates = sorted(state.get("election_candidates", []))
            if not candidates:
                # 无人竞选，直接进公告天亮
                return {"turn_type": "day_announcement", "current_player_id": None, "parallel_player_ids": None}
            # 有人竞选，进入上警发言环节（串行）
            return {"turn_type": "sheriff_discussion", "discussion_queue": candidates, "current_player_id": None, "parallel_player_ids": None}
            
        elif turn_type == "sheriff_discussion" and not state["discussion_queue"]:
            # 发言结束，由非上警玩家投票（并行）
            candidates = state.get("election_candidates", [])
            voters = [p_id for p_id in state["alive_players"] if p_id not in candidates]
            if not voters:
                # 极端情况：全员上警，全部退水或某种逻辑错误，这里兜底
                return {"turn_type": "sheriff_settle", "current_player_id": None}
            return {"turn_type": "sheriff_voting", "discussion_queue": sorted(voters), "current_player_id": None}
            
        elif turn_type == "sheriff_voting" and not state["discussion_queue"]:
            return {"turn_type": "sheriff_settle", "current_player_id": None}

        elif turn_type == "sheriff_settle":
            # 如果平票 PK 逻辑在这里触发
            if state.get("pk_candidates"):
                return {"turn_type": "pk_discussion", "discussion_queue": state["pk_candidates"], "current_player_id": None}
            
            # 第一天竞选完后进公告（天亮了）
            if state["day_count"] == 1:
                return {"turn_type": "day_announcement", "current_player_id": None}
                
            return {"turn_type": "discussion", "discussion_queue": get_ordered_queue(state), "current_player_id": None}
            
        elif turn_type == "pk_discussion" and not state["discussion_queue"]:
             # PK 讨论结束，进入 PK 投票
             # 投票者是不在 PK 列表中的存活玩家
             voters = [p_id for p_id in state["alive_players"] if p_id not in state["pk_candidates"]]
             if not voters: voters = state["alive_players"] # 全员 PK 则全员投
             return {"turn_type": "pk_voting", "discussion_queue": voters, "current_player_id": None}
        
        elif turn_type == "pk_voting" and not state["discussion_queue"]:
             return {"turn_type": "voting_settle", "current_player_id": None}

        elif turn_type == "discussion" and not state["discussion_queue"]:
            return {"turn_type": "voting", "discussion_queue": sorted(state["alive_players"]), "current_player_id": None}
            
        elif turn_type == "voting" and not state["discussion_queue"]:
            return {"turn_type": "voting_settle", "current_player_id": None}
            
        elif turn_type == "voting_settle":
            # 1. 检查是否有 PK
            if state.get("pk_candidates"):
                return {"turn_type": "pk_discussion", "discussion_queue": state["pk_candidates"], "current_player_id": None}
            
            # 2. 检查被投出的人是否有遗言
            if state.get("pending_last_words"):
                return {"turn_type": "last_words", "current_player_id": None}
            
            # 3. 检查猎人反击
            if state.get("pending_hunter_shoot"):
                return {"turn_type": "hunter_shoot", "current_player_id": state["pending_hunter_shoot"]}
            
            # 4. 检查警长移交
            if state.get("pending_sheriff_transfer"):
                return {"turn_type": "sheriff_transfer", "current_player_id": state.get("sheriff_id")}

            return {"turn_type": "execution_announcement", "current_player_id": None}
            
        elif turn_type == "sheriff_transfer":
            # 移交完毕后继续
            if state.get("last_execution_id"):
                return {"turn_type": "execution_announcement", "current_player_id": None}
            return {"turn_type": "day_announcement", "current_player_id": None} # 可能需要回到公告后的逻辑

        elif turn_type == "execution_announcement":
            return {
                "phase": "night",
                "day_count": state["day_count"] + 1,
                "turn_type": "guard_protect",
                "current_player_id": None,
                "parallel_player_ids": None
            }

    return {}

def get_ordered_queue(state: GameState) -> List[int]:
    """辅助函数：根据警长偏好计算发言顺序"""
    alive = sorted(state["alive_players"])
    sheriff_id = state.get("sheriff_id")
    order_pref = state.get("speech_order_preference")
    
    if sheriff_id is None or order_pref is None:
        return alive
    
    # 简单的环形排序逻辑：以警长为中心
    idx = alive.index(sheriff_id)
    if order_pref == "clockwise":
        # 顺时针：idx+1, idx+2 ...
        return alive[idx+1:] + alive[:idx+1]
    else:
        # 逆时针
        rev = alive[::-1]
        r_idx = rev.index(sheriff_id)
        return rev[r_idx+1:] + rev[:r_idx+1]

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
            # 守卫和女巫同时作用于同一人，会导致该人依然死亡（医疗事故）
            if (is_guarded and is_saved) or (not is_guarded and not is_saved):
                dead_ids.add(wolf_kill)
        if witch_poison is not None:
            dead_ids.add(witch_poison)
            
        new_alive = [p_id for p_id in state["alive_players"] if p_id not in dead_ids]
        updated_players = state["players"]
        
        pending_hunter = None
        pending_last_words = []
        pending_sheriff_transfer = False
        
        for p in updated_players:
            if p.id in dead_ids:
                # 注意：此处不立即设置 p.is_alive = False，为了支持后续上警环节的隐秘死
                # 在 day_announcement 时再统一应用
                
                # 猎人判定
                if p.role == "hunter":
                    if p.id == witch_poison:
                        pass # 毒死不能开枪
                    elif state.get("hunter_can_shoot"):
                        pending_hunter = p.id
                
                # 遗言判定 (仅第一晚死亡的人有遗言)
                if state["day_count"] == 1:
                    pending_last_words.append(p.id)
                
                # 警长移交判定
                if p.id == state.get("sheriff_id"):
                    pending_sheriff_transfer = True
        
        # 提炼对局总结 (长期记忆)
        # 严格过滤：如果没有新的玩家发言，则不更新总结中关于“发言”的部分
        recent_history = state["history"][-40:]
        has_new_speech = any(m.player_id is not None for m in recent_history)
        
        if not has_new_speech and state.get("game_summary"):
            # 如果没有新发言且已有总结，保持现状，仅追加死亡公告（如果需要）
            new_summary = state["game_summary"]
        else:
            history_str = "\n".join([f"【玩家 {m.player_id}】: {m.content}" if m.player_id else f"【系统】: {m.content}" for m in recent_history])
            summary_prompt = (
                "你是一个狼人杀游戏的记录员。当前是第{day}天。请根据提供的【最新进展】更新对局总结。\n"
                f"原有总结：{state.get('game_summary','')}\n"
                f"最新进展：\n{history_str}\n"
                "【严格准则】：\n"
                "1. **禁止幻觉**：如果最新进展中没有任何玩家发言，绝对禁止虚构任何对话内容（如“1号跳预言家”等）。\n"
                "2. **身份脱敏**：严禁泄露上帝视角的真实身份。仅记录公开的跳职、金水、查杀及怀疑链。\n"
                "3. **极简**：控制在80字以内，仅记录关键转折点。\n"
                "如果你发现最新进展中只有系统死亡公告而无玩家发言，请仅更新死亡信息，不要碰发言总结。"
            ).format(day=state['day_count'])
            
            try:
                new_summary = summarizer_llm.invoke(summary_prompt).content
            except Exception:
                new_summary = state.get("game_summary", "对局进行中...")

        return {
            "players": updated_players,
            "alive_players": new_alive,
            "last_night_dead": sorted(list(dead_ids)),
            "pending_hunter_shoot": pending_hunter,
            "pending_last_words": sorted(pending_last_words),
            "pending_sheriff_transfer": pending_sheriff_transfer,
            "game_summary": new_summary,
            "phase": "day",
            "turn_type": "sheriff_nomination" if state["day_count"] == 1 and state.get("sheriff_id") is None else "day_announcement",
            "discussion_queue": sorted(state["alive_players"]) if state["day_count"] == 1 and state.get("sheriff_id") is None else [],
            "night_actions": {},
            "votes": {},
            "parallel_player_ids": None
        }
        
    if turn_type == "day_announcement":
        dead_ids = state.get("last_night_dead", [])
        
        # 应用死亡状态更新 (重要：这里才是真正结算生死的地方)
        updated_players = state["players"]
        new_alive = list(state["alive_players"])
        for p in updated_players:
            if p.id in dead_ids:
                p.is_alive = False
                if p.id in new_alive:
                    new_alive.remove(p.id)
        
        dead_info = "平安夜" if not dead_ids else f"玩家 {', '.join(map(str, dead_ids))} 死亡"
        msg = Message(role="system", content=f"【上帝公告】第{state['day_count']}天。昨晚是{dead_info}。")
        
        return {
            "history": [msg],
            "players": updated_players,
            "alive_players": sorted(new_alive),
            "last_night_dead": [] # 清空本轮死亡记录
        }

    if turn_type == "sheriff_settle":
        votes = state.get("votes", {})
        counts = {}
        for voter_id, target_id in votes.items():
            if target_id is not None:
                counts[target_id] = counts.get(target_id, 0) + 1
        
        if not counts:
            return {"sheriff_id": None, "votes": {}, "pk_candidates": []}
            
        max_votes = max(counts.values())
        winners = [p_id for p_id, v in counts.items() if v == max_votes]
        
        if len(winners) == 1:
            winner = winners[0]
            msg = Message(role="system", content=f"【上帝公告】玩家 {winner} 当选警长！")
            return {"history": [msg], "sheriff_id": winner, "votes": {}, "pk_candidates": []}
        else:
            # 平票 PK
            msg = Message(role="system", content=f"【上帝公告】警长竞选出现平票，玩家 {', '.join(map(str, winners))} 进入 PK 环节。")
            return {"history": [msg], "pk_candidates": winners, "votes": {}}

    if turn_type == "voting_settle":
        votes = state.get("votes", {})
        counts = {}
        sheriff_id = state.get("sheriff_id")
        for voter_id, target_id in votes.items():
            if target_id is not None:
                weight = 1.5 if voter_id == sheriff_id else 1.0
                counts[target_id] = counts.get(target_id, 0) + weight
        
        if not counts:
            return {"last_execution_id": None, "votes": {}, "pk_candidates": []}
            
        max_votes = max(counts.values())
        winners = [p_id for p_id, v in counts.items() if v == max_votes]
        
        if len(winners) == 1:
            winner = winners[0]
            updated_players = state["players"]
            pending_hunter = None
            pending_sheriff_transfer = False
            for p in updated_players:
                if p.id == winner:
                    p.is_alive = False
                    if p.role == "hunter" and state.get("hunter_can_shoot"):
                        pending_hunter = p.id
                    if p.id == state.get("sheriff_id"):
                        pending_sheriff_transfer = True
            
            new_alive = [p_id for p_id in state["alive_players"] if p_id != winner]
            return {
                "players": updated_players,
                "alive_players": new_alive,
                "last_execution_id": winner,
                "pending_hunter_shoot": pending_hunter,
                "pending_last_words": [winner], # 被处决玩家总有遗言
                "pending_sheriff_transfer": pending_sheriff_transfer,
                "votes": {},
                "pk_candidates": []
            }
        else:
            # 投票平票
            msg = Message(role="system", content=f"【上帝公告】投票出现平票，玩家 {', '.join(map(str, winners))} 进入 PK 环节。")
            return {"history": [msg], "pk_candidates": winners, "votes": {}}
        
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

    if turn_type == "sheriff_transfer":
        # 警长遗言中可以选择：移交或撕掉
        # 这里为了简化，假设 player_agent 返回了 target_id 用于移交，或者 None 用于撕掉
        transfer_target = state["night_actions"].get("sheriff_transfer")
        if transfer_target is not None:
            msg = Message(role="system", content=f"【上帝公告】原警长将警徽移交给玩家 {transfer_target}。")
            return {"history": [msg], "sheriff_id": transfer_target, "pending_sheriff_transfer": False}
        else:
            msg = Message(role="system", content="【上帝公告】原警长选择撕掉警徽，本局后续将没有警长。")
            return {"history": [msg], "sheriff_id": None, "pending_sheriff_transfer": False}

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
