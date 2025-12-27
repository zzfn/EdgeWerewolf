# -*- coding: utf-8 -*-
import os
import sys

# 将项目根目录添加到 python 路径，修复 ModuleNotFoundError
sys.path.append(os.getcwd())

from dotenv import load_dotenv
from src.agent.graph import workflow
from langfuse.langchain import CallbackHandler
from langgraph.checkpoint.sqlite import SqliteSaver

# 加载环境变量
load_dotenv()

def run_simulation():
    """运行狼人杀 AI 对局模拟 (12人标准局 + 上帝视角日志)"""
    print("\n" + "="*50)
    print(" 🐺  AI 狼人杀 - 上帝视角控制台 (God-View Console)  🐺 ")
    print("="*50 + "\n")
    
    langfuse_handler = CallbackHandler()
    thread_id = os.getenv("MATCH_THREAD_ID", "auto_match_v5") # 升级版本以防状态冲突
    
    print(f"🔹 会话 ID: {thread_id}")
    print(f"🔹 持久化: checkpoints.sqlite")
    print("-" * 50)

    with SqliteSaver.from_conn_string("checkpoints.sqlite") as saver:
        graph = workflow.compile(checkpointer=saver)
        config = {
            "configurable": {"thread_id": thread_id}, 
            "recursion_limit": 100,
            "callbacks": [langfuse_handler],
            "run_name": "AI-Werewolf-Match"
        }
        
        initial_inputs = {}
        
        try:
            for event in graph.stream(initial_inputs, config):
                for node_name, output in event.items():
                    # 1. 打印基础节点进度
                    print(f"\n[系统流水] {node_name} 正在执行...", end=" ", flush=True)

                    # 2. 上帝视角：透传心理活动和秘密动作 (来自 player_agent)
                    if node_name == "player_agent" and "last_thought" in output:
                        print("🤖 AI 思考完成")
                        print(f"   💭 【内心独白】: {output['last_thought']}")
                        if output.get("last_action"):
                            target_str = f" -> 目标: {output['last_target']}" if output.get("last_target") else ""
                            print(f"   🎯 【隐秘动作】: {output['last_action']}{target_str}")

                    # 3. 游戏内正式消息 (History)
                    new_messages = output.get("history", [])
                    if new_messages:
                        print("\n" + "—"*30 + "【公屏发言】" + "—"*30)
                        for msg in new_messages:
                            if msg.player_id:
                                # 给不同角色简单的图标标识
                                icon = "🧛" if msg.role == "werewolf" else "👤"
                                print(f"{icon} [玩家 {msg.player_id}] ({msg.role}): {msg.content}")
                            else:
                                print(f"📢 {msg.content}")
                        print("—"*70)
                    
                    # 4. 上帝实时总结播报 (来自 action_handler)
                    if node_name == "action_handler" and "game_summary" in output:
                        print("\n" + "📜 " + "—"*20 + "【上帝对局总结】" + "—"*20)
                        print(f"   {output['game_summary']}")
                        print("—"*68)

                    # 5. 游戏结束判定
                    if output.get("game_over"):
                        print("\n" + "🏁 " + "*"*20 + " 游戏总结 " + "*"*20)
                        print(f"🏆 获胜方: 【{'狼人' if output['winner_side'] == 'werewolf' else '好人'}】")
                        print("*"*50 + "\n")
                        return

        except Exception as e:
            print(f"\n❌ 运行出错: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    run_simulation()
