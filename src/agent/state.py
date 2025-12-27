from typing import Annotated, List, Optional, Dict, Literal, Any
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
import operator
from pydantic import BaseModel, Field

class RoleClaim(BaseModel):
    player_id: int
    role: str
    day: int
    claimed_content: str

class EventRecord(BaseModel):
    day: int
    phase: str
    description: str

class VotingSummary(BaseModel):
    day: int
    turn_type: str
    details: str

class GameSummary(BaseModel):
    role_claims: List[RoleClaim] = Field(default_factory=list)
    major_events: List[EventRecord] = Field(default_factory=list)
    voting_records: List[VotingSummary] = Field(default_factory=list)
    key_suspicions: List[str] = Field(default_factory=list) # 关键怀疑关系：如“1号怀疑2号是狼”
    game_progress: str = "" # 对局整体进程的极简描述

def merge_summary(left: GameSummary, right: GameSummary) -> GameSummary:
    """对于总结，我们通常采取全量覆盖或者智能合并，这里简单化处理：新的直接覆盖旧的，因为总结节点会读取旧的数据"""
    return right

class Message(BaseModel):
    role: str
    content: str
    player_id: Optional[int] = None

class PlayerState(BaseModel):
    id: int
    role: str  # werewolf, villager, seer, witch, hunter, guard
    personality: Optional[str] = None # 玩家性格特点
    is_alive: bool = True
    private_history: List[Message] = Field(default_factory=list)
    private_thoughts: List[str] = Field(default_factory=list)

def merge_dict(left: Dict[Any, Any], right: Dict[Any, Any]) -> Dict[Any, Any]:
    """合并字典的 Reducer"""
    new_dict = left.copy()
    new_dict.update(right)
    return new_dict

def merge_players(left: List[PlayerState], right: List[PlayerState]) -> List[PlayerState]:
    """合并玩家列表的 Reducer，根据 ID 覆盖更新"""
    player_map = {p.id: p for p in left}
    for p in right:
        player_map[p.id] = p
    return sorted(list(player_map.values()), key=lambda x: x.id)

def merge_list(left: List[Any], right: List[Any]) -> List[Any]:
    """合并列表的 Reducer（去重并合并）"""
    return list(set(left) | set(right))

class GameState(TypedDict):
    # 基础信息
    players: Annotated[List[PlayerState], merge_players]
    alive_players: List[int]
    
    # 流程控制 (GM 控制点)
    phase: Literal["night", "day"]
    turn_type: str            # "guard_protect", "wolf_kill", "seer_check", "witch_action", "discussion", "voting"
    discussion_queue: List[int]
    current_player_id: Optional[int]
    parallel_player_ids: Optional[List[int]] # 用于并行调度的 ID 列表
    day_count: int
    
    # 公共信息 (追加模式)
    history: Annotated[List[Message], operator.add]
    game_summary: Annotated[GameSummary, merge_summary]  # 结构化对局总结（长期记忆）
    
    # 临时决策数据 (Action 消费点)
    night_actions: Annotated[Dict[str, Any], merge_dict] # {"wolf_kill": 5, ...}
    votes: Annotated[Dict[int, int], merge_dict]         # {投票者ID: 被投者ID}
    
    # 角色特殊状态 (由 Action 控制)
    witch_potions: Dict[str, bool] # {"save": True, "poison": True}
    last_guarded_id: Optional[int]
    hunter_can_shoot: bool
    
    # 判定结果 (由 GM/Action 更新)
    last_night_dead: List[int]
    last_execution_id: Optional[int]
    last_transfer_target: Optional[int]
    sheriff_id: Optional[int]
    pending_hunter_shoot: Optional[int]
    pending_last_words: List[int]          # 等待发表遗言的玩家 ID 列表
    pending_sheriff_transfer: bool        # 是否处于警徽移交环节
    pk_candidates: Annotated[List[int], merge_list]               # PK 环节的候选人列表
    speech_order_preference: Optional[Literal["clockwise", "counter_clockwise"]] # 警长指定的发言顺序
    election_candidates: Annotated[List[int], merge_list]
    game_over: bool
    winner_side: Optional[Literal["werewolf", "villager"]]
    
    # 上帝视角增强字段 (非对局核心状态，仅用于可视化显示)
    # 并行环节下，我们使用 lambda x, y: y 来允许覆盖而不报错（只取并行中最后一个完成的）
    last_thought: Annotated[Optional[str], lambda x, y: y]
    last_action: Annotated[Optional[str], lambda x, y: y]
    last_target: Annotated[Optional[int], lambda x, y: y]
