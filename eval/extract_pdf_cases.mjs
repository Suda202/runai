#!/usr/bin/env node
/**
 * 从 PDF 提取所有评测 case
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';
import pdfParse from 'pdf-parse';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

async function extractPdfText(pdfPath) {
  const dataBuffer = fs.readFileSync(pdfPath);
  const data = await pdfParse(dataBuffer);
  return data.text;
}

function parseTestCases(text) {
  const cases = [];
  
  // 按 "Case" 分割文本
  const caseSections = text.split(/Case\s+#?(\d+)/i).filter(s => s.trim());
  
  console.log(`找到 ${Math.floor(caseSections.length / 2)} 个潜在 case`);
  
  for (let i = 0; i < caseSections.length; i += 2) {
    if (i + 1 >= caseSections.length) break;
    
    const caseId = parseInt(caseSections[i].trim());
    const caseContent = caseSections[i + 1];
    
    if (isNaN(caseId)) continue;
    
    // 提取关键信息
    const testCase = {
      id: caseId,
      category: extractCategory(caseContent),
      query: extractQuery(caseContent),
      profile: extractProfile(caseContent),
      hard_constraints: extractConstraints(caseContent),
      soft_reference: extractReference(caseContent)
    };
    
    // 验证必填字段
    if (testCase.query && testCase.category) {
      cases.push(testCase);
    }
  }
  
  return cases;
}

function extractCategory(text) {
  // 匹配类别模式
  const patterns = [
    /类别[：:]\s*([^\n]+)/i,
    /Category[：:]\s*([^\n]+)/i,
    /分类[：:]\s*([^\n]+)/i,
  ];
  
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) return match[1].trim();
  }
  
  // 尝试从内容推断
  if (text.includes('大体重') || text.includes('体重')) return '大体重缓震';
  if (text.includes('扁平足')) return '足型-扁平足';
  if (text.includes('宽脚') || text.includes('宽楦')) return '足型-宽脚';
  if (text.includes('碳板')) return '慢速体验碳板';
  if (text.includes('越野')) return '越野-泥地防滑';
  if (text.includes('速度训练') || text.includes('间歇跑')) return '速度训练-平价无碳板';
  
  return '未分类';
}

function extractQuery(text) {
  // 匹配查询模式
  const patterns = [
    /查询[：:]\s*["""]([^"""]+)["""]/,
    /Query[：:]\s*["""]([^"""]+)["""]/,
    /用户输入[：:]\s*["""]([^"""]+)["""]/,
    /问题[：:]\s*["""]([^"""]+)["""]/,
  ];
  
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) return match[1].trim();
  }
  
  // 尝试提取引号内的第一段文字
  const quoteMatch = text.match(/["""]([^"""]{20,}?)["""]/);
  if (quoteMatch) return quoteMatch[1].trim();
  
  return null;
}

function extractProfile(text) {
  const profile = {};
  
  // 提取用户画像
  if (text.match(/体重[：:]\s*(\d+\s*kg|90kg\+|大体重)/i)) {
    profile.weight = text.match(/体重[：:]\s*([^\n,，]+)/i)?.[1].trim();
  }
  
  if (text.match(/足型|扁平足|高足弓|宽脚/i)) {
    const footMatch = text.match(/(扁平足|高足弓|宽脚|内旋|外翻)/i);
    if (footMatch) profile.foot_type = footMatch[1];
  }
  
  if (text.match(/配速|pace/i)) {
    const paceMatch = text.match(/配速[：:]\s*([^\n,，]+)/i);
    if (paceMatch) profile.pace = paceMatch[1].trim();
  }
  
  if (text.match(/症状|疼痛|pain/i)) {
    const painMatch = text.match(/(膝盖疼|足弓酸痛|脚踝不适|挤脚|磨泡)/i);
    if (painMatch) profile.pain_point = painMatch[1];
  }
  
  return Object.keys(profile).length > 0 ? profile : undefined;
}

function extractConstraints(text) {
  const constraints = {
    must_have: [],
    must_not: []
  };
  
  // 提取 must_have
  const mustHaveMatch = text.match(/must[_-]have[：:]([^]+?)(?:must[_-]not|$)/i);
  if (mustHaveMatch) {
    const items = mustHaveMatch[1].split(/[,，\n]/).map(s => s.trim()).filter(Boolean);
    constraints.must_have = items.slice(0, 3);
  }
  
  // 提取 must_not
  const mustNotMatch = text.match(/must[_-]not[：:]([^]+?)(?:推荐|soft|$)/i);
  if (mustNotMatch) {
    const items = mustNotMatch[1].split(/[,，\n]/).map(s => s.trim()).filter(Boolean);
    constraints.must_not = items.slice(0, 3);
  }
  
  return constraints;
}

function extractReference(text) {
  const reference = {
    suggested_shoes: [],
    alternatives: [],
    confidence: 'high'
  };
  
  // 提取推荐鞋款
  const suggestedMatch = text.match(/推荐|suggested[_-]shoes[：:]([^]+?)(?:备选|alternatives|$)/i);
  if (suggestedMatch) {
    const shoes = suggestedMatch[1]
      .split(/[,，\n]/)
      .map(s => s.trim())
      .filter(s => s && s.length > 3 && /[a-z]/i.test(s));
    reference.suggested_shoes = shoes.slice(0, 3);
  }
  
  // 提取备选方案
  const altMatch = text.match(/备选|alternatives[：:]([^]+?)(?:confidence|$)/i);
  if (altMatch) {
    const shoes = altMatch[1]
      .split(/[,，\n]/)
      .map(s => s.trim())
      .filter(s => s && s.length > 3 && /[a-z]/i.test(s));
    reference.alternatives = shoes.slice(0, 3);
  }
  
  return reference;
}

async function main() {
  const pdfPath = path.join(__dirname, '..', '跑鞋测评答案评估v2.pdf');
  
  console.log('正在读取 PDF...');
  const text = await extractPdfText(pdfPath);
  
  console.log(`提取文本长度: ${text.length} 字符`);
  console.log('\n开始解析评测 case...\n');
  
  const cases = parseTestCases(text);
  
  console.log(`\n成功解析 ${cases.length} 个 case\n`);
  
  // 按 id 排序
  cases.sort((a, b) => a.id - b.id);
  
  // 显示概览
  cases.forEach(c => {
    console.log(`Case #${c.id}: ${c.category}`);
    console.log(`  Query: ${c.query?.substring(0, 50)}...`);
    console.log(`  Suggested: ${c.soft_reference.suggested_shoes.join(', ')}`);
    console.log();
  });
  
  // 保存结果
  const output = {
    version: '2.0',
    description: '跑鞋推荐评测集 - 完整版（从 PDF 提取）',
    extracted_at: new Date().toISOString(),
    cases: cases
  };
  
  const outputPath = path.join(__dirname, 'test_cases_full.json');
  fs.writeFileSync(outputPath, JSON.stringify(output, null, 2));
  
  console.log(`\n✅ 已保存到: ${outputPath}`);
  console.log(`📊 总计: ${cases.length} 个评测用例`);
}

main().catch(console.error);
