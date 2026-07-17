// 悬停预览用的轻量词条数据（静态构建时生成 /data.json）
import { entries } from '../lib/data.mjs';

export function GET() {
  const lite = {};
  for (const e of entries) lite[e.id] = { title: e.title, type: e.type, summary: e.summary };
  return new Response(JSON.stringify(lite), {
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
  });
}
