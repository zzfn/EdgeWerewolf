from typing import Literal, Optional
from pydantic import BaseModel, Field

class AgentOutput(BaseModel):
    """玩家决策的基本输出结构"""
    thought: str = Field(description="内心的真实逻辑推理，不公开")
    speech: str = Field(description="对场上其玩家说的话（仅在白天发言阶段有效）")
    action: Optional[str] = Field(description="具体的手游操作，如：投票、击杀、查验、quit_election（退水）、clockwise/counter_clockwise（指定发言方向）等")
    target_id: Optional[int] = Field(description="行动的目标玩家 ID")

class NightAction(BaseModel):
    """夜晚行动的具体输出结构"""
    thought: str = Field(description="行动时的思考逻辑")
    action_type: Literal["kill", "check", "protect", "save", "poison", "pass", "shoot", "transfer_badge", "rip_badge"]
    target_id: Optional[int] = Field(description="行动目标玩家 ID")

class DiscussionOutput(BaseModel):
    """白天发言的输出结构"""
    thought: str = Field(description="对当前局势的逻辑分析")
    speech: str = Field(description="实际发表的言论")

class VotingOutput(BaseModel):
    """投票阶段的输出结构"""
    thought: str = Field(description="投票理由")
    target_id: Optional[int] = Field(description="投票给哪个玩家的 ID，弃票则为 None")
