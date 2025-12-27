import os
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from src.agent.state import GameState, Message, PlayerState
from src.agent.schema import AgentOutput, NightAction
from src.agent.prompts.base import (
    BASE_SYSTEM_PROMPT,
    WOLF_INSTRUCTIONS,
    VILLAGER_INSTRUCTIONS,
    SEER_INSTRUCTIONS,
    WITCH_INSTRUCTIONS,
    HUNTER_INSTRUCTIONS,
    GUARD_INSTRUCTIONS,
    SHERIFF_NOMINATION_INSTRUCTIONS,
    SHERIFF_DISCUSSION_INSTRUCTIONS,
    SHERIFF_VOTING_INSTRUCTIONS,
)
from dotenv import load_dotenv
from langfuse.langchain import CallbackHandler

# 加载环境变量
load_dotenv()

# 初始化 DeepSeek 模型
llm = ChatOpenAI(
    model="deepseek-chat", 
    openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
    openai_api_base="https://api.deepseek.com/v1",
    temperature=0.7
)

def get_role_instructions(player: PlayerState, state: GameState) -> str:
    
    # 基础角色指令
    role = player.role
    if role == "werewolf":
        teammates = [str(p.id) for p in state["players"] if p.role == "werewolf" and p.id != player.id]
        instructions = WOLF_INSTRUCTIONS.format(teammates=", ".join(teammates))
    elif role == "villager":
        instructions = VILLAGER_INSTRUCTIONS
    elif role == "seer":
        history_msgs = [m.content for m in player.private_history if m.role == "system"]
        check_history = "\n - " + "\n - ".join(history_msgs) if history_msgs else "暂无记录"
        instructions = SEER_INSTRUCTIONS.format(check_history=check_history)
    elif role == "witch":
        p = state["witch_potions"]
        save_status = "【可用】" if p.get("save") else "【已用完】"
        clock_status = "【可用】" if p.get("poison") else "【已用完】"
        status_str = f"解药：{save_status}, 毒药：{clock_status}"
        
        killed_id = state.get("night_actions", {}).get("wolf_kill")
        killed_info = f"昨晚被狼人击杀的是：{killed_id}号玩家" if killed_id is not None else "昨晚没有人被狼人击杀。"
        instructions = WITCH_INSTRUCTIONS.format(potions_status=status_str, killed_info=killed_info)
    elif role == "hunter":
        instructions = HUNTER_INSTRUCTIONS
    elif role == "guard":
        instructions = GUARD_INSTRUCTIONS
    
    # 追加环节特定指令
    turn_type = state["turn_type"]
    if turn_type == "sheriff_nomination":
        instructions += "\n\n" + SHERIFF_NOMINATION_INSTRUCTIONS
    elif turn_type == "sheriff_discussion":
        instructions += "\n\n" + SHERIFF_DISCUSSION_INSTRUCTIONS
    elif turn_type == "sheriff_voting":
        instructions += "\n\n" + SHERIFF_VOTING_INSTRUCTIONS
        
    return instructions

def player_agent_node(state: GameState, config: RunnableConfig) -> Dict[str, Any]:
    """
    智能体执行节点 (Player_Agent)：LLM 驱动。
    职责：根据当前身份、公共历史和私有想法，生成发言、内心思考或结构化动作。
    """
    current_id = state.get("current_player_id")
    if current_id is None:
        return {}

    player = next(p for p in state["players"] if p.id == current_id)
    phase = state["phase"]
    turn_type = state["turn_type"]

    # 构造 Prompt
    role_instr = get_role_instructions(player, state)
    sys_prompt = BASE_SYSTEM_PROMPT.format(
        role=player.role,
        player_id=player.id,
        personality=player.personality or "理性思考",
        role_specific_instructions=role_instr
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "{system_instructions}"),
        ("human", "当前对局状态：\n阶段：{phase}\n环节：{turn_type}\n游戏历史大纲（长期记忆）：{game_summary}\n最近发言记录（短期记忆）：\n{history}\n你的私有想法：{private_thoughts}\n请输出你的决策。")
    ])
    
    # 结构化输出
    if phase == "night" or turn_type in ["hunter_shoot", "sheriff_transfer"]:
        structured_llm = llm.with_structured_output(NightAction, method="function_calling")
    else:
        structured_llm = llm.with_structured_output(AgentOutput, method="function_calling")
        
    # 构造历史字符串：显示玩家 ID 而非角色名，防止混淆发言者
    history_lines = []
    for m in state["history"][-20:]: # 稍微增加记忆长度
        prefix = f"【玩家 {m.player_id}】" if m.player_id else "【系统公告】"
        history_lines.append(f"{prefix}: {m.content}")
    history_str = "\n".join(history_lines)
    
    private_thoughts_str = "\n".join(player.private_thoughts[-5:])
    
    # Langfuse 局部观测
    langfuse_handler = CallbackHandler()
    
    # 翻译环节名称，减少 AI 混淆
    type_map = {
        "night": "夜晚",
        "day": "白天",
        "wolf_kill": "狼人杀人",
        "seer_check": "预言家验人",
        "witch_action": "女巫行动",
        "guard_action": "守卫行动",
        "day_announcement": "天亮公告",
        "sheriff_nomination": "警长竞选报名",
        "sheriff_discussion": "警长竞选发言",
        "sheriff_voting": "警长投票",
        "sheriff_settle": "警长产生结果公布",
        "discussion": "自由发言",
        "voting": "处决投票",
        "voting_settle": "处决结果公布",
        "last_words": "发表遗言",
        "pk_discussion": "PK发言",
        "pk_voting": "PK投票"
    }
    cn_phase = type_map.get(phase, phase)
    cn_turn_type = type_map.get(turn_type, turn_type)

    # 执行调用
    chain = prompt | structured_llm
    try:
        response = chain.invoke({
            "system_instructions": sys_prompt,
            "phase": cn_phase,
            "turn_type": cn_turn_type,
            "game_summary": state.get("game_summary", ""),
            "history": history_str,
            "private_thoughts": private_thoughts_str
        }, config={"callbacks": [langfuse_handler]})
    except Exception as e:
        print(f"Error calling LLM: {e}")
        response = None

    # 处理 None 响应（兜底逻辑）
    if response is None:
        if phase == "night" or turn_type in ["hunter_shoot", "sheriff_transfer"]:
            response = NightAction(thought="系统异常，选择跳过行动。", action_type="pass", target_id=None)
        else:
            response = AgentOutput(thought="思考中...", speech="我暂时没有什么想说的。", action=None, target_id=None)
    
    # 更新 Player 私有状态
    # 为了并行合并，只返回被修改的玩家对象
    current_player = next(p for p in state["players"] if p.id == current_id)
    # 使用 model_copy 确保在并行环境下状态隔离
    new_player = current_player.model_copy(deep=True)
    new_player.private_thoughts.append(response.thought)
            
    updates: Dict[str, Any] = {
        "players": [new_player],
        "last_thought": response.thought,
        "last_action": response.action if hasattr(response, 'action') else (response.action_type if hasattr(response, 'action_type') else None),
        "last_target": response.target_id if hasattr(response, 'target_id') else None
    }
    
    if phase == "night" or turn_type == "hunter_shoot":
        updates["night_actions"] = {turn_type: response.target_id}
    elif turn_type == "sheriff_transfer":
        # 复用 night_actions 存储移交决策
        target = response.target_id if response.action_type == "transfer_badge" else None
        updates["night_actions"] = {"sheriff_transfer": target}
    else:
        # 白天发言 (仅在非并行环节且有发言内容时记录)
        # 并行环节（如投票、上警报名）仅执行决策和内心思考，不产生公屏发言
        parallel_types = ["voting", "pk_voting", "sheriff_nomination", "sheriff_voting"]
        if response.speech and turn_type not in parallel_types:
            msg = Message(role=player.role, content=response.speech, player_id=player.id)
            updates["history"] = [msg] 
        
        # 处理投票 (含 PK 投票)
        if turn_type in ["voting", "pk_voting"]:
            target_id = response.target_id if hasattr(response, 'target_id') else None
            updates["votes"] = {player.id: target_id}

        # 处理警长竞选
        if turn_type == "sheriff_nomination":
            if response.action == "run":
                updates["election_candidates"] = [player.id]
            elif response.action == "quit_election":
                # 退水逻辑在并行阶段通常不适用，除非是后续环节
                # 这里简单处理：如果确实触发了，则在 history 中体现，GM 会处理
                msg = Message(role="system", content=f"【系统公告】玩家 {player.id} 宣布退水，退出警长竞选。")
                if "history" in updates:
                    updates["history"].append(msg)
                else:
                    updates["history"] = [msg]
                # 注意：并行环境下从 list 移除比较麻烦，通常是通过 GM 在 settle 时判定

        # 处理投警长
        if turn_type == "sheriff_voting":
            target_id = response.target_id if hasattr(response, 'target_id') else None
            updates["votes"] = {player.id: target_id}

        # 处理发言顺序指定 (警长权力)
        if turn_type == "discussion" and player.id == state.get("sheriff_id"):
            if response.action in ["clockwise", "counter_clockwise"]:
                updates["speech_order_preference"] = response.action

    return updates
