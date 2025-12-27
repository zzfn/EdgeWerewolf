# -*- coding: utf-8 -*-
import os
import sys

# 将项目根目录添加到 python 路径，修复 ModuleNotFoundError
sys.path.append(os.getcwd())

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 注意: 目前主要通过 `langgraph dev` 启动，
# 详见 `langgraph.json` 及其配置的图入口。
