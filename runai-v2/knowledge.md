# RunAI 知识库 - 跑鞋物理参数
> L2 | 父级: CLAUDE.md | Updated: 2026-01-15

物理参数用于推理和搜索，是推荐的依据。

## 核心物理参数

### 1. Drop (落差)
鞋跟到前掌的高度差 (mm)。

| 数值 | 特性 | 适用场景 |
|------|------|----------|
| 高 (>8mm) | 减少跟腱拉伸 | 跟腱炎恢复、后掌落地 |
| 中 (6-8mm) | 平衡过渡 | 日常训练、多数跑者 |
| 低 (<6mm) | 减少膝盖压力 | 前掌落地、足底筋膜炎 |
| 零 (0mm) | 自然步态 | 追求自然跑法、需适应期 |

### 2. Stability (稳定性)
控制过度内旋 (overpronation) 的能力。

| 类型 | 关键词 | 适用症状 |
|------|--------|----------|
| 稳定型 | "stability", "guidance", "medial post", "wide base" | 膝盖内侧疼、足外翻 |
| 过度内旋 | "overpronation support" | 扁平足、踝关节不稳 |

### 3. Cushion (缓震)
吸收冲击的能力。硬度单位 HA (Shore A)，越低越软。

| 硬度 | 特性 | 适用场景 |
|------|------|----------|
| <25 HA | 极软 | 恢复跑、长距离 |
| 25-35 HA | 中等 | 日常训练 |
| >35 HA | 偏硬 | 竞速、响应快 |

### 4. Rocker (滚动设计)
减少脚趾弯折，辅助过渡。

| 关键词 | 适用症状 |
|--------|----------|
| "rocker", "rigid forefoot", "stiff plate" | 足底筋膜炎、拇外翻 |

### 5. Flexibility (灵活性)
前掌弯折程度。

| 类型 | 特性 |
|------|------|
| 僵硬 | 保护足底筋膜、竞速推进 |
| 灵活 | 自然步态、日常舒适 |

### 6. Last (鞋楦)
鞋型宽度和足弓适配。

| 类型 | 关键词 | 适用脚型 |
|------|--------|----------|
| 直楦 | "straight last" | 扁平足 |
| 弯楦 | "curved last" | 高足弓 |
| 宽楦 | "2E", "4E", "wide toe box", "spacious fit" | 宽脚 |

## 推理规则速查

### 症状 → 参数需求

| 症状 | 推理 | 搜索关键词 |
|------|------|------------|
| 膝盖内侧疼 | 足外翻 → 稳定性 | "stability shoe", "guidance", "overpronation" |
| 小腿前侧疼 | 冲击大 → 高落差+顶级缓震 | "high drop", "max cushion", "shock absorption" |
| 足底筋膜炎 | 筋膜拉扯 → 僵硬滚动 | "rocker", "arch support", "rigid forefoot" |
| 跟腱炎 | 跟腱拉扯 → 低落差 | "low drop", "<6mm drop" |

### 脚型 → 参数需求

| 脚型 | 需求 | 搜索关键词 |
|------|------|------------|
| 扁平足 | 足弓支撑/直楦 | "straight last", "arch support", "stability" |
| 高足弓 | 缓震代替吸震 | "high cushion", "neutral shoe", "soft midsole" |
| 宽脚 | 宽楦/延展鞋面 | "2E", "4E", "wide toe box" |

### 场景 → 参数需求

| 场景 | 需求 | 搜索关键词 |
|------|------|------------|
| 竞速 | 轻量、响应、碳板 | "race shoe", "carbon plate", "lightweight" |
| 恢复跑 | 极致柔软 | "recovery shoe", "ultra soft", "<25 HA" |
| 日常训练 | 耐用、全覆盖 | "daily trainer", "durable", "full rubber" |
| 多场景 | 跨界能力 | "versatile", "multi-purpose", "hybrid" |

## 矛盾信息处理

**可信度公式**：
```
可信度 = 来源权重 × 样本量 × 用户匹配度 × 时间衰减
```

**优先级**：
1. 专业评测 > 普通用户帖子
2. 多人一致 > 单一案例
3. 具体描述 > 笼统评价
4. 近期评价 > 旧评价

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
