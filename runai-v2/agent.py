"""RunAI Agent - Python 版本 + LangSmith Tracing
[I N P U T]: 依赖 tools.py 的 tavily_search, google_shopping 工具
[O U T P U T]: 对外提供 run_agent() 异步函数，返回推荐结果字符串
[P O S]: runai-v2/ 的核心入口，承载 System Prompt + Agent 配置
[P R O T O C O L]: 变更时更新此头部，然后检查 CLAUDE.md
"""

import asyncio
import textwrap
from typing import Any
from dotenv import load_dotenv

from claude_agent_sdk import (
    ClaudeAgentOptions,
    query,
    create_sdk_mcp_server,
)
from claude_agent_sdk.types import (
    PermissionResultAllow,
    ToolPermissionContext,
)
from langsmith.integrations.claude_agent_sdk import configure_claude_agent_sdk

from tools import tavily_search, google_shopping
from config import LLM_MODEL, MAX_TURNS, SHOPPING_ENABLED, logger


# ============================================================
# 环境初始化 - Environment Setup
# ============================================================

load_dotenv()
configure_claude_agent_sdk()

# System Prompt
RUNNING_SHOES_PROMPT = textwrap.dedent("""
    你是 RunAI.one，跑鞋研究专家。

    ## 工具
    - **tavily_search**: queries (list[str] 或单个字符串)，英文搜索评测和口碑
    - **google_shopping**: queries (list[str])，查价格和购买链接

    **重要**：只使用上述工具，不要使用 WebSearch 或其他搜索工具。

    ## 追问
    必问因素：人群、性别、体重、预算、脚型、用途
    - 缺失 → 一次性问，最多 4 个，给出选项
    - 用户已提 → 不要重复问
    - 用户提了症状 → 追问位置/程度
    - 用户没提症状 → 不追问

    ## 搜索策略
    - 英文搜索
    - 信息足够即可输出，不要凑轮次
    - 价格查不到 → 估算 + "请自行搜索"

    ## 推理规则（核心）
    | 症状 | 需求参数 | 搜索关键词 |
    |------|----------|------------|
    | 膝盖内侧疼/足外翻 | 稳定性 | stability, guidance, overpronation |
    | 小腿前侧疼 | 高落差+顶级缓震 | high drop, max cushion |
    | 足底筋膜炎 | 僵硬滚动 | rocker, arch support, rigid forefoot |
    | 跟腱炎 | 低落差 | low drop, <6mm drop |
    | 扁平足 | 足弓支撑 | straight last, arch support, stability |
    | 高足弓 | 高缓震 | high cushion, neutral, soft midsole |
    | 宽脚 | 宽楦 | 2E, 4E, wide toe box |

    ## 矛盾信息处理
    专业评测 > 用户帖子 > 单一案例
    多人一致 > 个案
    近期评价 > 旧评价

    ## 输出格式
    需求分析（1-2句）

    推荐方案
    首选：鞋款名 - 价格（标注"价格仅供参考"）
    - 推荐理由（引用来源）
    - 诚实缺点
    - 购买链接或"请自行搜索"

    次选/备选...

    如果只买一双，选 XXX。

    避坑提示（引用来源）

    信息来源（链接）

    用中文回复。
    """).strip()


def create_ask_user_handler(mock_answers: dict[str, str] | None = None, profile: dict | None = None):
    """创建 AskUserQuestion 处理器

    Args:
        mock_answers: 预设回答，格式 {"问题关键词": "选项label"}
        profile: 用户画像，用于自动推断回答
    """
    async def can_use_tool(
        tool_name: str, input_data: dict, context: ToolPermissionContext
    ) -> PermissionResultAllow:
        if tool_name == "AskUserQuestion":
            answers = {}
            questions = input_data.get("questions", [])

            for q in questions:
                question_text = q.get("question", "")
                header = q.get("header", "")
                options = q.get("options", [])

                # 策略1: 从 mock_answers 匹配
                if mock_answers:
                    for key, value in mock_answers.items():
                        if key in question_text or key in header:
                            answers[question_text] = value
                            logger.info(f"MockAnswer | {header}: {value}")
                            break

                # 策略2: 从 profile 推断
                if question_text not in answers and profile:
                    inferred = infer_answer_from_profile(header, options, profile)
                    if inferred:
                        answers[question_text] = inferred
                        logger.info(f"InferAnswer | {header}: {inferred}")

                # 策略3: 默认选第一个选项
                if question_text not in answers and options:
                    answers[question_text] = options[0].get("label", "")
                    logger.info(f"DefaultAnswer | {header}: {answers[question_text]}")

            return PermissionResultAllow(
                updated_input={"questions": questions, "answers": answers}
            )

        # 其他工具自动允许
        return PermissionResultAllow(updated_input=input_data)

    return can_use_tool


def infer_answer_from_profile(header: str, options: list, profile: dict) -> str | None:
    """根据 profile 推断回答"""
    header_lower = header.lower()

    # 映射表：profile 字段 -> 问题 header 关键词
    mappings = {
        "weight": ["体重", "weight"],
        "experience": ["经验", "experience", "人群"],
        "foot_type": ["脚型", "足弓", "foot"],
        "pain_point": ["疼痛", "pain", "症状"],
        "scenario": ["用途", "路面", "场景", "scenario"],
        "budget": ["预算", "budget", "价格"],
    }

    for profile_key, keywords in mappings.items():
        if profile_key in profile:
            for kw in keywords:
                if kw in header_lower or kw in header:
                    # 找匹配的选项
                    profile_value = str(profile[profile_key]).lower()
                    for opt in options:
                        label = opt.get("label", "").lower()
                        desc = opt.get("description", "").lower()
                        if profile_value in label or profile_value in desc:
                            return opt.get("label")
                    # 没找到精确匹配，返回 profile 值让模型理解
                    return profile[profile_key]
    return None


async def run_agent(
    user_query: str,
    mock_answers: dict[str, str] | None = None,
    profile: dict | None = None,
) -> str:
    """Run the RunAI agent with a query

    Args:
        user_query: 用户查询
        mock_answers: 预设追问回答（评测用）
        profile: 用户画像（自动推断回答用）
    """
    # Create MCP server with tools
    tools = [tavily_search]
    allowed = ["mcp__running-shoe-tools__tavily_search", "AskUserQuestion"]

    if SHOPPING_ENABLED:
        tools.append(google_shopping)
        allowed.insert(1, "mcp__running-shoe-tools__google_shopping")

    tools_server = create_sdk_mcp_server(
        name="running-shoe-tools",
        version="1.0.0",
        tools=tools,
    )

    options = ClaudeAgentOptions(
        model=LLM_MODEL,
        system_prompt=RUNNING_SHOES_PROMPT,
        mcp_servers={"running-shoe-tools": tools_server},
        allowed_tools=allowed,
        max_turns=MAX_TURNS,
        can_use_tool=create_ask_user_handler(mock_answers, profile),
    )

    result_text = ""

    async def prompt_stream():
        yield {
            "type": "user",
            "message": {"role": "user", "content": user_query},
        }

    async for message in query(prompt=prompt_stream(), options=options):
        msg_type = type(message).__name__

        if msg_type == 'AssistantMessage' and hasattr(message, 'content'):
            content = message.content
            if isinstance(content, list):
                for block in content:
                    block_type = type(block).__name__
                    if hasattr(block, 'text'):
                        result_text += block.text + "\n"
                        logger.debug(f"Text | {block.text[:200]}..." if len(block.text) > 200 else f"Text | {block.text}")
                    elif block_type == 'ToolUseBlock':
                        logger.info(f"ToolCall | {block.name} → {str(block.input)[:100]}")
            elif isinstance(content, str):
                result_text += content + "\n"
                logger.debug(f"Text | {content}")
        elif msg_type == 'UserMessage' and hasattr(message, 'content'):
            for block in message.content:
                if hasattr(block, 'content'):
                    result_content = str(block.content)[:200]
                    logger.debug(f"ToolResult | {result_content}...")
        elif msg_type == 'ResultMessage' and hasattr(message, 'result') and message.result:
            result_text = message.result

    return result_text.strip()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        user_query = " ".join(sys.argv[1:])
    else:
        user_query = "我体重95公斤，膝盖有点疼，求推荐保护性最好的跑鞋"

    print(f"\n{'='*60}")
    print(f"[RunAI Agent - Python + LangSmith]")
    print(f"{'='*60}")
    print(f"\n[Query] {user_query}\n")

    result = asyncio.run(run_agent(user_query))

    print(f"\n{'='*60}")
    print("[Result]")
    print(f"{'='*60}")
    print(result)
