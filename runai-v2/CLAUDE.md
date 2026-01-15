# runai-v2/
> L2 | 父级: /CLAUDE.md | Updated: 2026-01-15

RunAI Agent Python 版本，基于 Claude Agent SDK + LangSmith。

## 架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         RunAI.one Agent 架构                              │
└─────────────────────────────────────────────────────────────────────────┘

                              用户查询
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Claude Agent SDK (Python)                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  ClaudeAgentOptions                                              │   │
│  │    • model: LLM_MODEL 环境变量（默认 Claude Sonnet 4.5）          │   │
│  │    • system_prompt: RUNNING_SHOES_PROMPT                        │   │
│  │    • max_turns: 15                                              │   │
│  │    • allowed_tools: [WebSearch*, tavily_search, google_shopping]│   │
│  │      * WebSearch 仅 Claude 模型可用                              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│                              ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Agent 循环 (最多 15 轮)                                         │   │
│  │    1. 思考 (ThinkingBlock)                                       │   │
│  │    2. 决定调用工具 / 直接回复                                     │   │
│  │    3. 执行工具 → 等待结果                                         │   │
│  │    4. 基于结果继续 / 结束                                         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
└──────────────────────────────│───────────────────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
┌─────────────────────────────┐   ┌─────────────────────────────┐
│      Tavily Search          │   │      Google Shopping        │
│  (MCP Custom Tool)          │   │  (MCP Custom Tool)          │
│                             │   │                             │
│  输入:                      │   │  输入:                      │
│  - queries: list[str]       │   │  - queries: list[str]       │
│  - sources?: list | str     │   │  - max_price?: int          │
│  - max_results?: int        │   │  - min_price?: int          │
│                             │   │                             │
│  输出:                      │   │  输出:                      │
│  - 评测文章                 │   │  - 产品名称 + 价格           │
│  - Reddit 用户反馈          │   │  - 零售商直链 (Zappos等)     │
│  - 权威来源链接             │   │  - 评分 + 评论数             │
│                             │   │                             │
│  API: Tavily API            │   │  API: SerpAPI               │
│                             │   │  - google_shopping          │
│  约束:                      │   │  - google_immersive_product │
│  • 批量查询 (queries) ✅    │   │                             │
│  • 英文搜索 ✅              │   │  约束:                      │
│                             │   │  • 批量查询 (queries) ✅    │
│                             │   │  • 禁止模糊查询 ✅           │
└─────────────────────────────┘   └─────────────────────────────┘
               │                               │
               └───────────────┬───────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         LangSmith Tracing                                │
│  • 追踪每次工具调用                                                      │
│  • 记录 Token 消耗                                                      │
│  • 可视化执行 Trace                                                     │
└─────────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
                         ┌──────────┐
                         │ 最终输出 │
                         └──────────┘
                           • 推荐方案
                           • 购买链接
                           • 避坑提示
                           • 信息来源

═══════════════════════════════════════════════════════════════════════════

                              工作流 (Tavily → 推理 → Shopping)

           ┌──────────────────────────────────────────────────────┐
           │                                                      │
           ▼                                                      │
    ┌──────────────┐        ┌──────────────┐        ┌──────────────┐
    │   Tavily     │   →    │   推理决策   │   →    │   Shopping   │
    │  搜索评测    │        │  收敛鞋款    │        │  查询价格    │
    │  用户口碑    │        │  列表        │        │  购买链接    │
    └──────────────┘        └──────────────┘        └──────────────┘
         最多 5 次               思考中列出              批量查询 1 次
                                候选列表
```

## 文件清单

```
agent.py      - Agent 主文件，System Prompt + 入口
tools.py      - 工具定义（tavily_search, google_shopping）
run_eval.py   - 评测脚本，从 test_cases.json 读取用例
```

## 依赖

```bash
# Claude Agent SDK (Python)
pip install claude-agent-sdk

# LangSmith 追踪
pip install langsmith>=0.6.0

# 其他
pip install httpx python-dotenv
```

**注意**：`claude-agent-sdk` 已内置 MCP Server 支持，不再需要单独的 `mcp` 包。

## 运行方式

```bash
# 单次查询
python agent.py "我体重90公斤，求推荐缓震好的跑鞋"

# 运行评测
python run_eval.py
```

## 工作流

### 1. 追问规则
**原则**：信息越完整，推荐越准确

**必问因素**：人群、性别、体重、预算、脚型、用途

**策略**：
- 缺失关键因素 → 一次性问，最多 4 个（工具限制）
- 用户已提 → 不要重复问

**症状/伤病**：
- 用户提了 → 问关键细节（位置、程度、时长）
- 用户没提 → 不追问

追问时直接输出问题，不调用工具。

### 2. 搜索语言
- **优先英文搜索**（专业评测质量高）
- **必要时中文补充**（国产品牌、国内价格、中文社区口碑）

### 3. 搜索工具优先级
| 模型 | WebSearch | tavily_search |
|------|-----------|---------------|
| Claude | ✅ 优先 | ✅ 备选/补充 |
| Minimax | ❌ 不可用 | ✅ 主力 |

代码通过 `is_claude_model()` 自动判断。

### 4. 搜索策略 - Agentic Search

**核心原则**：
1. **信息不足 → 追问**
2. **信息足够 → 迭代搜索**
   - 每轮搜索基于上一轮的结果
   - 粒度从大到小：了解可选鞋款 → 深挖评测 → 对比 → 价格
   - 动态决策，不预定义固定轮数

**Tavily 限制**：最多 5 轮（免费版限制）。

### 4. Tavily 批量搜索
把用户问题翻译成 2-4 个英文查询，一次传入。

### 5. 矛盾信息处理
搜索结果可能有矛盾评价，处理原则：
- 先推理判断（看来源质量、样本量、是否适用当前用户）
- 能判断就给明确结论，不要轻易说"有争议"
- 真的无法判断时才在缺点里标注争议点

**信息可信度判断**：
- **来源优先级**：专业评测 > Reddit/论坛 > 电商评价 > 单一案例
- **时效性**：近期评价 > 旧评价（跑鞋迭代快）
- **一致性**：多人一致 > 个案

**识别营销内容**（降低权重或忽略）：
- 只说优点不提缺点
- 过度使用"最好""完美""神器"等词
- 来源是品牌官网或明显软文
- 没有具体使用场景和数据支撑

### 6. Shopping 批量查询
单次调用获取所有候选鞋款的价格和链接。

### 7. 降级策略
- **Google Shopping 429** → 立即降级，用 Tavily 查价格
- **Shopping 完全失败** → 估算价格范围 + 提供购物平台建议

### 工具参数
```python
# Tavily
tavily_search(queries: list[str], sources?: list[str] | "high_priority", max_results?: int)

# Google Shopping
google_shopping(queries: list[str], max_price?: int, min_price?: int)
```

**注意**：Claude Agent SDK 可能将 list 参数序列化为 JSON 字符串，`tools.py` 中的 `parse_list_param()` 函数会自动处理。

**默认高优先级来源**（`sources: "high_priority"`）：
- 专业评测：RunRepeat、Solereview、Believe in the Run、Doctors of Running
- 用户口碑：Reddit r/runningshoegeeks、r/running、r/AskRunningShoeGeeks

### 输出格式
```
## 需求分析
1-2 句关键需求

## 推荐方案
**首选：鞋款名** - $价格（价格仅供参考）
- 推荐理由（引用来源）
- 诚实缺点
- 购买渠道：国内推荐京东/淘宝/得物，海外推荐 Amazon/Zappos/Running Warehouse

**次选/备选**...

如果只买一双，选 XXX。

## 避坑提示
不推荐的鞋款及原因

## 信息来源
引用的评测和讨论链接
```

## 关键配置

| 配置项 | 值 | 说明 |
|--------|----|-----|
| model | `LLM_MODEL` 环境变量 | 默认：`claude-sonnet-4-5-20250929` |
| max_turns | 15 | Agent 最大迭代轮次 |

## 环境变量

```bash
# .env（根目录）
# LLM_MODEL=MiniMax-M2.1                     # 可选：切换到 MiniMax（不支持 WebSearch）
SERPAPI_KEY=xxx                              # Google Shopping (SerpAPI)
TAVILY_API_KEY=xxx                           # Tavily 搜索
LANGSMITH_API_KEY=xxx                        # LangSmith 追踪
LANGSMITH_TRACING=true
LANGCHAIN_PROJECT=runai-eval
```

**模型切换**：
- 默认使用 Claude Sonnet 4.5（支持 WebSearch）
- 设置 `LLM_MODEL=MiniMax-M2.1` 切换到 MiniMax（仅支持 tavily_search）
- 代码通过 `is_claude_model()` 自动判断可用工具

[PROTOCOL]: 变更时更新此头部，然后检查 /CLAUDE.md
