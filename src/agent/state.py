from typing import Annotated, List, Optional, Dict, Literal
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
import operator

class Message(BaseModel):
    role: str
    content: str
    player_id: Optional[int] = None

class PlayerState(BaseModel):
    id: int
    name: str
    role: str  # werewolf, villager, seer, witch, hunter, guard
    is_alive: bool = True
    private_history: List[Message] = Field(default_factory=list)
    private_thoughts: List[str] = Field(default_factory=list)

class GameState(TypedDict):
    # 基础信息
    players: List[PlayerState]
    alive_players: List[int]
    
    # 流程控制
    phase: Literal["night", "day"]
    turn_type: str  # e.g., "werewolf_kill", "seer_check", "discussion", "voting"
    day_count: int
    current_speaker_id: Optional[int]
    
    # 公共信息
    history: Annotated[List[Message], operator.add]
    
    # 夜晚动作缓冲区
    night_actions: Dict[str, Optional[int]] # e.g., {"wolf_kill": 5, "seer_check": 3, "witch_save": 5}
    
    # 角色特殊状态
    witch_potions: Dict[str, bool] # {"save": True, "poison": True}
    last_guarded_id: Optional[int]
    hunter_can_shoot: bool
    
    # 判定结果
    last_night_dead: List[int]
    game_over: bool
    winner_side: Optional[Literal["werewolf", "villager"]]
