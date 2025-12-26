import asyncio
from src.agent.graph import graph
from src.agent.state import PlayerState

async def simulate_tie_and_pk():
    """模拟投票平票进入 PK 的场景"""
    print("\n--- 模拟开始：投票平票进入 PK ---")
    
    # 构造初始状态：3人存活，1号和2号平票
    players = [
        PlayerState(id=1, role="villager", is_alive=True),
        PlayerState(id=2, role="werewolf", is_alive=True),
        PlayerState(id=3, role="seer", is_alive=True),
    ]
    
    initial_state = {
        "players": players,
        "alive_players": [1, 2, 3],
        "phase": "day",
        "turn_type": "voting_settle",
        "day_count": 1,
        "history": [],
        "night_actions": {},
        "votes": {1: 2, 2: 1, 3: 2}, # 稍微修改一下，让 2 票给 2，1 票给 1？不对，要平票
        "votes": {1: 2, 2: 1}, # 3 弃票，1和2平票
        "sheriff_id": None,
        "pk_candidates": [],
        "pending_last_words": []
    }
    
    # 运行图
    config = {"recursion_limit": 50}
    final_state = await graph.ainvoke(initial_state, config)
    
    print(f"当前环节: {final_state['turn_type']}")
    print(f"PK 候选人: {final_state['pk_candidates']}")
    print(f"公告记录: {[m.content for m in final_state['history'] if m.role == 'system'][-1]}")
    
    # 验证是否进入 pk_discussion
    assert final_state["turn_type"] == "pk_discussion"
    assert final_state["pk_candidates"] == [1, 2]

async def simulate_last_words():
    """模拟死亡产生遗言的场景"""
    print("\n--- 模拟开始：夜晚死亡产生遗言 ---")
    
    players = [
        PlayerState(id=1, role="villager", is_alive=True),
        PlayerState(id=2, role="werewolf", is_alive=True),
    ]
    
    # 模拟 night_settle 发现 1 号死了
    initial_state = {
        "players": players,
        "alive_players": [1, 2],
        "phase": "night",
        "turn_type": "night_settle",
        "day_count": 1,
        "night_actions": {"wolf_kill": 1},
        "history": [],
        "votes": {},
        "sheriff_id": None
    }
    
    final_state = await graph.ainvoke(initial_state)
    print(f"当前环节: {final_state['turn_type']}")
    print(f"等待遗言列表: {final_state['pending_last_words']}")
    
    # 应该先公告，然后 GM 发现有遗言，切到 last_words
    assert final_state["turn_type"] == "last_words"
    assert 1 in final_state["pending_last_words"]

if __name__ == "__main__":
    asyncio.run(simulate_tie_and_pk())
    asyncio.run(simulate_last_words())
