"""RunAI 评测评分器 - LLM-as-Judge
[I N P U T]: Agent 输出结果 + 测试用例
[O U T P U T]: LLM 评估的各维度评分
"""

import json
import re
import httpx
from dataclasses import dataclass, field


@dataclass
class EvalResult:
    """评测结果"""
    case_id: int
    total_score: float
    breakdown: dict = field(default_factory=dict)
    comment: str = ""

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "total_score": self.total_score,
            "breakdown": self.breakdown,
            "comment": self.comment,
        }


class RunAIScorer:
    """RunAI 推荐结果评分器 - 使用 LLM 评估"""

    JUDGE_PROMPT = '''你是跑鞋推荐质量评审专家。请评估以下推荐结果。

## 用户查询
{query}

## 用户画像
{profile}

## 参考约束（仅供参考，不是绝对标准）
- 建议满足: {must_have}
- 建议避免: {must_not}

## 参考答案（仅供参考，Agent 可以推荐更合适的）
{suggested_shoes}

## Agent 推荐结果
{result}

---

请从以下维度评分（0-100），并给出简短评语：

1. **需求理解** (25%): 是否准确理解用户的核心需求？
2. **推荐合理性** (30%): 推荐的鞋款是否适合用户？理由是否充分？
3. **信息质量** (25%): 是否引用了可靠来源？是否诚实提及缺点？
4. **输出规范** (20%): 格式是否清晰？是否包含必要信息？

返回 JSON 格式（不要加 markdown 代码块）：
{{"need_understanding": 0-100, "recommendation": 0-100, "info_quality": 0-100, "format": 0-100, "total": 0-100, "comment": "一句话评价"}}'''

    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm

    def score(self, result: str, case: dict) -> EvalResult:
        """对单个结果评分"""
        if not result:
            return EvalResult(
                case_id=case.get("id", 0),
                total_score=0,
                breakdown={},
                comment="No result",
            )

        if self.use_llm:
            return self._score_with_llm(result, case)
        else:
            return self._score_simple(result, case)

    def _score_with_llm(self, result: str, case: dict) -> EvalResult:
        """使用 LLM 评估"""
        import os

        prompt = self.JUDGE_PROMPT.format(
            query=case.get("query", ""),
            profile=json.dumps(case.get("profile", {}), ensure_ascii=False),
            must_have=case.get("hard_constraints", {}).get("must_have", []),
            must_not=case.get("hard_constraints", {}).get("must_not", []),
            suggested_shoes=case.get("soft_reference", {}).get("suggested_shoes", []),
            result=result[:3000],  # 截断避免太长
        )

        try:
            # 使用 MiniMax API (Anthropic 兼容)
            api_key = os.environ.get("MINIMAX_API_KEY")
            base_url = os.environ.get("MINIMAX_BASE_URL", "https://api.minimaxi.com/anthropic")

            response = httpx.post(
                f"{base_url}/v1/messages",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "MiniMax-M2.1",
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=30,
            )

            if response.status_code == 200:
                resp_json = response.json()
                # 兼容 Anthropic 和 OpenAI 格式
                content = ""
                if "content" in resp_json:
                    # MiniMax 可能返回多个块：thinking + text
                    for block in resp_json["content"]:
                        if block.get("type") == "text":
                            content = block.get("text", "")
                            break
                    # 如果没找到 text 类型，尝试其他格式
                    if not content and resp_json["content"]:
                        content = resp_json["content"][0].get("text") or resp_json["content"][0].get("content", "")
                elif "choices" in resp_json:
                    content = resp_json["choices"][0]["message"]["content"]
                else:
                    content = str(resp_json)

                # 去掉 markdown 代码块
                if content.startswith("```"):
                    content = re.sub(r'^```(?:json)?\s*', '', content)
                    content = re.sub(r'\s*```$', '', content)

                # 解析 JSON
                scores = json.loads(content)
                return EvalResult(
                    case_id=case.get("id", 0),
                    total_score=scores.get("total", 0),
                    breakdown={
                        "need_understanding": scores.get("need_understanding", 0),
                        "recommendation": scores.get("recommendation", 0),
                        "info_quality": scores.get("info_quality", 0),
                        "format": scores.get("format", 0),
                    },
                    comment=scores.get("comment", ""),
                )
        except Exception as e:
            print(f"[WARN] LLM scoring failed: {e}")

        # 降级到简单评分
        return self._score_simple(result, case)

    def _score_simple(self, result: str, case: dict) -> EvalResult:
        """简单评分（降级方案）"""
        score = 50  # 基础分

        # 有推荐 +20
        if re.search(r'(首选|推荐|建议)', result):
            score += 20

        # 有理由 +10
        if re.search(r'(推荐理由|因为|适合)', result):
            score += 10

        # 有来源 +10
        if re.search(r'https?://', result):
            score += 10

        # 有缺点 +10
        if re.search(r'(缺点|不足|注意)', result):
            score += 10

        return EvalResult(
            case_id=case.get("id", 0),
            total_score=min(score, 100),
            breakdown={"simple_score": score},
            comment="Simple scoring (LLM unavailable)",
        )
