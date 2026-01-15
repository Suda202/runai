# RunAI.one 重构计划

> 基于 Claude Agent SDK，最大化复用 Claude Code 能力

---

## 1. 现状问题

### 1.1 架构问题

| 问题 | 现状 | 影响 |
|------|------|------|
| OODA 硬编码 | `core.py` 手动编排 4 阶段流程 | 限制 Agent 自主性 |
| 启发式规则 | `_heuristic_analysis()` 硬编码关键词 | 需要人工维护，不灵活 |
| 验证逻辑 | `_check_compatibility()` 硬编码鞋款列表 | 新鞋款需要改代码 |
| 两套实现 | Python + Node.js 并存 | 维护成本高 |
| Node.js 太弱 | `maxTurns: 1, tools: []` | 根本不是 Agent |

### 1.2 核心误区

**现状**：在 Agent 外部硬编码流程（编排式）
```python
# ❌ 错误做法
def run(self):
    self._analyze_needs()      # 步骤 1
    self._search_information() # 步骤 2
    self._validate_candidates()# 步骤 3
    self._compose_output()     # 步骤 4
```

**目标**：让 Agent 自主决定（自主式）
```javascript
// ✅ 正确做法
query({
    prompt: userQuery,
    options: {
        preset: 'claude_code',
        systemPrompt: DOMAIN_KNOWLEDGE,
        // Agent 自己决定搜什么、验证什么、什么时候停止
    }
})
```

---

## 2. 重构目标

### 2.1 核心原则

**先复现，再自定义**
- 使用 `preset: 'claude_code'` 继承 CC 完整能力
- 领域知识放在 System Prompt
- 只在必要时添加自定义工具

### 2.2 技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| 框架 | Claude Agent SDK (Node.js) | 官方支持，原生 tool use |
| 模型 | MiniMax（Anthropic 兼容） | 成本考虑 |
| 搜索 | Tavily API | WebSearch 不可用时的替代 |
| 商品 | SerpAPI Google Shopping | 价格和购买链接 |

### 2.3 工具策略

| 工具 | 来源 | 用途 |
|------|------|------|
| `Read/Write/Edit` | CC 内置 | 文件操作 |
| `Bash` | CC 内置 | 命令执行 |
| `WebFetch` | CC 内置 | 抓取页面内容 |
| `tavily_search` | **自定义** | 评测搜索、Reddit 口碑 |
| `google_shopping` | **自定义** | 商品价格、购买链接 |

---

## 3. 新架构设计

### 3.1 目录结构

```
shopping/
├── CLAUDE.md                    # 项目说明（保留）
├── REFACTOR_PLAN.md             # 本文档
├── package.json                 # Node.js 依赖
├── .env                         # 环境变量
│
├── src/
│   ├── index.mjs                # 主入口
│   ├── agent.mjs                # Agent 配置
│   ├── prompts/
│   │   └── running-shoes.mjs    # 跑鞋领域 System Prompt
│   └── tools/
│       ├── index.mjs            # 工具注册
│       ├── tavily.mjs           # Tavily 搜索
│       └── shopping.mjs         # Google Shopping
│
├── claude-agent-sdk/            # SDK（保留）
│
└── _deprecated/                 # 废弃代码（暂存）
    └── runai-agent/             # 旧 Python 实现
```

### 3.2 核心代码

#### `src/agent.mjs` - Agent 配置

```javascript
import { query } from '../claude-agent-sdk/sdk.mjs';
import { RUNNING_SHOES_PROMPT } from './prompts/running-shoes.mjs';
import { registerTools } from './tools/index.mjs';

export function createAgent(options = {}) {
  return {
    preset: 'claude_code',

    // 领域知识
    systemPrompt: RUNNING_SHOES_PROMPT,

    // 模型配置（MiniMax）
    model: process.env.LLM_MODEL || 'MiniMax-M2.1',

    // Agent 循环配置
    maxTurns: 15,

    // 权限
    permissionMode: 'bypassPermissions',
    allowDangerouslySkipPermissions: true,

    // 环境变量（API Keys）
    env: {
      ...process.env,
      ANTHROPIC_API_KEY: process.env.MINIMAX_API_KEY,
      ANTHROPIC_BASE_URL: process.env.MINIMAX_BASE_URL,
    },

    // 自定义工具
    tools: registerTools(),

    ...options,
  };
}

export async function runAgent(userQuery) {
  const config = createAgent();
  const q = query({ prompt: userQuery, options: config });

  for await (const message of q) {
    if (message.type === 'assistant') {
      console.log('[Agent]', message.content);
    }
    if (message.type === 'tool_use') {
      console.log('[Tool]', message.name, message.input);
    }
    if (message.type === 'result' && message.subtype === 'success') {
      return message.result;
    }
  }
}
```

#### `src/tools/tavily.mjs` - Tavily 搜索

```javascript
import fetch from 'node-fetch';

export const tavilySearchTool = {
  name: 'tavily_search',
  description: `Search the web using Tavily API. Use for:
- Running shoe reviews (site:runrepeat.com)
- Reddit discussions (site:reddit.com/r/running)
- Expert opinions and comparisons
Returns structured search results with titles, URLs, and content snippets.`,

  input_schema: {
    type: 'object',
    properties: {
      query: {
        type: 'string',
        description: 'Search query. Include site: prefix for specific sources.'
      },
      max_results: {
        type: 'integer',
        description: 'Maximum results to return (default: 5)',
        default: 5
      }
    },
    required: ['query']
  },

  async execute({ query, max_results = 5 }) {
    const response = await fetch('https://api.tavily.com/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: process.env.TAVILY_API_KEY,
        query,
        max_results,
        include_answer: true,
      })
    });

    const data = await response.json();

    return data.results.map(r => ({
      title: r.title,
      url: r.url,
      content: r.content,
    }));
  }
};
```

#### `src/tools/shopping.mjs` - Google Shopping

```javascript
import fetch from 'node-fetch';

export const googleShoppingTool = {
  name: 'google_shopping',
  description: `Search Google Shopping for running shoe prices and purchase links.
Returns product listings with:
- Product name
- Price (USD)
- Purchase link
- Rating and review count
Use for price comparison and finding where to buy.`,

  input_schema: {
    type: 'object',
    properties: {
      query: {
        type: 'string',
        description: 'Product search query (e.g., "Nike Pegasus 41")'
      },
      max_price: {
        type: 'integer',
        description: 'Maximum price filter in USD'
      }
    },
    required: ['query']
  },

  async execute({ query, max_price }) {
    const params = new URLSearchParams({
      api_key: process.env.SERPAPI_KEY,
      engine: 'google_shopping',
      q: query,
      location: 'United States',
      hl: 'en',
    });

    if (max_price) {
      params.append('tbs', `mr:1,price:1,ppr_max:${max_price}`);
    }

    const response = await fetch(`https://serpapi.com/search?${params}`);
    const data = await response.json();

    return (data.shopping_results || []).slice(0, 5).map(item => ({
      name: item.title,
      price: item.price,
      link: item.link,
      rating: item.rating,
      reviews: item.reviews,
      source: item.source,
    }));
  }
};
```

#### `src/prompts/running-shoes.mjs` - 领域 System Prompt

```javascript
export const RUNNING_SHOES_PROMPT = `你是 RunAI.one，专业的跑鞋研究助手。

## 核心能力

你可以使用以下工具进行研究：
- **tavily_search**: 搜索评测（RunRepeat）和用户口碑（Reddit）
- **google_shopping**: 搜索商品价格和购买链接

## 研究流程

当用户询问跑鞋推荐时，你应该：

1. **理解需求**：分析用户的体重、配速、症状、预算等
2. **搜索信息**：
   - 使用 google_shopping 获取价格和购买链接
   - 使用 tavily_search 搜索 RunRepeat 评测
   - 使用 tavily_search 搜索 Reddit 真实用户反馈
3. **验证推荐**：确保推荐符合用户需求，排除不适合的鞋款
4. **输出买家指南**

## 领域知识

### 缓震需求判断
- 大体重（85kg+）或膝盖疼 → 需要 Max Cushion
- 日常训练、无特殊症状 → Medium Cushion 即可
- 追求速度、比赛 → 可以牺牲缓震换轻量

### 支撑需求判断
- 扁平足、过度内旋 → 需要 Stability 支撑鞋
- 正常足弓 → Neutral 中性鞋即可
- 高足弓 → 避免过度支撑

### 常见鞋款定位
| 鞋款 | 定位 | 适合人群 |
|------|------|----------|
| HOKA Bondi | Max Cushion | 大体重、膝盖保护 |
| ASICS Nimbus | Max Cushion | 高里程、舒适优先 |
| Brooks Ghost | Medium Cushion | 日常训练、入门 |
| Nike Pegasus | Medium Cushion | 通用、性价比 |
| ASICS Kayano | Stability | 扁平足、过度内旋 |
| Brooks Adrenaline | Stability | 稳定支撑、GuideRails |

### 避坑规则
- **Nike Invincible**：大体重（90kg+）不稳定，容易崴脚
- **竞速碳板鞋**：不适合慢配速训练，缓震不足
- **停产型号**：注意检查是否还在售

## 用户分层

- **新手信号**："刚开始跑步"、"第一双跑鞋"、"beginner"
  → 用通俗语言解释，避免专业术语

- **进阶信号**：主动提配速、体重、PB 目标
  → 可用专业术语（drop、stack height、碳板）

## 输出格式

### 买家指南（6 板块）

1. **用户画像**：总结用户的关键需求
2. **最佳推荐**：
   - 产品名 + 价格 + 购买链接
   - 推荐理由（基于搜索结果）
   - 诚实缺点
3. **备选方案**：2-3 款对比
4. **真实用户反馈**：Reddit 口碑
5. **购买渠道**：链接和价格对比
6. **劝退提示**：哪些鞋款不适合该用户

### 信息来源

每条推荐必须标注来源：
- [RunRepeat] 评分 + 链接
- [Reddit] 用户反馈 + 链接
- [Google Shopping] 价格 + 购买链接

## 注意事项

- 不要说 "Great!" "Awesome!" 等空洞词汇
- 不要推荐避坑名单中的鞋款
- 每个推荐必须有理由和来源
- 如果搜索结果不足，诚实说明

---
今天的日期：${new Date().toISOString().split('T')[0]}
`;
```

#### `src/tools/index.mjs` - 工具注册

```javascript
import { tavilySearchTool } from './tavily.mjs';
import { googleShoppingTool } from './shopping.mjs';

export function registerTools() {
  return [
    tavilySearchTool,
    googleShoppingTool,
  ];
}

// 工具执行器
export async function executeTool(name, input) {
  const tools = {
    tavily_search: tavilySearchTool,
    google_shopping: googleShoppingTool,
  };

  const tool = tools[name];
  if (!tool) {
    throw new Error(`Unknown tool: ${name}`);
  }

  return await tool.execute(input);
}
```

#### `src/index.mjs` - 主入口

```javascript
import { runAgent } from './agent.mjs';
import dotenv from 'dotenv';

dotenv.config();

async function main() {
  const testCases = [
    '我体重95公斤，膝盖有点疼，求推荐保护性最好的鞋',
    '我是扁平足，容易过度内旋，预算1000元',
    '刚开始跑步，预算500-800，主要在公园跑',
  ];

  for (const query of testCases) {
    console.log('\n' + '='.repeat(60));
    console.log('[User]', query);
    console.log('='.repeat(60));

    const result = await runAgent(query);
    console.log('\n[Result]\n', result);
  }
}

main().catch(console.error);
```

---

## 4. 环境变量

```bash
# .env
# MiniMax API（Anthropic 兼容）
MINIMAX_API_KEY=your_minimax_key
MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic/v1/messages
LLM_MODEL=MiniMax-M2.1

# Tavily（搜索）
TAVILY_API_KEY=your_tavily_key

# SerpAPI（Google Shopping）
SERPAPI_KEY=your_serpapi_key
```

---

## 5. 迁移步骤

### Phase 1: 准备（Day 1）

- [ ] 创建 `src/` 目录结构
- [ ] 移动旧代码到 `_deprecated/`
- [ ] 更新 `.env` 配置

### Phase 2: 核心实现（Day 2-3）

- [ ] 实现 `src/agent.mjs` - Agent 配置
- [ ] 实现 `src/tools/tavily.mjs` - Tavily 工具
- [ ] 实现 `src/tools/shopping.mjs` - Shopping 工具
- [ ] 编写 `src/prompts/running-shoes.mjs` - 领域 Prompt

### Phase 3: 集成测试（Day 4）

- [ ] 测试工具调用是否正常
- [ ] 测试 Agent 循环是否工作
- [ ] 验证输出格式是否符合预期

### Phase 4: 优化（Day 5）

- [ ] 根据测试结果调整 Prompt
- [ ] 优化工具描述
- [ ] 处理边界情况

---

## 6. 验证标准

### 功能验证

| 测试场景 | 预期行为 |
|----------|----------|
| 大体重+膝盖疼 | 推荐 Max Cushion（Bondi/Nimbus） |
| 扁平足+内旋 | 推荐 Stability（Kayano/Adrenaline） |
| 新手+低预算 | 推荐入门鞋（Pegasus/Ghost） |
| 搜索不到 | 诚实说明，不编造 |

### 质量指标

- [ ] Agent 自主调用工具（无硬编码流程）
- [ ] 每条推荐有来源链接
- [ ] 避坑鞋款不出现在推荐中
- [ ] 响应时间 < 30s

---

## 7. 与旧架构对比

| 维度 | 旧架构 | 新架构 |
|------|--------|--------|
| 流程控制 | 硬编码 4 阶段 | Agent 自主决定 |
| 领域知识 | 代码中的规则函数 | System Prompt |
| 工具调用 | 确定性顺序 | LLM 自主选择 |
| 验证逻辑 | 硬编码关键词列表 | LLM 推理判断 |
| 可维护性 | 改规则需要改代码 | 改 Prompt 即可 |
| 灵活性 | 低（流程固定） | 高（Agent 自适应） |

---

## 8. 风险与应对

| 风险 | 应对方案 |
|------|----------|
| MiniMax 兼容性问题 | 测试 tool use 是否正常工作 |
| Tavily 搜索质量 | 调整搜索词，必要时加 site: 前缀 |
| Agent 循环过长 | 设置 maxTurns: 15，Prompt 中指导停止条件 |
| 推荐不准确 | 迭代优化领域 Prompt |

---

## 9. 后续优化方向

1. **Memory**：保存用户画像（体重、配速偏好）
2. **多轮对话**：支持追问和澄清
3. **训练计划**：扩展到训练计划生成
4. **Web UI**：构建前端界面

---

*文档版本：v1.0*
*创建日期：2026-01-14*
