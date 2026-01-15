"""RunAI Agent 工具定义 - Tavily 搜索 & Google Shopping
[I N P U T]: 依赖 os.environ 的 API keys (TAVILY_API_KEY, SERPAPI_KEY)
[O U T P U T]: 对外提供 tavily_search, google_shopping 异步函数
[P O S]: runai-v2/ 的工具层，处理所有外部 API 调用
[P R O T O C O L]: 变更时更新此头部，然后检查 CLAUDE.md
"""

import os
import json
import asyncio
import httpx
from typing import Any
from claude_agent_sdk import tool

from config import (
    TAVILY_CONCURRENCY,
    TAVILY_TIMEOUT,
    TAVILY_MAX_RESULTS,
    TAVILY_HIGH_PRIORITY_SOURCES,
    SHOPPING_CONCURRENCY,
    SHOPPING_TIMEOUT,
    SHOPPING_RETRY_ATTEMPTS,
    SHOPPING_RETRY_DELAY,
    SHOPPING_MAX_PRODUCTS,
    logger,
)


def parse_list_param(value: Any) -> list | None:
    """解析可能是 JSON 字符串或普通字符串的 list 参数"""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        # 尝试解析 JSON 数组
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
        # 普通字符串包装成单元素列表
        if value.strip():
            return [value.strip()]
    return None


@tool(
    "tavily_search",
    """Search the web using Tavily API. Best for:
- Running shoe reviews from RunRepeat, Believe in the Run, Doctors of Running
- Reddit discussions from r/running, r/runningshoegeeks
- Expert comparisons and analysis

Supports:
- Batch queries (queries: list[str]) with internal concurrency
- Priority sources (sources: list[str] or "high_priority")

Tips:
- Use "vs" for comparisons (e.g., "Bondi 8 vs Nimbus 26")
- Add sources="high_priority" for prioritized reviews from RunRepeat, Reddit, etc.""",
    {
        "queries": list,
        "sources": list,
        "max_results": int,
    },
)
async def tavily_search(args: dict[str, Any]) -> dict[str, Any]:
    """Search using Tavily API, supports batch queries with internal concurrency and priority sources"""
    queries = parse_list_param(args.get("queries"))
    sources = args.get("sources")
    max_results = args.get("max_results", TAVILY_MAX_RESULTS)

    # Validate queries
    if not queries:
        return {"content": [{"type": "text", "text": "Error: queries is required and must be a list (got: " + str(type(args.get("queries"))) + ")"}]}

    targets = [s.strip() for s in queries if isinstance(s, str) and s.strip()]
    if not targets:
        return {"content": [{"type": "text", "text": "Error: queries must be a non-empty list of strings"}]}

    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return {"content": [{"type": "text", "text": "Error: TAVILY_API_KEY not configured"}]}

    try:
        async with httpx.AsyncClient() as client:
            sem = asyncio.Semaphore(TAVILY_CONCURRENCY)

            async def search_one(q: str) -> str:
                async with sem:
                    # Add source filter if specified
                    search_query = q
                    if sources and isinstance(sources, list):
                        site_filter = " OR ".join([f"site:{s}" for s in sources if s])
                        search_query = f"{q} ({site_filter})"
                    elif sources == "high_priority":
                        site_filter = " OR ".join([f"site:{s}" for s in TAVILY_HIGH_PRIORITY_SOURCES])
                        search_query = f"{q} ({site_filter})"

                    response = await client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": api_key,
                            "query": search_query,
                            "max_results": min(max_results, 10),
                            "include_answer": True,
                            "include_raw_content": False,
                            "include_images": False,
                        },
                        timeout=TAVILY_TIMEOUT
                    )
                    response.raise_for_status()
                    data = response.json()

                    output = f'## Search Results for "{q}"\n\n'
                    if data.get("answer"):
                        output += f"### Answer\n\n{data['answer']}\n\n"

                    for i, r in enumerate(data.get("results", []), 1):
                        output += f"**{i}. {r.get('title', 'N/A')}**\n"
                        output += f"URL: {r.get('url', 'N/A')}\n"
                        output += f"Score: {r.get('score', 0):.2f}\n"
                        output += f"{r.get('content', '')[:300]}\n\n---\n\n"
                    return output

            results = await asyncio.gather(*[search_one(t) for t in targets], return_exceptions=True)
            output = ""
            for r, t in zip(results, targets):
                if isinstance(r, Exception):
                    output += f'## Search Results for "{t}"\n\nError: {str(r)}\n\n'
                else:
                    output += r

            return {"content": [{"type": "text", "text": output}]}

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Tavily search failed: {str(e)}"}]}


@tool(
    "google_shopping",
    """Search Google Shopping for running shoe prices and purchase links (US market).

Input:
- queries (list): List of specific shoe model names, e.g. ["HOKA Bondi 9", "ASICS Gel-Nimbus 27"]
- max_price (int, optional): Maximum price filter
- min_price (int, optional): Minimum price filter

Returns:
- Product name and price (USD)
- Direct purchase links to retailers (Amazon, Zappos, etc.)
- Rating and review count

IMPORTANT: Only use specific shoe model names. Do NOT use generic terms like "best running shoes".""",
    {
        "queries": list,
        "max_price": int,
        "min_price": int,
    },
)
async def google_shopping(args: dict[str, Any]) -> dict[str, Any]:
    """Search Google Shopping via SerpAPI with two-step lookup, supporting batch queries with bounded concurrency and light retry"""
    queries = parse_list_param(args.get("queries"))
    max_price = args.get("max_price")
    min_price = args.get("min_price")

    if not queries:
        return {"content": [{"type": "text", "text": "Error: queries is required and must be a list of shoe names"}]}

    targets = [s.strip() for s in queries if isinstance(s, str) and s.strip()]
    if not targets:
        return {"content": [{"type": "text", "text": "Error: queries must be a non-empty list of strings"}]}

    api_key = os.environ.get("SERPAPI_KEY")
    if not api_key:
        return {"content": [{"type": "text", "text": "Error: SERPAPI_KEY not configured"}]}

    try:
        async with httpx.AsyncClient(timeout=SHOPPING_TIMEOUT) as client:
            sem = asyncio.Semaphore(SHOPPING_CONCURRENCY)

            async def get_with_retry(url: str, params: dict, attempts: int = SHOPPING_RETRY_ATTEMPTS) -> dict:
                """429 时短暂重试后降级返回错误，非 429 错误也会重试"""
                delay = SHOPPING_RETRY_DELAY
                last_exc: Exception | None = None
                for k in range(attempts):
                    try:
                        resp = await client.get(url, params=params)
                        if resp.status_code == 429:
                            if k < attempts - 1:
                                wait_time = delay * (k + 1)
                                logger.warning(f"Shopping API | 429 rate limited, retry in {wait_time}s...")
                                await asyncio.sleep(wait_time)
                                delay *= 1.5
                                continue
                            return {"error": "RATE_LIMIT", "detail": "Google Shopping API rate limited"}
                        resp.raise_for_status()
                        return resp.json()
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 429:
                            if k < attempts - 1:
                                await asyncio.sleep(delay)
                                continue
                            return {"error": "RATE_LIMIT", "detail": "Google Shopping API rate limited"}
                        raise
                    except Exception as e:
                        last_exc = e
                        if k < attempts - 1:
                            await asyncio.sleep(delay)
                            delay *= 1.6
                raise last_exc if last_exc else RuntimeError("request failed")

            async def handle_one(q: str) -> str:
                async with sem:
                    # Step 1: Google Shopping API - 获取商品列表和 product_id
                    params = {
                        "api_key": api_key,
                        "engine": "google_shopping",
                        "q": q,
                        "location": "United States",
                        "hl": "en",
                        "gl": "us",
                    }
                    if max_price or min_price:
                        tbs = "mr:1,price:1"
                        if min_price:
                            tbs += f",ppr_min:{min_price}"
                        if max_price:
                            tbs += f",ppr_max:{max_price}"
                        params["tbs"] = tbs

                    data = await get_with_retry("https://serpapi.com/search", params)
                    # 处理 429 降级情况
                    if data.get("error") == "RATE_LIMIT":
                        return f'## Google Shopping Results for "{q}"\n\n⚠️ **API Rate Limited** - Price lookup failed. Use Tavily to search for prices instead.\n\n'
                    if data.get("error"):
                        return f'## Google Shopping Results for "{q}"\n\nSerpAPI error: {data["error"]}\n'

                    products = data.get("shopping_results", [])[:SHOPPING_MAX_PRODUCTS]
                    if not products:
                        return f'## Google Shopping Results for "{q}"\n\nNo products found for "{q}"\n'

                    out = f'## Google Shopping Results for "{q}"\n\n'

                    # Step 2: Google Immersive Product API - 获取卖家直链
                    for i, p in enumerate(products, 1):
                        page_token = p.get("immersive_product_page_token")
                        title = p.get("title", "N/A")
                        price = p.get("price") or p.get("extracted_price") or "N/A"
                        source = p.get("source", "N/A")
                        rating = p.get("rating")
                        reviews = p.get("reviews", 0)
                        thumbnail = p.get("thumbnail", "")

                        out += f"### {i}. {title}\n"
                        if thumbnail:
                            out += f"![{title}]({thumbnail})\n"
                        out += f"**Price**: {price}\n"
                        out += f"**Source**: {source}\n"
                        if rating:
                            out += f"**Rating**: {rating} ({reviews} reviews)\n"

                        if page_token:
                            try:
                                detail_params = {
                                    "api_key": api_key,
                                    "engine": "google_immersive_product",
                                    "page_token": page_token,
                                    "hl": "en",
                                    "gl": "us",
                                }
                                detail_data = await get_with_retry("https://serpapi.com/search", detail_params)
                                # 提取卖家列表 (stores 在 product_results.stores)
                                stores = detail_data.get("product_results", {}).get("stores", [])
                                if stores:
                                    out += "**Purchase Links**:\n"
                                    for store in stores[:3]:
                                        name = store.get("name", "Unknown")
                                        price_s = store.get("price") or store.get("base_price") or "N/A"
                                        link = store.get("link", "N/A")
                                        out += f"  - [{name}]({link}) - {price_s}\n"
                                else:
                                    out += f"**Link**: {p.get('product_link') or 'N/A'}\n"
                            except Exception:
                                out += f"**Link**: {p.get('product_link') or 'N/A'}\n"
                        else:
                            out += f"**Link**: {p.get('product_link') or 'N/A'}\n"
                        out += "\n---\n\n"

                    return out

            results = await asyncio.gather(*[handle_one(t) for t in targets], return_exceptions=True)
            output = ""
            for r, t in zip(results, targets):
                if isinstance(r, Exception):
                    output += f'## Google Shopping Results for "{t}"\n\nError: {str(r)}\n\n'
                else:
                    output += r

            return {"content": [{"type": "text", "text": output}]}

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Google Shopping search failed: {str(e)}"}]}
