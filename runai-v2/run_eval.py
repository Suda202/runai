"""RunAI Agent 评测脚本 - 运行测试用例并记录到 LangSmith"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from agent import run_agent
from eval.scorer import RunAIScorer

# Load environment variables
load_dotenv()


async def run_eval(test_cases_path: str, output_dir: str = None):
    """Run evaluation on test cases"""

    # Load test cases
    with open(test_cases_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cases = data.get("cases", [])
    scorer = RunAIScorer()

    print(f"\n{'#'*60}")
    print(f"# RunAI Agent 评测 - {len(cases)} 个测试用例")
    print(f"# LangSmith Project: runai-eval")
    print(f"{'#'*60}\n")

    results = []

    for i, case in enumerate(cases, 1):
        print(f"\n{'='*60}")
        print(f"[{i}/{len(cases)}] Case #{case['id']}: {case['category']}")
        print(f"{'='*60}")
        print(f"Query: {case['query']}")
        print(f"Expected: {case['soft_reference']['suggested_shoes']}")
        print(f"-"*60)

        start_time = datetime.now()

        try:
            # 传入 mock_answers 和 profile 用于自动回答追问
            mock_answers = case.get("mock_answers")
            profile = case.get("profile")

            result = await run_agent(
                user_query=case["query"],
                mock_answers=mock_answers,
                profile=profile,
            )

            duration = (datetime.now() - start_time).total_seconds()

            # 自动评分
            eval_result = scorer.score(result, case)

            results.append({
                "case_id": case["id"],
                "category": case["category"],
                "query": case["query"],
                "expected": case["soft_reference"]["suggested_shoes"],
                "result": result,
                "duration_seconds": duration,
                "success": True,
                "error": None,
                "eval_score": eval_result.to_dict(),
            })

            print(f"\n[Complete] Duration: {duration:.1f}s | Score: {eval_result.total_score}")
            print(f"Result preview: {result[:200]}..." if result else "[No result]")

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()

            results.append({
                "case_id": case["id"],
                "category": case["category"],
                "query": case["query"],
                "expected": case["soft_reference"]["suggested_shoes"],
                "result": None,
                "duration_seconds": duration,
                "success": False,
                "error": str(e),
            })

            print(f"\n[Error] {e}")

        # Wait between cases to avoid rate limiting
        if i < len(cases):
            print(f"\n[Waiting 5s before next case...]")
            await asyncio.sleep(5)

    # Summary
    print(f"\n\n{'#'*60}")
    print(f"# 评测结果汇总")
    print(f"{'#'*60}")

    success_count = sum(1 for r in results if r["success"])
    total_duration = sum(r["duration_seconds"] for r in results)

    # 计算平均分
    scores = [r["eval_score"]["total_score"] for r in results if r.get("eval_score")]
    avg_score = sum(scores) / len(scores) if scores else 0

    print(f"\n成功率: {success_count}/{len(results)}")
    print(f"平均分: {avg_score:.1f}")
    print(f"总耗时: {total_duration:.1f}s")
    print(f"平均耗时: {total_duration/len(results):.1f}s")

    print(f"\n{'─'*60}")
    print(f"{'Case':<8} {'Category':<15} {'Score':<8} {'Time':<8} {'Status'}")
    print(f"{'─'*60}")

    for r in results:
        status = "✅" if r["success"] else "❌"
        score = r.get("eval_score", {}).get("total_score", 0)
        print(f"#{r['case_id']:<7} {r['category']:<15} {score:<8.1f} {r['duration_seconds']:<8.1f}s {status}")

    # Save results
    if output_dir:
        output_path = Path(output_dir) / f"eval_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存: {output_path}")

    print(f"\n🔗 查看 LangSmith Traces: https://smith.langchain.com/")

    return results


if __name__ == "__main__":
    # Default paths
    test_cases_path = Path(__file__).parent.parent / "eval" / "test_cases.json"
    output_dir = Path(__file__).parent.parent / "eval" / "results"

    print(f"Test cases: {test_cases_path}")
    print(f"Output dir: {output_dir}")

    # Check environment
    required_vars = ["LANGSMITH_API_KEY", "TAVILY_API_KEY", "SERPAPI_KEY"]
    missing = [v for v in required_vars if not os.environ.get(v)]

    if missing:
        print(f"\n❌ Missing environment variables: {missing}")
        print("Please set them in .env file or environment")
        sys.exit(1)

    # Run evaluation
    asyncio.run(run_eval(str(test_cases_path), str(output_dir)))
