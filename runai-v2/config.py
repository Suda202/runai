"""RunAI Agent 配置文件
[P O S]: runai-v2/ 的配置中心，所有可调参数集中管理
[P R O T O C O L]: 变更时更新此头部，然后检查 CLAUDE.md
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# 模型配置
# ============================================================
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-4-5-20250929")
MAX_TURNS = 15

# ============================================================
# Tavily 搜索配置
# ============================================================
TAVILY_CONCURRENCY = 4  # 并发查询数
TAVILY_TIMEOUT = 30.0   # 单次请求超时（秒）
TAVILY_MAX_RESULTS = 5  # 每次搜索返回结果数

# 高优先级来源
TAVILY_HIGH_PRIORITY_SOURCES = [
    # 专业评测
    "runrepeat.com",
    "solereview.com",
    "believeintherun.com",
    "doctorsofrunning.com",
    # Reddit 社区
    "reddit.com/r/runningshoegeeks",
    "reddit.com/r/running",
    "reddit.com/r/AskRunningShoeGeeks",
]

# ============================================================
# Google Shopping 配置（暂时禁用，SerpAPI 配额用完）
# ============================================================
SHOPPING_ENABLED = False  # 是否启用 Google Shopping
SHOPPING_CONCURRENCY = 2  # 并发查询数（降低以减少 429）
SHOPPING_TIMEOUT = 30.0   # 单次请求超时（秒）
SHOPPING_RETRY_ATTEMPTS = 2  # 重试次数
SHOPPING_RETRY_DELAY = 2.0   # 重试初始延迟（秒）
SHOPPING_MAX_PRODUCTS = 3    # 每个查询返回产品数

# ============================================================
# LangSmith 配置
# ============================================================
LANGSMITH_PROJECT = os.environ.get("LANGCHAIN_PROJECT", "runai-eval")

# ============================================================
# 日志配置
# ============================================================
import logging

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FORMAT = "[%(levelname)s] %(message)s"

def setup_logging():
    """配置全局日志"""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format=LOG_FORMAT,
    )
    return logging.getLogger("runai")

logger = setup_logging()
