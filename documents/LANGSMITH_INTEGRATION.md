# LangSmith 集成指南

## 概述

LangSmith 是 LangChain 提供的 LLM 应用追踪和监控平台，可以：

- 📊 **完整追踪**：记录每次 Agent 调用的输入、输出、耗时
- 💰 **成本分析**：统计 Token 使用和成本
- 🔍 **调试工具**：查看完整的执行链路和中间结果  
- 📈 **性能监控**：分析响应时间、成功率等指标
- 🏷️  **标签管理**：按场景、用户、会话等维度组织数据

---

## 快速开始

### 1. 安装依赖

```bash
npm install langsmith
```

### 2. 配置环境变量

创建 `.env` 文件并添加：

```bash
# LangSmith 配置
LANGCHAIN_API_KEY=lsv2_pt_your_api_key_here
LANGCHAIN_PROJECT=your-project-name
LANGCHAIN_TRACING_V2=true
```

获取 API Key:
1. 访问 https://smith.langchain.com/
2. 注册/登录账户
3. Settings → API Keys → Create API Key

### 3. 启用追踪

在应用启动时调用配置函数：

```javascript
import { configure_claude_agent_sdk } from './langsmith-config.mjs';

// 必须在任何 Agent 调用之前执行
configure_claude_agent_sdk();
```

### 4. 使用追踪包装器

```javascript
import { query } from './claude-agent-sdk/sdk.mjs';
import { traceAgentQuery } from './langsmith-config.mjs';

const queryParams = {
  prompt: '你的提示词',
  options: { /* ... */ },
};

const metadata = {
  name: 'my-agent-task',
  tags: ['shopping', 'recommendation'],
  user_id: 'user-123',
  session_id: 'session-456',
};

// 使用追踪包装器
for await (const message of traceAgentQuery(query, queryParams, metadata)) {
  // 处理消息...
}
```

---

## 架构设计

### 文件职责

```
langsmith-config.mjs          # 配置和追踪包装器
├── configure_claude_agent_sdk()  # 初始化 LangSmith 客户端
├── traceAgentQuery()             # Agent 查询追踪包装器
├── withTracing()                 # 通用函数追踪装饰器
└── getLangSmithClient()          # 获取客户端实例

agent-with-langsmith.mjs      # 集成示例
└── 演示如何在实际应用中使用追踪
```

### 核心原则

1. **非侵入性**：不修改原有 Agent 代码逻辑
2. **可选启用**：未配置 API Key 时自动降级为无追踪模式
3. **错误隔离**：追踪失败不影响 Agent 正常执行
4. **零开销**：未启用时无性能损耗

---

## API 参考

### `configure_claude_agent_sdk()`

初始化 LangSmith 客户端，必须在应用启动时调用。

**返回值**：
- `true`：初始化成功
- `false`：初始化失败（缺少 API Key 或配置错误）

**环境变量**：
- `LANGCHAIN_API_KEY`：LangSmith API Key（必需）
- `LANGCHAIN_PROJECT`：项目名称（可选）
- `LANGCHAIN_ENDPOINT`：API 端点（可选）

**示例**：

```javascript
import { configure_claude_agent_sdk } from './langsmith-config.mjs';

const enabled = configure_claude_agent_sdk();
if (enabled) {
  console.log('✅ LangSmith 追踪已启用');
} else {
  console.log('⚠️ LangSmith 未启用，将以无追踪模式运行');
}
```

---

### `traceAgentQuery(queryFn, queryParams, metadata)`

包装 Claude Agent SDK 的 `query` 函数，添加 LangSmith 追踪。

**参数**：
- `queryFn`：原始的 `query` 函数
- `queryParams`：query 参数对象
- `metadata`：追踪元数据对象
  - `name`：追踪名称（默认：'claude-agent-query'）
  - `tags`：标签数组（默认：['claude-agent-sdk']）
  - `user_id`：用户 ID（可选）
  - `session_id`：会话 ID（可选）
  - 其他自定义字段...

**返回值**：异步生成器，与原始 `query` 返回值相同

**示例**：

```javascript
const queryParams = {
  prompt: '推荐运动鞋',
  options: {
    model: 'anthropic/claude-sonnet-4',
    maxTurns: 3,
  },
};

const metadata = {
  name: 'shoe-recommendation',
  tags: ['shopping', 'shoes'],
  user_id: 'user-001',
  session_id: 'session-20240109',
  context: { budget: '500-800', experience: 'beginner' },
};

for await (const message of traceAgentQuery(query, queryParams, metadata)) {
  if (message.type === 'assistant') {
    console.log(message.message.content);
  }
}
```

---

### `withTracing(fn, name, tags)`

为任意异步函数添加 LangSmith 追踪的装饰器。

**参数**：
- `fn`：要追踪的函数
- `name`：追踪名称（默认使用函数名）
- `tags`：标签数组（默认：[]）

**返回值**：包装后的函数

**示例**：

```javascript
import { withTracing } from './langsmith-config.mjs';

async function fetchProductData(productId) {
  // 调用外部 API...
  return data;
}

// 包装函数以添加追踪
const tracedFetch = withTracing(
  fetchProductData,
  'fetch-product-data',
  ['api', 'product']
);

// 使用包装后的函数
const data = await tracedFetch('product-123');
```

---

## 实际应用示例

### 示例 1：运动鞋推荐 Agent

```javascript
import { query } from './claude-agent-sdk/sdk.mjs';
import { configure_claude_agent_sdk, traceAgentQuery } from './langsmith-config.mjs';

// 应用启动
configure_claude_agent_sdk();

async function recommendShoes(userProfile) {
  const queryParams = {
    prompt: `根据用户画像推荐运动鞋：${JSON.stringify(userProfile)}`,
    options: {
      model: 'anthropic/claude-sonnet-4',
      maxTurns: 2,
    },
  };

  const metadata = {
    name: 'shoe-recommendation',
    tags: ['shopping', 'recommendation'],
    user_id: userProfile.userId,
    session_id: userProfile.sessionId,
    user_profile: userProfile,
  };

  for await (const message of traceAgentQuery(query, queryParams, metadata)) {
    if (message.type === 'result' && message.subtype === 'success') {
      return message.result;
    }
  }
}

// 使用
const recommendation = await recommendShoes({
  userId: 'user-001',
  sessionId: 'session-20240109',
  weight: '75kg',
  budget: '500-800',
  experience: 'beginner',
});
```

### 示例 2：批量处理多个用户

```javascript
async function batchRecommend(users) {
  for (const user of users) {
    const metadata = {
      name: `batch-recommendation-${user.name}`,
      tags: ['batch', 'shopping'],
      user_id: user.id,
      batch_id: 'batch-001',
    };

    const queryParams = {
      prompt: `推荐运动鞋给 ${user.name}`,
      options: { maxTurns: 1 },
    };

    for await (const message of traceAgentQuery(query, queryParams, metadata)) {
      if (message.type === 'result') {
        console.log(`${user.name}: ${message.result}`);
      }
    }
  }
}
```

---

## LangSmith Dashboard 使用

### 查看追踪数据

1. 访问 https://smith.langchain.com/
2. 选择对应的 Project
3. 在 Runs 列表中查看所有追踪记录

### 筛选和搜索

- **按标签过滤**：使用 `tags` 字段筛选特定类型的调用
- **按时间范围**：查看特定时间段的数据
- **按状态**：筛选成功/失败的调用
- **搜索**：按 Run ID、名称等搜索

### 性能分析

- **响应时间分布**：查看不同调用的耗时
- **成本统计**：按时间、用户、场景统计成本
- **错误率**：监控失败率和错误类型
- **Token 使用**：分析输入/输出 Token 消耗

---

## 最佳实践

### 1. 合理命名

使用描述性的追踪名称和标签：

```javascript
// ❌ 不好
const metadata = { name: 'task1', tags: ['test'] };

// ✅ 好
const metadata = {
  name: 'shoe-recommendation-beginner',
  tags: ['shopping', 'recommendation', 'shoes', 'beginner'],
};
```

### 2. 添加上下文

在 metadata 中添加有用的上下文信息：

```javascript
const metadata = {
  name: 'recommendation',
  tags: ['shopping'],
  user_id: 'user-001',
  session_id: 'session-123',
  user_profile: {
    experience: 'beginner',
    budget: '500-800',
  },
  request_time: new Date().toISOString(),
};
```

### 3. 分层追踪

对复杂流程使用嵌套追踪：

```javascript
// 主流程追踪
for await (const msg of traceAgentQuery(query, params, mainMetadata)) {
  // 处理结果...
  
  // 子任务追踪
  const result = await withTracing(
    processResult,
    'process-recommendation',
    ['post-processing']
  )(msg.result);
}
```

### 4. 错误处理

追踪失败不应影响业务逻辑：

```javascript
try {
  for await (const msg of traceAgentQuery(query, params, metadata)) {
    // 业务逻辑...
  }
} catch (error) {
  // 错误会自动记录到 LangSmith
  console.error('Agent 执行失败:', error);
  // 业务降级处理...
}
```

### 5. 成本控制

使用标签和元数据分析成本：

```javascript
const metadata = {
  name: 'recommendation',
  tags: ['production', 'paid-user'],  // 区分生产/测试、付费/免费用户
  cost_center: 'marketing',
  priority: 'high',
};
```

---

## 故障排查

### 追踪未显示在 Dashboard

**可能原因**：
1. API Key 未设置或无效
2. Project 名称不匹配
3. 网络连接问题

**解决方案**：
```javascript
// 检查配置
console.log('LANGCHAIN_API_KEY:', process.env.LANGCHAIN_API_KEY);
console.log('LANGCHAIN_PROJECT:', process.env.LANGCHAIN_PROJECT);

// 测试连接
const client = getLangSmithClient();
await client.createRun({/* test run */});
```

### 追踪数据不完整

**可能原因**：
1. Agent 执行被中断
2. 异步迭代未完成

**解决方案**：
确保完整迭代 Agent 结果：

```javascript
for await (const message of traceAgentQuery(query, params, metadata)) {
  // 处理所有消息类型
  if (message.type === 'result') {
    // 确保等待结果处理完成
  }
}
```

### 性能影响

**问题**：追踪是否影响性能？

**答案**：
- 追踪操作是异步的，不阻塞主流程
- 未启用时零开销
- 启用后每次调用增加约 50-100ms 网络延迟（不影响 Agent 执行）

---

## 进阶功能

### 自定义 Run 类型

```javascript
await langsmithClient.createRun({
  id: runId,
  name: 'custom-task',
  run_type: 'tool',  // 可选: chain, tool, llm, retriever
  inputs: { /* ... */ },
  outputs: { /* ... */ },
});
```

### 关联父子 Run

```javascript
const parentRunId = crypto.randomUUID();
await langsmithClient.createRun({
  id: parentRunId,
  name: 'parent-task',
  run_type: 'chain',
});

await langsmithClient.createRun({
  id: crypto.randomUUID(),
  name: 'child-task',
  run_type: 'tool',
  parent_run_id: parentRunId,  // 关联父 Run
});
```

### 添加反馈

```javascript
await langsmithClient.createFeedback(runId, {
  key: 'user-rating',
  score: 0.9,
  comment: '推荐很准确',
});
```

---

## 总结

### 核心优势

✅ **无侵入集成**：一行代码启用追踪  
✅ **生产级可靠**：错误隔离，追踪失败不影响业务  
✅ **丰富元数据**：支持自定义标签、用户信息、会话等  
✅ **强大分析**：成本、性能、错误率一目了然  
✅ **易于调试**：完整的执行链路和中间结果

### 使用流程

1. 安装 `langsmith`
2. 配置环境变量（API Key、Project）
3. 应用启动时调用 `configure_claude_agent_sdk()`
4. 使用 `traceAgentQuery()` 包装 Agent 调用
5. 在 LangSmith Dashboard 查看追踪数据

---

## 参考资源

- **LangSmith 官方文档**：https://docs.smith.langchain.com/
- **Claude Agent SDK**：./claude-agent-sdk/README.md
- **集成示例**：./agent-with-langsmith.mjs
- **配置文件**：./langsmith-config.mjs

---

**问题反馈**：如有问题，请检查 LangSmith Dashboard 的错误日志或查看控制台输出的追踪信息。
