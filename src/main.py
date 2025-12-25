import os
from dotenv import load_dotenv
from src.agent.graph import graph
from src.utils.helpers import get_default_state

# 加载环境变量
load_dotenv()

def run_simulation():
    """运行狼人杀 AI 对局模拟 (零参数自动启动)"""
    print("--- 🐺 狼人杀 AI 对局开始 (标准 3-节点 架构) 🐺 ---")
    
    config = {"configurable": {"thread_id": "auto_match_1"}, "recursion_limit": 100}
    
    # 传递空字典，触发图内部的 init 节点进行初始化和身份分配
    initial_state = {}
    printed_history_len = 0

    try:
        for event in graph.stream(initial_state, config):
            for node_name, output in event.items():
                # 打印节点名（可选，方便调试）
                # print(f"\n[{node_name}]", end=" ")
                
                # 检查并打印游戏历史新消息
                current_history = output.get("history", [])
                if len(current_history) > printed_history_len:
                    for i in range(printed_history_len, len(current_history)):
                        msg = current_history[i]
                        # 格式化输出：[Player X] (角色): 内容
                        if msg.player_id:
                            print(f"\n【玩家 {msg.player_id}】({msg.role}): {msg.content}")
                        else:
                            # 系统/上帝公告
                            print(f"\n{msg.content}")
                    printed_history_len = len(current_history)
                
                if output.get("game_over"):
                    print(f"\n🏆 游戏结束！获胜方: 【{'狼人' if output['winner_side'] == 'werewolf' else '好人'}】")
                    return

    except Exception as e:
        print(f"\n❌ 运行出错: {e}")

if __name__ == "__main__":
    run_simulation()
