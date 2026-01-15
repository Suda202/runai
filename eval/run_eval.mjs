#!/usr/bin/env node
/**
 * 跑鞋推荐评测脚本
 *
 * 评估维度：
 * 1. 硬约束违反检查（must_not 列表）
 * 2. 推荐合理性（是否在 soft_reference 范围内）
 * 3. 需要搜索验证的部分
 */

import dotenv from 'dotenv';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { runAgent } from '../runai-v2/agent.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

dotenv.config({ path: join(__dirname, '..', '.env') });

// 加载测试用例
function loadTestCases() {
  const content = readFileSync(join(__dirname, 'test_cases.json'), 'utf-8');
  return JSON.parse(content);
}

// 检查鞋款是否在"不推荐"上下文中被提及
function isInNegativeContext(output, shoeName) {
  const lowerOutput = output.toLowerCase();
  const lowerShoe = shoeName.toLowerCase();
  const normalizedShoe = normalizeForMatching(shoeName);

  // 定义负面上下文关键词
  const negativePatterns = [
    '不要买', '不推荐', '避开', '避坑', '劝退', '不适合',
    '❌', '⚠️', 'not recommended', "don't buy", 'avoid',
    '不要选', '谨慎', '禁止', '不建议'
  ];

  // 尝试多种方式找到鞋款位置
  // 1. 精确匹配
  let shoeIndex = lowerOutput.indexOf(lowerShoe);

  // 2. 如果精确匹配失败，尝试用标准化后的关键词匹配
  if (shoeIndex === -1) {
    const keywords = normalizedShoe.split(' ').filter(w => w.length > 2);
    // 找包含所有关键词的最短片段
    for (const keyword of keywords) {
      const idx = lowerOutput.indexOf(keyword);
      if (idx !== -1 && (shoeIndex === -1 || idx < shoeIndex)) {
        shoeIndex = idx;
      }
    }
  }

  if (shoeIndex === -1) return false;

  // 检查鞋款前后100字符范围内是否有负面关键词
  const contextStart = Math.max(0, shoeIndex - 100);
  const contextEnd = Math.min(lowerOutput.length, shoeIndex + 100);
  const context = lowerOutput.slice(contextStart, contextEnd);

  return negativePatterns.some(pattern => context.includes(pattern.toLowerCase()));
}

// 从 must_not 条目中提取独立的鞋款名称
// 处理 "Nike Vaporfly/Alphafly(说明)" 这种复合格式
function extractShoeNames(forbidden) {
  // 先去掉括号内的说明
  const withoutComment = forbidden.split('(')[0].trim();
  // 按 "/" 分割得到独立鞋款
  return withoutComment.split('/').map(s => s.trim()).filter(Boolean);
}

// 品牌名称标准化映射
const BRAND_ALIASES = {
  'nb': 'new balance',
  'asics': 'asics',
  'hoka one one': 'hoka',
};

// 标准化鞋款名称用于模糊匹配
// "NB 1080v14 2E" → "new balance 1080"
// "Saucony Peregrine 15" → "saucony peregrine"
function normalizeForMatching(name) {
  let normalized = name.toLowerCase()
    .replace(/\([^)]*\)/g, '')              // 移除括号及内容 (2E/4E版)
    .replace(/v\d{1,2}(\.\d+)?/gi, '')      // 移除 v14, v2.0（不要求前置空格）
    .replace(/\s+\d{1,2}(\.\d+)?$/g, '')    // 移除末尾1-2位版本号 (Peregrine 14)
    .replace(/\s*(2e|4e|wide)/gi, '')       // 移除楦宽标识
    .replace(/\s+/g, ' ')
    .trim();

  // 品牌别名替换
  for (const [alias, full] of Object.entries(BRAND_ALIASES)) {
    if (normalized.startsWith(alias + ' ')) {
      normalized = full + normalized.slice(alias.length);
      break;
    }
  }

  return normalized;
}

// 检查输出中是否包含某鞋款（支持模糊匹配）
function outputContainsShoe(outputLower, shoeName) {
  const normalizedShoe = normalizeForMatching(shoeName);
  const normalizedOutput = normalizeForMatching(outputLower);

  // 精确匹配优先
  if (outputLower.includes(shoeName.toLowerCase())) {
    return true;
  }
  // 标准化后子串匹配
  if (normalizedOutput.includes(normalizedShoe)) {
    return true;
  }
  // 关键词匹配：参考鞋款的所有关键词都出现在输出中
  // 处理 "NB 1080" 匹配 "New Balance Fresh Foam 1080" 的情况
  const refWords = normalizedShoe.split(' ').filter(w => w.length > 1);
  if (refWords.length >= 2) {
    const allWordsFound = refWords.every(word => normalizedOutput.includes(word));
    if (allWordsFound) {
      return true;
    }
  }
  return false;
}

// 评估单个输出
function evaluateOutput(output, testCase) {
  const result = {
    case_id: testCase.id,
    category: testCase.category,
    query: testCase.query,
    output: output,
    scores: {
      hard_constraint_pass: true,
      violations: [],
      matches: [],
      correct_avoidance: [], // 新增：正确的避坑
      needs_verification: []
    }
  };

  if (!output) {
    result.scores.hard_constraint_pass = false;
    result.scores.violations.push('无输出');
    return result;
  }

  const outputLower = output.toLowerCase();

  // 检查 must_not 违反
  for (const forbidden of testCase.hard_constraints.must_not) {
    // 提取独立鞋款名称（处理 "Vaporfly/Alphafly" 这种复合格式）
    const shoeNames = extractShoeNames(forbidden);

    for (const shoeName of shoeNames) {
      if (outputContainsShoe(outputLower, shoeName)) {
        // 检查是否在负面上下文中（即Agent正确地说"不要买"）
        if (isInNegativeContext(output, shoeName)) {
          result.scores.correct_avoidance.push(`正确避坑: ${shoeName}`);
        } else {
          result.scores.hard_constraint_pass = false;
          result.scores.violations.push(`推荐了禁止鞋款: ${shoeName} (来自约束: ${forbidden})`);
        }
      }
    }
  }

  // 检查是否匹配 suggested_shoes（模糊匹配版本号）
  for (const suggested of testCase.soft_reference.suggested_shoes) {
    if (outputContainsShoe(outputLower, suggested)) {
      result.scores.matches.push(suggested);
    }
  }

  // 检查是否匹配 alternatives（模糊匹配版本号）
  for (const alt of testCase.soft_reference.alternatives) {
    if (outputContainsShoe(outputLower, alt)) {
      result.scores.matches.push(`[替代] ${alt}`);
    }
  }

  // 如果没有匹配任何参考答案，标记需要验证
  if (result.scores.matches.length === 0 && result.scores.hard_constraint_pass) {
    result.scores.needs_verification.push('推荐鞋款不在参考列表中，需要搜索验证');
  }

  return result;
}

// 运行单个测试
async function runSingleTest(testCase) {
  console.log('\n' + '═'.repeat(70));
  console.log(`📋 Case #${testCase.id}: ${testCase.category}`);
  console.log('═'.repeat(70));
  console.log(`\n❓ Query: ${testCase.query}\n`);

  const startTime = Date.now();

  try {
    const output = await runAgent(testCase.query);
    const duration = Date.now() - startTime;

    const evaluation = evaluateOutput(output, testCase);
    evaluation.duration_ms = duration;

    // 打印评估结果
    console.log('\n' + '─'.repeat(70));
    console.log('📊 评估结果:');
    console.log('─'.repeat(70));

    if (evaluation.scores.hard_constraint_pass) {
      console.log('✅ 硬约束检查: 通过');
    } else {
      console.log('❌ 硬约束检查: 失败');
      evaluation.scores.violations.forEach(v => console.log(`   - ${v}`));
    }

    if (evaluation.scores.correct_avoidance?.length > 0) {
      console.log(`✅ 正确避坑: ${evaluation.scores.correct_avoidance.join(', ')}`);
    }

    if (evaluation.scores.matches.length > 0) {
      console.log(`✅ 匹配参考答案: ${evaluation.scores.matches.join(', ')}`);
    }

    if (evaluation.scores.needs_verification.length > 0) {
      console.log('⚠️  需要验证:', evaluation.scores.needs_verification.join(', '));
    }

    console.log(`⏱️  耗时: ${duration}ms`);

    return evaluation;

  } catch (error) {
    console.error('❌ 执行失败:', error.message);
    return {
      case_id: testCase.id,
      category: testCase.category,
      error: error.message,
      scores: { hard_constraint_pass: false, violations: ['执行失败'] }
    };
  }
}

// 主函数
async function main() {
  const args = process.argv.slice(2);
  const testData = loadTestCases();

  console.log('\n' + '╔' + '═'.repeat(68) + '╗');
  console.log('║' + ' '.repeat(20) + '跑鞋推荐评测系统' + ' '.repeat(22) + '║');
  console.log('╚' + '═'.repeat(68) + '╝');
  console.log(`\n📁 测试集: ${testData.cases.length} 个用例\n`);

  let casesToRun = testData.cases;

  // 如果指定了 case id
  if (args.length > 0) {
    const caseId = parseInt(args[0]);
    casesToRun = testData.cases.filter(c => c.id === caseId);
    if (casesToRun.length === 0) {
      console.error(`❌ 未找到 Case #${caseId}`);
      process.exit(1);
    }
  }

  const results = [];

  for (const testCase of casesToRun) {
    const result = await runSingleTest(testCase);
    results.push(result);

    // 避免 API 限流
    if (testCase !== casesToRun[casesToRun.length - 1]) {
      console.log('\n⏳ 等待 5 秒避免限流...\n');
      await new Promise(r => setTimeout(r, 5000));
    }
  }

  // 保存结果
  const outputPath = join(__dirname, 'results', `eval_${Date.now()}.json`);
  mkdirSync(join(__dirname, 'results'), { recursive: true });
  writeFileSync(outputPath, JSON.stringify(results, null, 2));
  console.log(`\n📄 结果已保存: ${outputPath}`);

  // 汇总
  console.log('\n' + '═'.repeat(70));
  console.log('📊 汇总');
  console.log('═'.repeat(70));

  const passed = results.filter(r => r.scores?.hard_constraint_pass).length;
  const matched = results.filter(r => r.scores?.matches?.length > 0).length;
  const needsVerify = results.filter(r => r.scores?.needs_verification?.length > 0).length;

  console.log(`硬约束通过: ${passed}/${results.length}`);
  console.log(`匹配参考答案: ${matched}/${results.length}`);
  console.log(`需要验证: ${needsVerify}/${results.length}`);
}

main().catch(console.error);
