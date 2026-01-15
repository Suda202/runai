# RunAI-v2 问题清单 & 优化计划
> Updated: 2026-01-15
> Status: **核心功能稳定，评测系统已实现**

---

## ✅ 已完成

### 核心功能
- [x] Claude Agent SDK 集成
- [x] WebSearch 优先（Claude 模型）
- [x] tavily_search 备选（MiniMax 模型）
- [x] google_shopping 价格查询
- [x] LangSmith Tracing

### Prompt 优化
- [x] 精简 System Prompt
- [x] 集成推理规则表格
- [x] 动态搜索轮次（"信息足够即可输出"）
- [x] 价格免责声明
- [x] 搜索策略优化（中国品牌用中文搜索）
- [x] 高优先级来源（跑步圣经、虎扑跑步区）

### 评测系统
- [x] LLM-as-Judge 评分器（scorer.py）
- [x] 评分维度：需求理解、推荐合理性、信息质量、输出规范
- [x] 参考约束和答案仅作参考，不是绝对标准

### 代码质量
- [x] 配置集中管理（config.py）
- [x] 日志统一（logging 模块）
- [x] `parse_list_param` 支持多种格式

### 文档
- [x] PRD 精简（删除过时 Node.js 代码）
- [x] CLAUDE.md 架构图更新
- [x] 删除过时的 knowledge.md

---

## 🔄 进行中

### 评测优化
- [ ] 更新 test_cases.json 预期答案
- [ ] 添加更多测试用例

---

## 📋 待办

### P1 - 推荐质量
- [ ] 追问选项设计优化
- [ ] 避坑提示来源权威性提升

### P2 - 功能扩展
- [ ] 恢复 Google Shopping 或接入替代 API
- [ ] A/B 测试不同 prompt 策略

---

## 文件清单

| 文件 | 状态 | 说明 |
|------|------|------|
| `agent.py` | ✅ | Agent 主文件，System Prompt |
| `tools.py` | ✅ | 工具定义 |
| `config.py` | ✅ | 配置集中管理 |
| `run_eval.py` | ✅ | 评测脚本 |
| `eval/scorer.py` | ✅ | LLM-as-Judge 评分器 |
| `CLAUDE.md` | ✅ | 技术文档 |
| `sports-agent-prd.md` | ✅ | 产品需求文档 |

---

*Last updated: 2026-01-15*
