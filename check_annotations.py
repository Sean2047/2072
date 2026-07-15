#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""方向B新目录草案源头标注核对脚本 v1（配合 D-045 关闭回收，归属分派前置）
用法: python3 check_annotations.py <新目录草案_方向B.md> <2072_v149.md> [--report 输出.md]

背景: 草案的节级源头标注 [v143 X.X] 以 v143 为基准；现行基准 v149 经历过
编号收拢与小节合并（重整工作文件 4.0 核销记录、决策日志 D-042）。
本脚本核对每条标注在 v149 中的有效性，输出问题清单（先出清单后修正，
符合“从定义好的逻辑前提出发”的校验原则）。

检查项:
  1. 悬空标注——标注节号在 v149 中不存在（附已知重编号映射建议）
  2. 重编号风险组——节号存在但所在组曾重编号/互换，内容对应需人工确认
  3. 覆盖检查——v149 中无任何标注指向的二级节（分派时按新节处理，
     重点关注 3.9/7.4——二者标题在 v143 中被吞，草案很可能漏标）
"""
import re, sys

# v143 -> v149 已知重编号映射（来源：重整工作文件 4.0 核销记录、D-042）
REMAP = {
    '3.13.7': '3.13.8',   # 与 3.13.8 互换
    '3.13.8': '3.13.7',
    '3.16.6': '3.16.5', '3.16.7': '3.16.6', '3.16.8': '3.16.7', '3.16.9': '3.16.8',
    '4.7.6': '4.7.5', '4.7.7': '4.7.6',
    '3.14.11': '3.14.4',  # 并入新3.14.4（全控路网的覆盖范围与经济逻辑）
    '3.14.13': '3.14.12', '3.14.14': '3.14.12',  # 合并为新3.14.12
    '3.14.15': '3.14.13', '3.14.16': '3.14.14',
    '3.14.17': '3.14.15', '3.14.18': '3.14.16',
}
# 存在性检查会通过、但内容可能已迁移/互换的组（需人工确认）
RISK_PREFIXES = ('3.13.', '3.14.', '3.16.', '4.7.')

def load_headers(path):
    hdr_re = re.compile(r'^#+\s*((?:\d+|[A-Z])(?:\.\d+)*)[\s　.]*(.*)')
    headers = {}
    for i, ln in enumerate(open(path, encoding='utf-8'), 1):
        m = hdr_re.match(ln)
        if m:
            headers[m.group(1)] = (i, m.group(2).strip())
    return headers

def main(draft_path, base_path, report=None):
    headers = load_headers(base_path)
    ann_re = re.compile(r'\[v14[39][\s　]*((?:\d+|[A-Z])(?:\.\d+)*)\]')
    anns = []  # (lineno, num, context)
    for i, ln in enumerate(open(draft_path, encoding='utf-8'), 1):
        for m in ann_re.finditer(ln):
            anns.append((i, m.group(1), ln.strip()[:60]))

    out = []
    emit = out.append
    emit('# 源头标注核对报告（草案 [v143 X.X] ↔ v149 现行节号）\n')
    emit(f'标注总数：{len(anns)}\n')

    dangling, risky, ok = [], [], 0
    for lineno, num, ctx in anns:
        if num not in headers:
            hint = f'（已知映射建议：{REMAP[num]} {headers.get(REMAP[num], ("", "?"))[1]}）' if num in REMAP else '（无已知映射，需人工定位）'
            dangling.append(f'- L{lineno}: [v143 {num}] 在 v149 中不存在 {hint} | {ctx}')
        elif num.startswith(RISK_PREFIXES) and num.count('.') >= 2:
            note = f'；已知映射：v143 {num} → v149 {REMAP[num]}' if num in REMAP else ''
            risky.append(f'- L{lineno}: [v143 {num}] 存在，但该组曾重编号（D-042/4.0），内容对应需人工确认{note} | 现标题：{headers[num][1]}')
        else:
            ok += 1

    emit(f'## 一、悬空标注（{len(dangling)}处，必须修正）\n')
    out += dangling or ['（无）']
    emit(f'\n## 二、重编号风险组（{len(risky)}处，逐条人工确认）\n')
    out += risky or ['（无）']

    referenced = {num for _, num, _ in anns}
    referenced |= {REMAP.get(num, '') for num in referenced}
    uncovered = [f'- {num}　{title}' + ('　★ v143中标题被吞，草案极可能漏标' if num in ('3.9', '7.4') else '')
                 for num, (_, title) in sorted(headers.items(), key=lambda kv: kv[1][0])
                 if num.count('.') == 1 and num[0].isdigit() and num not in referenced]
    emit(f'\n## 三、v149 中无标注覆盖的二级节（{len(uncovered)}处，分派时按新节处理）\n')
    out += uncovered or ['（无）']
    emit(f'\n## 四、通过：{ok} 处标注可直接沿用\n')

    text = '\n'.join(out)
    if report:
        open(report, 'w', encoding='utf-8').write(text)
        print(f'报告已写入 {report}')
    else:
        print(text)
    return len(dangling)

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    rep = sys.argv[sys.argv.index('--report') + 1] if '--report' in sys.argv else None
    if len(args) != 2:
        print(__doc__); sys.exit(2)
    sys.exit(1 if main(args[0], args[1], rep) else 0)
