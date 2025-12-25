from typing import Annotated, List, Optional, Dict, Literal, Any
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
import operator

class Message(BaseModel):
    role: str
    content: str
    player_id: Optional[int] = None

class PlayerState(BaseModel):
    id: int
    role: str  # werewolf, villager, seer, witch, hunter, guard
    is_alive: bool = True
    private_history: List[Message] = Field(default_factory=list)
    private_thoughts: List[str] = Field(default_factory=list)

class GameState(TypedDict):
    # 基础信息
    players: List[PlayerState]
    alive_players: List[int]
    
    # 流程控制 (GM 控制点)
    phase: Literal["night", "day"]
    turn_type: str            # "guard_protect", "wolf_kill", "seer_check", "witch_action", "discussion", "voting"
    discussion_queue: List[int]
    current_player_id: Optional[int]
    day_count: int
    
    # 公共信息 (追加模式)
    history: Annotated[List[Message], operator.add]
    
    # 临时决策数据 (Action 消费点)
    night_actions: Dict[str, Any] # {"wolf_kill": 5, ...}
    votes: Dict[int, int]         # {投票者ID: 被投者ID}
    
    # 角色特殊状态 (由 Action 控制)
    witch_potions: Dict[str, bool] # {"save": True, "poison": True}
    last_guarded_id: Optional[int]
    hunter_can_shoot: bool
    
    # 判定结果 (由 GM/Action 更新)
    last_night_dead: List[int]
    sheriff_id: Optional[int]
    election_candidates: List[int]
    game_over: bool
    winner_side: Optional[Literal["werewolf", "villager"]]
