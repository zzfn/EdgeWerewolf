import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
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

# 加载环境变量
load_dotenv()

# 初始化 DeepSeek 模型
# DeepSeek API 兼容 OpenAI 格式
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
        teammates = [p.name for p in state["players"] if p.role == "werewolf" and p.id != player.id]
        return WOLF_INSTRUCTIONS.format(teammates=", ".join(teammates))
    elif role == "villager":
        return VILLAGER_INSTRUCTIONS
    elif role == "seer":
        # 获取该预言家的验人记录 (假设存放在 private_thoughts 或定制逻辑中)
        return SEER_INSTRUCTIONS.format(check_history="暂无")
    elif role == "witch":
        return WITCH_INSTRUCTIONS.format(potions_status=str(state["witch_potions"]))
    return ""

def player_node(state: GameState):
    """
    统一的玩家决策节点。
    """
    turn_type = state.get("turn_type")
    phase = state.get("phase")
    
    # 确定当前行动的玩家 ID
    # 这里逻辑可以根据 turn_type 细化
    current_player_id = state.get("current_speaker_id")
    
    # 如果是夜晚且没有指定 speaker，可能需要根据 turn_type 自动确定
    if phase == "night" and current_player_id is None:
        if turn_type == "wolf_kill":
            # 简化：只取第一个存活的狼人作为代表决策，或者循环所有狼人
            wolves = [p.id for p in state["players"] if p.role == "werewolf" and p.is_alive]
            current_player_id = wolves[0] if wolves else None
        elif turn_type == "seer_check":
            seers = [p.id for p in state["players"] if p.role == "seer" and p.is_alive]
            current_player_id = seers[0] if seers else None
        # ... 其他角色同理
        
    if current_player_id is None:
        return state

    # 获取玩家对象
    player = next(p for p in state["players"] if p.id == current_player_id)
    
    # 构造 Prompt
    role_instr = get_role_instructions(player, state)
    sys_prompt = BASE_SYSTEM_PROMPT.format(
        role=player.role,
        player_id=player.id,
        player_name=player.name,
        role_specific_instructions=role_instr
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", sys_prompt),
        ("human", "当前局势：\n公共历史：{history}\n你的私有想法：{private_thoughts}\n请输出你的决策。")
    ])
    
    # 选择输出 Schema
    if phase == "night":
        structured_llm = llm.with_structured_output(NightAction, method="function_calling")
    else:
        structured_llm = llm.with_structured_output(AgentOutput, method="function_calling")
        
    history_str = "\n".join([f"{m.role}: {m.content}" for m in state["history"][-10:]]) # 取最近10条
    private_thoughts_str = "\n".join(player.private_thoughts[-5:])
    
    chain = prompt | structured_llm
    response = chain.invoke({
        "history": history_str,
        "private_thoughts": private_thoughts_str
    })
    
    # 处理行动
    if phase == "night":
        # 存入夜晚动作缓冲区
        state["night_actions"][turn_type] = response.target_id
        # 记录内心思考到私有状态
        player.private_thoughts.append(response.thought)
    else:
        # 白天发言
        if response.speech:
            new_msg = Message(role=player.role, content=response.speech, player_id=player.id)
            state["history"].append(new_msg)
        player.private_thoughts.append(response.thought)
        
    return state
