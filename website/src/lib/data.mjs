// 数据装载层：消费 website_prototype/build.py 的构建产物（entries.json / graph.json / jianyu.json）。
// 原则：build.py 是唯一解析器，本文件只读产物、不解析词条源文件。
// DATA_DIR 环境变量可覆盖数据目录（VM /tmp 构建等场景）；默认取仓库内 website_prototype/site/。
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = process.env.DATA_DIR || path.resolve(HERE, '../../../website_prototype/site');

function loadJSON(name) {
  const p = path.join(DATA_DIR, name);
  if (!fs.existsSync(p)) {
    throw new Error(`缺少构建产物 ${p} —— 请先运行 python3 website_prototype/build.py 与 check_entries.py`);
  }
  return JSON.parse(fs.readFileSync(p, 'utf-8'));
}

export const data = loadJSON('entries.json');
export const graph = loadJSON('graph.json');
export const jianyu = loadJSON('jianyu.json');
export const fulldoc = loadJSON('fulldoc.json');

export const entries = data.entries;
export const VARS = data.vars;
export const BASE_DOC = data.base_doc;
export const byId = new Map(entries.map((e) => [e.id, e]));

// 节号 → 词条 id（词典"见于"列链接用）
export const secMap = new Map();
for (const e of entries) {
  if (e.extract) secMap.set(e.extract.replace(/-(intro|full)$/, ''), e.id);
}

// 入边索引（比原型更全：ref 节号引用 / term 术语链接 / related 显式声明；child 不算反向链接）
export const inbound = new Map();
for (const edge of graph.edges) {
  if (edge.kind === 'child') continue;
  if (!inbound.has(edge.to)) inbound.set(edge.to, new Map());
  const m = inbound.get(edge.to);
  if (!m.has(edge.from)) m.set(edge.from, new Set());
  m.get(edge.from).add(edge.kind);
}

// 站内路径助手（兼容 base='/' 与 base='/2072'）
export function url(p) {
  const b = import.meta.env.BASE_URL;
  return (b.endsWith('/') ? b.slice(0, -1) : b) + p;
}

// build.py 产物内链接为 "<id>.html" 形式，渲染时统一改写为站内路由
export function rewriteLinks(html) {
  if (!html) return html;
  return html.replace(/href="([A-Za-z0-9-]+)\.html"/g, (_, id) => `href="${url(`/entries/${id}/`)}"`);
}
