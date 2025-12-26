from src.agent.nodes.engine import game_master_node, action_handler_node
from src.agent.state import PlayerState

def test_gm_pk_logic():
    print("测试：检测到 PK 候选人后应进入 pk_discussion")
    players = [
        PlayerState(id=1, role="villager", is_alive=True),
        PlayerState(id=2, role="werewolf", is_alive=True),
        PlayerState(id=3, role="seer", is_alive=True),
        PlayerState(id=4, role="villager", is_alive=True),
        PlayerState(id=5, role="villager", is_alive=True),
    ]
    state = {
        "players": players,
        "alive_players": [1, 2, 3, 4, 5],
        "phase": "day",
        "turn_type": "voting_settle",
        "day_count": 1,
        "pk_candidates": [1, 2],
        "history": [],
        "night_actions": {},
        "votes": {},
        "sheriff_id": None
    }
    res = game_master_node(state, {})
    assert res["turn_type"] == "pk_discussion"
    assert res["discussion_queue"] == [1, 2]
    print("✅ 通过")

def test_gm_night_to_election_logic():
    print("测试：第一夜结束后，无警长应进入 sheriff_nomination (非公告)")
    players = [
        PlayerState(id=1, role="villager", is_alive=True),
        PlayerState(id=2, role="werewolf", is_alive=True),
        PlayerState(id=3, role="seer", is_alive=True),
        PlayerState(id=4, role="villager", is_alive=True),
        PlayerState(id=5, role="villager", is_alive=True),
    ]
    state = {
        "players": players,
        "alive_players": [1, 2, 3, 4, 5],
        "phase": "night",
        "turn_type": "night_settle",
        "day_count": 1,
        "history": [],
        "night_actions": {"wolf_kill": 1},
        "votes": {},
        "sheriff_id": None,
        "witch_potions": {"save": True, "poison": True}
    }
    res = action_handler_node(state, {})
    assert res["turn_type"] == "sheriff_nomination"
    print("✅ 通过")

def test_gm_election_to_announcement_logic():
    print("测试：第一天竞选结束后应进入 day_announcement")
    players = [
        PlayerState(id=1, role="villager", is_alive=True),
        PlayerState(id=2, role="werewolf", is_alive=True),
        PlayerState(id=3, role="seer", is_alive=True),
        PlayerState(id=4, role="villager", is_alive=True),
        PlayerState(id=5, role="villager", is_alive=True),
    ]
    state = {
        "players": players,
        "alive_players": [1, 2, 3, 4, 5],
        "phase": "day",
        "turn_type": "sheriff_settle",
        "day_count": 1,
        "pk_candidates": [],
        "history": [],
        "night_actions": {},
        "votes": {},
        "sheriff_id": 2
    }
    res = game_master_node(state, {})
    assert res["turn_type"] == "day_announcement"
    print("✅ 通过")

def test_gm_last_words_logic():
    print("测试：竞选公告后，若有死者应进入 last_words")
    players = [
        PlayerState(id=1, role="villager", is_alive=False),
        PlayerState(id=2, role="werewolf", is_alive=True),
        PlayerState(id=3, role="seer", is_alive=True),
        PlayerState(id=4, role="villager", is_alive=True),
        PlayerState(id=5, role="villager", is_alive=True),
    ]
    state = {
        "players": players,
        "alive_players": [2, 3, 4, 5],
        "phase": "day",
        "turn_type": "day_announcement",
        "day_count": 1,
        "pending_last_words": [1],
        "last_night_dead": [1],
        "history": [],
        "night_actions": {},
        "votes": {},
        "sheriff_id": 2
    }
    res = game_master_node(state, {})
    assert res["turn_type"] == "last_words"
    print("✅ 通过")

def test_gm_sheriff_order_logic():
    print("测试：警长指定逆时针发言顺序")
    players = [
        PlayerState(id=1, role="villager", is_alive=True),
        PlayerState(id=2, role="werewolf", is_alive=True),
        PlayerState(id=3, role="seer", is_alive=True)
    ]
    state = {
        "players": players,
        "alive_players": [1, 2, 3],
        "phase": "day",
        "turn_type": "day_announcement",
        "day_count": 2,
        "history": [],
        "night_actions": {},
        "votes": {},
        "sheriff_id": 2,
        "speech_order_preference": "counter_clockwise",
        "last_night_dead": []
    }
    res = game_master_node(state, {})
    assert res["turn_type"] == "discussion"
    assert res["discussion_queue"] == [1, 3, 2]
    print("✅ 通过")

if __name__ == "__main__":
    test_gm_pk_logic()
    test_gm_night_to_election_logic()
    test_gm_election_to_announcement_logic()
    test_gm_last_words_logic()
    test_gm_sheriff_order_logic()
