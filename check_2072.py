#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2072 世界观文件机械校验脚本 v1
用法: python3 check_2072.py <文档.md> [--report 输出.md]
检查项:
  1. 交叉引用存在性（"见X.X节"等指向的小节是否存在）
  2. 交叉引用标题匹配（"X.X节（标签）"的标签与实际标题是否相符，疑似错位仅提示）
  3. 小节编号连续性（同级编号是否跳号/乱序）
  4. 繁体字混排
  5. 异常字符（値/阙值类/灰难/联准会等）
  6. 引号方向异常（”…”两侧均为右引号）
  7. 旧分类体系残留关键词
"""
import re, sys

TRAD = set('狀態續驟貨幣聯儲陸溫導間臨脹兩個類寬鬆迴饋惡無單獨執門範醫療討減擋貼隨億處齊題並體發經農業產獻歷紀錄輸雞園區帶動員選擇標準確認識別聽說話語權們來')
ANOMALIES = ['価', '値', '阙值', '阙値', '灰难', '联准会', '聯准会', '篹', '通谀']
OLD_CLASS = ['威权整合者', '城邦整合者', '边缘脱嵌', '制造业人口大国', '摇摆自主体', 'F/D类', 'D（化石', 'D（矿产']
# 新体系合法用法白名单：行内同时出现 B2 且提及威权整合者的情况人工判断，脚本只报行号

def main(path, report=None):
    lines = open(path, encoding='utf-8').read().split('\n')
    out = []
    def emit(s): out.append(s)

    # --- 提取标题 ---
    hdr_re = re.compile(r'^#+\s*(\d+(?:\.\d+)*)[\s　.]*(.*)')
    headers = {}   # num -> (lineno, title)
    hdr_seq = []   # (num_tuple, num, lineno)
    for i, ln in enumerate(lines, 1):
        m = hdr_re.match(ln)
        if m:
            num, title = m.group(1), m.group(2).strip()
            headers[num] = (i, title)
            hdr_seq.append((tuple(int(x) for x in num.split('.')), num, i))

    # --- 1&2 交叉引用 ---
    emit('## 一、交叉引用检查\n')
    ref_re = re.compile(r'(?:见|見|第|参见|详见)?\s*(\d+\.\d+(?:\.\d+)*)\s*节(?:（([^）]{1,30})）)?')
    dangling, mismatch = [], []
    for i, ln in enumerate(lines, 1):
        if hdr_re.match(ln): continue
        for m in ref_re.finditer(ln):
            num, label = m.group(1), m.group(2)
            if num not in headers:
                dangling.append((i, num, ln.strip()[:60]))
            elif label:
                title = headers[num][1]
                if not any(ch in title for ch in label if ch not in '的与和及'):
                    mismatch.append((i, num, label, title))
    emit(f'### 1.1 指向不存在小节的引用（{len(dangling)}处）\n')
    for i, num, ctx in dangling: emit(f'- L{i}: 引用 {num}节 不存在 | 上下文: {ctx}')
    emit(f'\n### 1.2 引用标签与实际标题疑似不符（{len(mismatch)}处，需人工确认）\n')
    for i, num, label, title in mismatch: emit(f'- L{i}: {num}节（{label}）实际标题为「{title}」')

    # --- 3 编号连续性 ---
    emit('\n## 二、小节编号连续性\n')
    from collections import defaultdict
    kids = defaultdict(list)
    for t, num, i in hdr_seq:
        kids[t[:-1]].append((t[-1], num, i))
    issues = []
    for parent, ks in kids.items():
        seq = [k[0] for k in ks]
        if seq != sorted(seq):
            issues.append(f'- 顺序错乱: {".".join(map(str,parent)) or "顶层"} 下出现 {[k[1] for k in ks]}')
        else:
            for a, b in zip(seq, seq[1:]):
                if b - a > 1:
                    issues.append(f'- 跳号: {".".join(map(str,parent))} 下 {a}→{b} 缺 {a+1}')
    emit(f'（{len(issues)}处）\n')
    for s in issues: emit(s)

    # --- 4 繁体混排 ---
    emit('\n## 三、繁体字混排\n')
    trad_lines = []
    for i, ln in enumerate(lines, 1):
        found = sorted(set(c for c in ln if c in TRAD))
        if found: trad_lines.append((i, found))
    emit(f'（{len(trad_lines)}行）\n')
    for i, f in trad_lines: emit(f'- L{i}: {"、".join(f)}')

    # --- 5 异常字符/词 ---
    emit('\n## 四、异常字符与用词\n')
    n = 0
    for i, ln in enumerate(lines, 1):
        hits = [a for a in ANOMALIES if a in ln]
        if hits: emit(f'- L{i}: {"、".join(hits)}'); n += 1
    emit(f'\n共{n}行')

    # --- 6 引号 ---
    emit('\n## 五、引号方向异常（”…”双右引号，仅统计）\n')
    q_re = re.compile(r'”[^“”\n]{1,50}”')
    qn = sum(len(q_re.findall(ln)) for ln in lines)
    emit(f'疑似双右引号包裹: 约{qn}处（建议全文正则替换时人工抽查）')

    # --- 7 旧分类残留 ---
    emit('\n## 六、旧分类体系残留关键词\n')
    n = 0
    for i, ln in enumerate(lines, 1):
        hits = [k for k in OLD_CLASS if k in ln]
        if hits: emit(f'- L{i}: {"、".join(hits)} | {ln.strip()[:50]}'); n += 1
    emit(f'\n共{n}行（注意：新体系下B2的合法描述需人工排除）')

    text = '\n'.join(out)
    if report:
        open(report, 'w', encoding='utf-8').write(text)
        print(f'报告已写入 {report}')
        print(f'摘要: 悬空引用{len(dangling)} 标签疑似不符{len(mismatch)} 编号问题{len(issues)} 繁体行{len(trad_lines)} 引号{qn}')
    else:
        print(text)

if __name__ == '__main__':
    rep = None
    if '--report' in sys.argv:
        rep = sys.argv[sys.argv.index('--report')+1]
    main(sys.argv[1], rep)
