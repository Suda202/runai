# LangSmith 快速开始指南

## 🎯 什么是 LangSmith？

LangSmith 是 LangChain 提供的 LLM 应用追踪和监控平台，帮助您：

- 📊 追踪每次 Agent 调用的完整执行过程
- 💰 分析成本和 Token 使用情况
- 🔍 调试错误和性能问题
- 📈 监控生产环境的应用表现

---

## ⚡ 3 分钟快速集成

### 步骤 1: 安装依赖

依赖已包含在项目中：

```bash
npm install  # langsmith 已在 package.json 中
```

### 步骤 2: 获取 LangSmith API Key

1. 访问 https://smith.langchain.com/
2. 注册/登录账户
3. 进入 **Settings** → **API Keys**
4. 点击 **Create API Key**
5. 复制生成的 Key（格式: `lsv2_pt_...`）

### 步骤 3: 配置环境变量

在 `.env` 文件中添加：

```bash
LANGCHAIN_API_KEY=lsv2_pt_your_key_here
LANGCHAIN_PROJECT=shopping-agent
LANGCHAIN_TRACING_V2=true
```

### 步骤 4: 在代码中启用

在应用启动时添加一行代码：

```javascript
import { configure_claude_agent_sdk } from './langsmith-config.mjs';

// 必须在任何 Agent 调用之前执行
configure_claude_agent_sdk();
```

### 步骤 5: 使用追踪包装器

包装您的 Agent 调用：

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
};

for await (const message of traceAgentQuery(query, queryParams, metadata)) {
  // 处理消息...
}
```

### 步骤 6: 查看追踪数据

访问 https://smith.langchain.com/ 查看：

- 完整的执行流程
- 耗时和成本统计
- 输入输出详情
- 错误堆栈（如果有）

---

## 🧪 测试集成

### 快速测试

验证配置是否正确：

```bash
node test-langsmith-quick.mjs
```

预期输出：

```
✅ LangSmith 初始化成功

配置信息:
  LANGCHAIN_API_KEY: ✓ 已设置
  LANGCHAIN_PROJECT: shopping-agent
  ...
```

### 完整测试

运行包含 LangSmith 追踪的 Agent 示例：

```bash
node agent-with-langsmith.mjs
```

### 实际业务场景测试

运行运动鞋推荐助手（集成版）：

```bash
node running-shoes-advisor-with-langsmith.mjs
```

---

## 📂 集成文件说明

### 核心文件

| 文件 | 职责 | 何时使用 |
|------|------|---------|
| `langsmith-config.mjs` | 配置和追踪包装器 | 被其他文件导入使用 |
| `agent-with-langsmith.mjs` | 集成示例 | 学习如何使用 |
| `test-langsmith-quick.mjs` | 快速测试 | 验证配置是否正确 |
| `running-shoes-advisor-with-langsmith.mjs` | 实际业务示例 | 查看真实场景用法 |
| `LANGSMITH_INTEGRATION.md` | 完整文档 | 查看详细 API 和最佳实践 |

### 配置文件

| 文件 | 说明 |
|------|------|
| `env.langsmith.example` | 环境变量示例 |
| `.env` | 实际配置（不要提交到 git） |

---

## 🔄 迁移现有代码

### 方式一：最小改动（推荐）

只需在应用启动时添加一行：

```javascript
import { configure_claude_agent_sdk } from './langsmith-config.mjs';

// 添加这一行
configure_claude_agent_sdk();

// 其他代码不变
const q = query({ /* ... */ });
for await (const msg of q) {
  // ...
}
```

**优点**：代码改动最小，自动追踪所有调用
**缺点**：无法添加自定义元数据（标签、用户 ID 等）

### 方式二：使用追踪包装器

包装 Agent 调用以添加元数据：

```javascript
import { configure_claude_agent_sdk, traceAgentQuery } from './langsmith-config.mjs';
import { query } from './claude-agent-sdk/sdk.mjs';

// 初始化
configure_claude_agent_sdk();

// 包装调用
const metadata = {
  name: 'recommendation-task',
  tags: ['shopping', 'shoes'],
  user_id: 'user-123',
};

for await (const msg of traceAgentQuery(query, queryParams, metadata)) {
  // ...
}
```

**优点**：完整的追踪信息，支持按标签/用户/会话筛选
**缺点**：需要修改调用代码

---

## 🎨 元数据最佳实践

### 基本元数据

```javascript
const metadata = {
  name: 'descriptive-task-name',       // 任务名称
  tags: ['category', 'type'],          // 标签数组
  user_id: 'user-123',                 // 用户 ID
  session_id: 'session-456',           // 会话 ID
};
```

### 业务场景元数据

```javascript
const metadata = {
  name: 'shoe-recommendation',
  tags: ['shopping', 'recommendation', 'beginner'],
  user_id: user.id,
  session_id: session.id,
  
  // 业务上下文
  user_profile: {
    experience: 'beginner',
    budget: '500-800',
  },
  
  // 技术信息
  model: 'anthropic/claude-sonnet-4',
  max_turns: 3,
  
  // 环境信息
  environment: 'production',
  version: '1.2.0',
  region: 'cn-north',
};
```

### 标签建议

**按功能分类**:
- `recommendation` - 推荐类任务
- `search` - 搜索类任务
- `analysis` - 分析类任务

**按场景分类**:
- `shopping` - 购物场景
- `customer-service` - 客服场景
- `content-generation` - 内容生成

**按用户类型**:
- `free-user` - 免费用户
- `paid-user` - 付费用户
- `vip` - VIP 用户

**按环境**:
- `dev` - 开发环境
- `staging` - 测试环境
- `production` - 生产环境

---

## 📊 LangSmith Dashboard 使用

### 查看追踪列表

1. 访问 https://smith.langchain.com/
2. 选择您的 Project
3. 在 **Runs** 列表中查看所有追踪

### 筛选和搜索

**按标签筛选**:
```
tags: shopping AND recommendation
```

**按时间范围**:
```
选择时间范围过滤器
```

**按状态**:
```
status: success  # 或 error
```

**按用户**:
```
metadata.user_id: user-123
```

### 查看详细信息

点击任意 Run 查看：

- **Inputs**: 提示词、参数
- **Outputs**: Agent 响应、结果
- **Metadata**: 标签、用户信息、自定义字段
- **Timeline**: 执行时间线
- **Costs**: Token 使用和成本
- **Errors**: 错误堆栈（如果有）

### 性能分析

Dashboard 提供：

- **响应时间分布图**
- **成本趋势图**
- **成功率统计**
- **Token 使用统计**

---

## 🚨 常见问题

### Q: 追踪未显示在 Dashboard

**A**: 检查以下几点：

1. API Key 是否正确设置
2. Project 名称是否匹配
3. 网络是否能访问 `api.smith.langchain.com`
4. 是否调用了 `configure_claude_agent_sdk()`

验证方法：

```bash
node test-langsmith-quick.mjs
```

### Q: 会影响性能吗？

**A**: 影响极小：

- 追踪操作是异步的，不阻塞主流程
- 未启用时零开销
- 启用后每次调用增加约 50-100ms 网络延迟（不影响 Agent 执行）

### Q: 未配置 API Key 会报错吗？

**A**: 不会！设计为优雅降级：

```javascript
configure_claude_agent_sdk();  // 返回 false，不抛出错误
// 应用继续正常运行，只是不记录追踪数据
```

### Q: 如何在生产环境使用？

**A**: 推荐做法：

```javascript
// 使用环境变量控制是否启用
if (process.env.NODE_ENV === 'production') {
  configure_claude_agent_sdk();
}
```

或者：

```javascript
// 始终配置，未设置 API Key 时自动禁用
configure_claude_agent_sdk();
```

### Q: 可以追踪其他函数吗？

**A**: 可以！使用 `withTracing()` 装饰器：

```javascript
import { withTracing } from './langsmith-config.mjs';

const tracedFunction = withTracing(
  myFunction,
  'my-function-name',
  ['tag1', 'tag2']
);

await tracedFunction(arg1, arg2);
```

---

## 🎯 下一步

1. **配置 API Key**: 按照步骤 2 获取并配置
2. **运行测试**: `node test-langsmith-quick.mjs`
3. **集成到应用**: 在启动时调用 `configure_claude_agent_sdk()`
4. **查看数据**: 访问 LangSmith Dashboard

---

## 📚 更多资源

- **完整文档**: [LANGSMITH_INTEGRATION.md](./LANGSMITH_INTEGRATION.md)
- **配置示例**: [env.langsmith.example](./env.langsmith.example)
- **集成示例**: [agent-with-langsmith.mjs](./agent-with-langsmith.mjs)
- **实战示例**: [running-shoes-advisor-with-langsmith.mjs](./running-shoes-advisor-with-langsmith.mjs)
- **LangSmith 官方文档**: https://docs.smith.langchain.com/

---

## 💡 提示

- 追踪数据在 LangSmith 免费版可保留 14 天
- 付费版提供更长的数据保留期和更多功能
- 建议在开发环境先熟悉功能，再部署到生产
- 合理使用标签和元数据，方便后续分析

---

**问题反馈**: 如有问题，请检查 `LANGSMITH_INTEGRATION.md` 中的详细文档。
