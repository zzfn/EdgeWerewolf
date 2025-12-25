import os
from datetime import datetime
from typing import Dict, List, Any, Optional
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
    """根据角色生成特定的指令"""
    role = player.role
    if role == "werewolf":
        teammates = [str(p.id) for p in state["players"] if p.role == "werewolf" and p.id != player.id]
        return WOLF_INSTRUCTIONS.format(teammates=", ".join(teammates))
    elif role == "villager":
        return VILLAGER_INSTRUCTIONS
    elif role == "seer":
        history_msgs = [m.content for m in player.private_history if m.role == "system"]
        check_history = "\n - " + "\n - ".join(history_msgs) if history_msgs else "暂无记录"
        return SEER_INSTRUCTIONS.format(check_history=check_history)
    elif role == "witch":
        p = state["witch_potions"]
        save_status = "【可用】" if p.get("save") else "【已用完】"
        poison_status = "【可用】" if p.get("poison") else "【已用完】"
        status_str = f"解药：{save_status}, 毒药：{poison_status}"
        return WITCH_INSTRUCTIONS.format(potions_status=status_str)
    return ""

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
        role_specific_instructions=role_instr
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "{system_instructions}"),
        ("human", "当前对局状态：\n阶段：{phase}\n环节：{turn_type}\n公共历史：{history}\n你的私有想法：{private_thoughts}\n请输出你的决策。")
    ])
    
    # 结构化输出
    if phase == "night":
        structured_llm = llm.with_structured_output(NightAction, method="function_calling")
    else:
        structured_llm = llm.with_structured_output(AgentOutput, method="function_calling")
        
    # 构造历史字符串：显示玩家 ID 而非角色名，防止混淆发言者
    history_lines = []
    for m in state["history"][-20:]: # 增加到 20 条，保持更长记忆
        prefix = f"【玩家 {m.player_id}】" if m.player_id else "【系统公告】"
        history_lines.append(f"{prefix}: {m.content}")
    history_str = "\n".join(history_lines)
    
    private_thoughts_str = "\n".join(player.private_thoughts[-5:])
    
    # Langfuse 局部观测
    langfuse_handler = CallbackHandler()
    
    # 执行调用
    chain = prompt | structured_llm
    response = chain.invoke({
        "system_instructions": sys_prompt,
        "phase": phase,
        "turn_type": turn_type,
        "history": history_str,
        "private_thoughts": private_thoughts_str
    }, config={"callbacks": [langfuse_handler]})
    
    # 更新 Player 私有状态
    updated_players = state["players"]
    for p in updated_players:
        if p.id == current_id:
            p.private_thoughts.append(response.thought)
            break
            
    updates: Dict[str, Any] = {"players": updated_players}
    
    if phase == "night":
        updates["night_actions"] = {**state["night_actions"], turn_type: response.target_id}
    else:
        # 白天发言
        if response.speech:
            msg = Message(role=player.role, content=response.speech, player_id=player.id)
            updates["history"] = [msg] 
        
        # 如果是投票，更新投票数据
        if turn_type == "voting":
            target_id = response.target_id if hasattr(response, 'target_id') else None
            updates["votes"] = {**state["votes"], player.id: target_id}

        # 处理警长竞选报名
        if turn_type == "sheriff_nomination":
            if response.action == "run":
                current_candidates = list(state.get("election_candidates", []))
                if player.id not in current_candidates:
                    current_candidates.append(player.id)
                updates["election_candidates"] = current_candidates

        # 处理投警长
        if turn_type == "sheriff_voting":
            target_id = response.target_id if hasattr(response, 'target_id') else None
            updates["votes"] = {**state["votes"], player.id: target_id}

    return updates
