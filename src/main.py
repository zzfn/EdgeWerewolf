import os
from dotenv import load_dotenv
from src.agent.graph import graph
from src.agent.state import PlayerState

# 加载环境变量 (API Key)
load_dotenv()

def initialize_game():
    """初始化 12 人经典局配置"""
    # 定义角色
    roles = (
        ["werewolf"] * 4 + 
        ["villager"] * 4 + 
        ["seer", "witch", "hunter", "guard"]
    )
    
    # 创建玩家状态
    players = []
    names = [
        "阿尔法", "贝塔", "伽玛", "德尔塔", 
        "艾普西隆", "泽塔", "艾塔", "西塔", 
        "约塔", "卡帕", "兰姆达", "缪"
    ]
    
    for i, role in enumerate(roles):
        players.append(PlayerState(
            id=i + 1,
            name=names[i],
            role=role,
            is_alive=True,
            private_history=[],
            private_thoughts=[]
        ))
        
    # 初始化游戏状态
    initial_state = {
        "players": players,
        "alive_players": [p.id for p in players],
        "phase": "night",
        "turn_type": "guard_protect", # 从守卫开始
        "day_count": 1,
        "current_speaker_id": None,
        "history": [],
        "night_actions": {},
        "witch_potions": {"save": True, "poison": True},
        "last_guarded_id": None,
        "hunter_can_shoot": True,
        "last_night_dead": [],
        "game_over": False,
        "winner_side": None
    }
    
    return initial_state

def run_simulation():
    """运行游戏模拟"""
    state = initialize_game()
    print("--- 🐺 狼人杀 AI 对局开始 🐺 ---")
    print(f"参与人数: {len(state['players'])}")
    
    # 运行图形
    # 注意：在实际 LangGraph dev 中，你可以通过 Studio 观察。
    # 这里我们通过代码调用来模拟流程。
    
    # 为了演示，我们只运行几个步骤或直到结束
    config = {"configurable": {"thread_id": "match_1"}}
    
    # 使用 stream 模式观察每一步的输出
    for event in graph.stream(state, config):
        for node_name, output in event.items():
            print(f"\n[节点: {node_name}]")
            if "turn_type" in output:
                print(f"阶段: {output['phase']} | 动作: {output['turn_type']}")
            
            # 如果有新的历史消息，打印出来
            if "history" in output and output["history"]:
                latest_msg = output["history"][-1]
                print(f">> {latest_msg.role} (玩家 {latest_msg.player_id}): {latest_msg.content}")
                
            if output.get("game_over"):
                print(f"\n🏆 游戏结束！获胜方: {output['winner_side']}")
                break

if __name__ == "__main__":
    run_simulation()
