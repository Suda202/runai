RunAI.one Claude Agent SDK 技术架构文档
版本：v2.0
更新：2026-01-14
定位：Claude Agent SDK + MCP Server 的详细技术设计

---

## 1. 系统概述

### 1.1 产品定位

运动垂类的深度研究 Agent，专注于跑步装备推荐（以跑鞋为主）。

- 目标市场：美国市场优先
- 目标用户：
  - 跑步小白：刚开始跑步，不了解装备
  - 进阶跑者：有基础，追求配速提升
  - 资深跑者：明确需求，快速比价

### 1.2 核心能力

- **搜索先行**：基于 Tavily 和 Google Shopping 的实时搜索验证
- **专家系统**：领域知识指导搜索策略，而非替代搜索
- **可信来源**：RunRepeat（评测）+ Reddit（口碑）+ Google Shopping（价格/链接）
- **结构化输出**：6 板块买家指南格式

### 1.3 技术栈

| 组件 | 技术选型 |
|------|----------|
| 核心框架 | Claude Agent SDK (Node.js) |
| 工具注册 | createSdkMcpServer (MCP Server) |
| 搜索 API | Tavily (评测/口碑), SerpAPI (Google Shopping) |
| Schema 定义 | Zod (运行时验证) |
| LLM | MiniMax-M2.1 (Anthropic 兼容接口) |

---

## 2. 系统架构

### 2.1 架构图

```
RunAI.one Agent (Claude Agent SDK)
    │
    ├── Agent Core
    │   ├── query() - SDK 核心调用
    │   ├── createSdkMcpServer() - MCP 工具注册
    │   └── System Prompt (领域知识)
    │
    ├── Tools (MCP Server)
    │   ├── tavily_search - 评测搜索 / Reddit 口碑
    │   └── google_shopping - 商品价格 / 购买链接
    │
    └── Output
        └── 买家指南（6板块）
```

### 2.2 组件说明

#### 2.2.1 Agent Core

**配置示例**：
```javascript
const config = {
  // 领域知识
  systemPrompt: RUNNING_SHOES_PROMPT,

  // 模型配置（MiniMax Anthropic 兼容）
  model: 'MiniMax-M2.1',

  // Agent 循环
  maxTurns: 15,

  // 权限模式
  permissionMode: 'bypassPermissions',
  allowDangerouslySkipPermissions: true,

  // 环境变量
  env: {
    PATH: process.env.PATH,
    ANTHROPIC_API_KEY: process.env.MINIMAX_API_KEY,
    ANTHROPIC_BASE_URL: 'https://api.minimaxi.com/anthropic',
    TAVILY_API_KEY: process.env.TAVILY_API_KEY,
    SERPAPI_KEY: process.env.SERPAPI_KEY,
  },

  // MCP Server 注册
  mcpServers: {
    'running-shoe-tools': runningShoeTools
  },

  // 显式允许的工具
  allowedTools: ['tavily_search', 'google_shopping'],
};
```

#### 2.2.2 Tools (MCP Server)

**工具注册方式**：
```javascript
import { createSdkMcpServer } from 'claude-agent-sdk';

const runningShoeTools = createSdkMcpServer({
  name: 'running-shoe-tools',
  version: '1.0.0',
  tools: [
    {
      name: 'tavily_search',
      description: '...',
      inputSchema: { query: z.string(), max_results: z.number().int().default(5) },
      handler: tavilySearchHandler
    },
    {
      name: 'google_shopping',
      description: '...',
      inputSchema: { query: z.string(), max_price: z.number().int().optional() },
      handler: googleShoppingHandler
    }
  ]
});
```

**关键点**：
- 使用 `inputSchema` (驼峰命名)，不是 `input_schema`
- Schema 使用 Zod 定义，不是 JSON Schema
- 自定义工具必须通过 `createSdkMcpServer` + `mcpServers` 注册

---

## 3. 工具详情

### 3.1 tavily_search

**用途**：专业评测搜索、Reddit 口碑获取

**定义**：
```javascript
export const tavilySearchTool = {
  name: 'tavily_search',
  description: `Search the web using Tavily API. Best for:
- Running shoe reviews from RunRepeat, Believe in the Run, Doctors of Running
- Reddit discussions from r/running, r/runningshoegeeks
- Expert comparisons and analysis

Tips:
- Add "site:runrepeat.com" for professional reviews
- Add "site:reddit.com/r/running" for user feedback`,
  inputSchema: {
    query: z.string().describe('Search query. Can include site: prefix.'),
    max_results: z.number().int().default(5).describe('Max results (default 5, max 10)')
  },
  handler: tavilySearchHandler
};
```

**搜索示例**：
```javascript
// 评测搜索
tavily_search({ query: 'HOKA Bondi 8 review site:runrepeat.com' })

// Reddit 口碑
tavily_search({ query: 'Nike Pegasus 41 heavy runner site:reddit.com/r/running' })

// 对比分析
tavily_search({ query: 'Bondi 8 vs Nimbus 26 cushioning comparison' })
```

### 3.2 google_shopping

**用途**：商品价格、购买链接（**必须使用**）

**定义**：
```javascript
export const googleShoppingTool = {
  name: 'google_shopping',
  description: `Search Google Shopping for running shoe prices and purchase links (US market).

Returns for each product:
- Product name and price (USD)
- Purchase link to retailer
- Rating and review count
- Retailer/source name

Use this tool when you need:
- Current market prices
- Where to buy specific shoes
- Price comparisons across retailers`,
  inputSchema: {
    query: z.string().describe('Product search query (e.g., "HOKA Bondi 8 mens")'),
    max_price: z.number().int().optional().describe('Max price filter in USD'),
    min_price: z.number().int().optional().describe('Min price filter in USD')
  },
  handler: googleShoppingHandler
};
```

**重要**：每次推荐前必须调用，用户需要可点击的购买链接。

---

## 4. System Prompt 设计

### 4.1 核心理念

```
你是专家，但必须通过搜索来验证和更新知识
```

专家价值体现在：
1. **知道该搜什么** - 精准定位信息源（RunRepeat、Reddit、Solereview）
2. **会解读数据** - 综合多源，识别矛盾，找可靠结论
3. **给出建议** - 基于搜索结果，结合用户需求

### 4.2 工作流程

#### 步骤1：理解需求（仅在极度信息不足时追问）

**追问规则**：
- 有明确症状（膝盖疼、扁平足）→ 直接搜索，不追问
- 有预算或用途 → 直接搜索，不追问
- **只有当用户仅说"推荐跑鞋"且无任何其他信息时**，才追问：
  1. 预算范围？
  2. 主要用途？

**原则**：宁可基于有限信息推荐通用选择，也不要过度追问。

#### 步骤2：执行针对性搜索

| 用户需求 | 搜索策略 |
|----------|----------|
| 大体重缓震 | `max cushion heavy runner [体重]kg site:runrepeat.com` |
| 扁平足支撑 | `stability shoes overpronation site:solereview.com` |
| 宽脚 | `wide toe box running shoes site:solereview.com` |
| 慢速碳板 | `[鞋款] minimum pace requirement site:reddit.com` |

#### 步骤3：综合搜索结果推荐

每条推荐必须：
- 引用具体来源（RunRepeat 评分、Reddit 链接）
- 说明推荐理由（基于搜索结果）
- 诚实说明缺点

#### 步骤4：查询价格和购买链接（必须执行！）

对每款推荐鞋，**必须**调用 google_shopping：
```javascript
google_shopping({ query: "HOKA Bondi 8 mens" })
```

**为什么必须？** 用户需要直接点击购买，没有链接的推荐是无效的。

### 4.3 输出格式

```markdown
### 1. 需求分析
简述关键需求（1-2句话）

### 2. 搜索过程
说明搜索了什么（让用户知道信息来源）

### 3. 推荐方案
**[鞋款名]** - $[价格]（来自 google_shopping）
- **来源**：[RunRepeat 评分 / Reddit 链接]
- **推荐理由**：...
- **用户反馈**：...
- **诚实缺点**：...
- **购买链接**：[必须是可点击的购买链接]

### 4. 备选方案
2-3款对比，每款含理由

### 5. 避坑提示
基于搜索结果，说明哪些鞋款不适合
- 必须引用来源："根据 [Reddit讨论]，[鞋款] 不适合..."

### 6. 信息来源
列出所有搜索结果链接
```

### 4.4 禁止行为

❌ 不搜索就推荐具体鞋款
❌ 编造来源或评价
❌ 依赖过时的训练数据
❌ 忽略搜索结果中的负面反馈
❌ 不调用 google_shopping 就给出价格或购买链接

---

## 5. 项目结构

```
runai-v2/
├── index.mjs             # 入口（测试用例）
├── agent.mjs             # Agent 配置（createSdkMcpServer）
├── prompts/
│   └── running-shoes-v3.mjs   # 领域 System Prompt
└── tools/
    ├── tavily.mjs        # Tavily 搜索实现
    └── shopping.mjs      # Google Shopping 实现
```

---

## 6. 工具调用统计

为了监控 Agent 行为，实现了工具调用统计：

```javascript
const toolCallStats = {
  calls: [],
  reset() { this.calls = []; },
  record(name, args) { this.calls.push({ name, args, timestamp: Date.now() }); },
  get count() { return this.calls.length; },
  get summary() { return this.calls.map(c => c.name).join(', ') || 'none'; }
};

function wrapHandler(name, handler) {
  return async (args, extra) => {
    toolCallStats.record(name, args);
    return handler(args, extra);
  };
}
```

**输出示例**：
```
[Complete]
  Tool Calls: 4 (tavily_search, tavily_search, google_shopping, google_shopping)
  Cost: $0.015234
  Duration: 12500ms
```

---

## 7. 环境配置

```bash
# .env（根目录）
MINIMAX_API_KEY=xxx              # MiniMax API（Anthropic 兼容）
MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic
LLM_MODEL=MiniMax-M2.1

SERPAPI_KEY=xxx                  # Google Shopping
TAVILY_API_KEY=xxx               # Tavily 搜索
```

---

## 8. 关键技术决策

### 8.1 为什么用 Claude Agent SDK?

| 对比项 | Dify | Claude Agent SDK |
|--------|------|------------------|
| 控制力 | 低，黑盒 | 高，代码可控 |
| 调试 | 困难 | 直接 Debug |
| 工具扩展 | 有限 | 无限（MCP Server） |
| 学习价值 | 低 | 高 |

### 8.2 为什么用 Zod 而非 JSON Schema?

- Claude Agent SDK 内部使用 Zod 进行运行时验证
- Zod 提供类型推断和 IDE 支持
- 更简洁的语法

### 8.3 为什么用 MiniMax 而非 Anthropic 直连?

- 成本更低
- API 完全兼容 Anthropic
- 国内访问更稳定

### 8.4 为什么 tavily_search 而非 web_search?

- Tavily 专为 AI 搜索优化，返回结构化结果
- 自带 Answer 摘要功能
- 无需处理 HTML 解析

---

## 9. ODR 参考特性（待实现）

参考 Open Deep Research 架构，以下特性可考虑：

1. **结构化商品信息**：图片、价格、购买链接的统一格式
2. **混合并行策略**：同时搜索评测和价格
3. **搜索结果缓存**：减少重复 API 调用
4. **Supervisor-Researcher 模式**：复杂查询的分层处理

---

## 10. 验收标准

| 场景 | 期望行为 |
|------|----------|
| 新手 + 预算 $150 | 直接搜索，推荐入门缓震鞋，含购买链接 |
| "我膝盖疼" | 直接搜索护膝跑鞋，不追问 |
| "推荐跑鞋" | 追问预算和用途（最多2问） |
| 每次推荐 | 必须有 google_shopping 返回的价格和链接 |
| 避坑提示 | 必须引用 Reddit/RunRepeat 来源 |

**质量指标**：
- 工具调用次数：3-6 次/查询
- 响应时间：< 30 秒
- 推荐准确率：80%+

---

## 11. 参考资料

- [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk)
- [Tavily API](https://docs.tavily.com/)
- [SerpAPI - Google Shopping](https://serpapi.com/google-shopping-api)
- [Zod Schema](https://zod.dev/)
- [MiniMax API](https://www.minimax.io/)
