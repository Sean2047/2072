# -*- coding: utf-8 -*-
"""2072 知识库网站原型构建脚本（零依赖）。

用法: python3 build.py
输入: entries/*.md（frontmatter + 可选正文）+ ../2072_vNNN.md（自动取版本号最大者，章节词条原文按节号提取）
输出: site/ 静态站点 + graph.json/entries.db 关联数据库。
构建报告打印到控制台（链接校验 = check_2072 引用校验的构建时形态）。
"""
import os, re, sys, html, json, glob

BASE = os.path.dirname(os.path.abspath(__file__))

def _latest_base_doc():
    """自动定位当前基准文档：project 根目录下 2072_vNNN.md 中版本号最大的一个。
    避免每次基准文档版本递增（v149→v150→……）都要手改本脚本硬编码路径。"""
    candidates = glob.glob(os.path.join(BASE, '..', '2072_v*.md'))
    versioned = []
    for p in candidates:
        m = re.search(r'2072_v(\d+)\.md$', os.path.basename(p))
        if m:
            versioned.append((int(m.group(1)), p))
    if not versioned:
        raise FileNotFoundError('未找到 2072_vNNN.md 基准文档')
    versioned.sort()
    return versioned[-1][1]

V149 = _latest_base_doc()  # 变量名沿用历史命名，实际指向当前最新版本基准文档
ENTRY_DIR = os.path.join(BASE, 'entries')
OUT = os.path.join(BASE, 'site')

# ---------- frontmatter ----------

def parse_entry(path):
    text = open(path, encoding='utf-8').read()
    m = re.match(r'---\n(.*?)\n---\n?(.*)', text, re.S)
    if not m:
        raise ValueError(f'no frontmatter: {path}')
    fm_text, body = m.group(1), m.group(2)
    fm, key = {}, None
    lines = fm_text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        km = re.match(r'^([A-Za-z_]+):\s*(.*)$', line)
        if km:
            key, val = km.group(1), km.group(2)
            if val == '|':  # block scalar
                block = []
                i += 1
                while i < len(lines) and (lines[i].startswith('  ') or lines[i] == ''):
                    block.append(lines[i][2:])
                    i += 1
                fm[key] = '\n'.join(block).strip()
                continue
            fm[key] = val.strip()
        i += 1
    for k in ('paths', 'variables', 'related', 'aliases', 'children'):
        if k in fm:
            fm[k] = [x.strip() for x in fm[k].split(',') if x.strip()]
    fm['body'] = body.strip()
    return fm

# ---------- v149 section extraction ----------

def load_v149():
    return open(V149, encoding='utf-8').read().split('\n')

def extract_section(lines, sec):
    """提取节正文（不含标题行）。sec 如 '4.9.1'；'4.9-intro' 表示二级节导语（到首个###为止）；
    '4.9-full' 表示二级节整节全文（含全部###子节，不在子节处断开，只在下一个同级##处断开）——
    用于"整节成篇不拆"的技术层词条（如3.7，D-060裁定），extract_section默认逐子节断开，
    -full后缀是显式的整节抽取模式，不影响其他现有extract写法的行为。"""
    intro = sec.endswith('-intro')
    full = sec.endswith('-full')
    if intro:
        sec = sec[:-6]
    if full:
        sec = sec[:-5]
    # 二级节(X.X)用##；三级(X.X.X)及形式上用###标题的四级编号节(如1.4.4.1)用###
    level = '##' if sec.count('.') == 1 else '###'
    pat = re.compile(r'^%s\s+%s　' % (level, re.escape(sec)))
    start = None
    for i, l in enumerate(lines):
        if pat.match(l):
            start = i + 1
            break
    if start is None:
        return None
    out = []
    for l in lines[start:]:
        if full:
            if re.match(r'^##\s', l):
                break
        elif re.match(r'^#{1,3}\s', l):
            if intro or not l.startswith('####'):
                break
        out.append(l)
    return '\n'.join(out).strip()

# ---------- markdown -> html (最小子集: 段落/粗斜体/表格/引用/列表) ----------

def inline_md(s):
    s = html.escape(s, quote=False)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<![\*\w])\*([^\*\n]+?)\*(?![\*\w])', r'<em>\1</em>', s)
    return s

def md_to_html(md):
    blocks, out = re.split(r'\n\s*\n', md), []
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        lines = b.split('\n')
        if all(l.lstrip().startswith('|') for l in lines) and len(lines) >= 2:
            rows = [[c.strip() for c in l.strip().strip('|').split('|')] for l in lines]
            body_rows, header = [], None
            for r in rows:
                if all(re.fullmatch(r':?-{2,}:?', c) for c in r):
                    header, body_rows = body_rows[-1], body_rows[:-1]
                    continue
                body_rows.append(r)
            t = '<table>'
            if header:
                t += '<thead><tr>' + ''.join(f'<th>{inline_md(c)}</th>' for c in header) + '</tr></thead>'
            t += '<tbody>' + ''.join('<tr>' + ''.join(f'<td>{inline_md(c)}</td>' for c in r) + '</tr>' for r in body_rows) + '</tbody></table>'
            out.append(t)
        elif all(l.lstrip().startswith('>') for l in lines):
            inner = ' '.join(l.lstrip()[1:].strip() for l in lines)
            out.append(f'<blockquote><p>{inline_md(inner)}</p></blockquote>')
        elif all(l.lstrip().startswith('- ') for l in lines):
            out.append('<ul>' + ''.join(f'<li>{inline_md(l.lstrip()[2:])}</li>' for l in lines) + '</ul>')
        elif re.match(r'^#{3,6}\s', lines[0]):
            # 三级及以下标题（-full 整节词条与全文阅读视图会包含 ###/#### 行）
            hm = re.match(r'^(#{3,6})\s+(.*)$', lines[0])
            lvl = min(len(hm.group(1)) - 1, 6)  # ###→h2 ####→h3（页面h1留给节标题）
            out.append(f'<h{lvl}>{inline_md(hm.group(2))}</h{lvl}>')
            rest = '\n'.join(lines[1:]).strip()
            if rest:
                out.append(f'<p>{inline_md(rest)}</p>')
        elif b.startswith('*') and b.endswith('*') and not b.startswith('**'):
            out.append(f'<p class="coda">{inline_md(b[1:-1])}</p>')
        else:
            out.append(f'<p>{inline_md(" ".join(lines))}</p>')
    return '\n'.join(out)

# ---------- linking ----------

SEC_REF = re.compile(r'(?:见)?(\d+\.\d+(?:\.\d+){0,2})节')

def link_refs(html_text, sec_map, stats, self_id):
    def repl(m):
        sec = m.group(1)
        tid = sec_map.get(sec)
        if tid and tid != self_id:
            stats['resolved'].append((self_id, sec, tid))
            return f'<a class="entry-link" href="{tid}.html" data-id="{tid}">{m.group(0)}</a>'
        if tid == self_id:
            return m.group(0)
        stats['unresolved'].append((self_id, sec))
        return f'<span class="unresolved" title="词条未收录（原型范围外）：{sec}节">{m.group(0)}</span>'
    return SEC_REF.sub(repl, html_text)

def link_terms(html_text, alias_map, self_id, stats):
    """每个段落内为概念别名的首次出现加链接（跳过标签内部与自身词条）。"""
    parts = re.split(r'(<[^>]+>)', html_text)  # 粗分标签/文本
    seen_in_par = set()
    result = []
    depth_a = 0
    for p in parts:
        if p.startswith('<'):
            if p.startswith('<a'):
                depth_a += 1
            elif p.startswith('</a'):
                depth_a -= 1
            if p in ('<p>',) or p.startswith('<p ') or p == '<li>':
                seen_in_par = set()
            result.append(p)
            continue
        if depth_a:
            result.append(p)
            continue
        for alias, tid in alias_map:
            if tid == self_id or tid in seen_in_par:
                continue
            idx = p.find(alias)
            if idx >= 0:
                p = p[:idx] + f'<a class="entry-link concept" href="{tid}.html" data-id="{tid}">{alias}</a>' + p[idx+len(alias):]
                seen_in_par.add(tid)
                stats['term_links'] += 1
                stats['term_edges'].append((self_id, tid))
        result.append(p)
    return ''.join(result)

# ---------- page templates ----------

def badge_row(e):
    b = [f'<span class="badge type-{e["type"]}">{e["type"]}词条</span>',
         f'<span class="badge layer">{e["layer"]}层</span>',
         f'<span class="badge src">{e["source"]}</span>']
    b += [f'<span class="badge path">{p}</span>' for p in e.get('paths', [])]
    b += [f'<span class="badge var" title="{VARS.get(v, "")}">{v}</span>' for v in e.get('variables', [])]
    b.append(f'<span class="badge dom">{e.get("domain", "")}</span>')
    return '<div class="badges">' + ''.join(b) + '</div>'

VARS = {'V1': '自动化替代率', 'V2': '能源丰裕度', 'V3': '流动回报率', 'V4': '国家整合能力',
        'V5': '社区吸附力', 'V6': '意义供给能力', 'V7': '痛苦政治化程度', 'V8': '历史滞后量'}

PAGE = '''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · 2072 知识库原型</title>
<link rel="stylesheet" href="style.css"></head>
<body><nav class="top"><a href="index.html">← 词条总览</a><span class="proto">《2072》知识库 · Part 4 原型</span></nav>
<main>{content}</main>
<div id="tooltip" hidden></div>
<script src="data.js"></script><script src="app.js"></script></body></html>'''

def entry_page(e, body_html, backlinks, id2entry, iface=None):
    parts = [f'<header class="entry-head"><h1>{html.escape(e["title"])}</h1>', badge_row(e)]
    if e.get('note'):
        parts.append(f'<div class="note">⚠ {inline_md(e["note"])}</div>')
    parts.append('</header>')
    parts.append(f'<section class="l1"><div class="ltag">一句话摘要</div><p class="summary">{inline_md(e["summary"])}</p></section>')
    parts.append(f'<section class="l2"><div class="ltag">一段概述</div>{md_to_html(e["overview"])}</section>')
    if e['type'] == '事件' and e.get('time_span'):
        iface = iface or {}
        parts.append('<section class="interface"><h2>接口声明</h2>'
                      f'<dl><dt>时间位置</dt><dd>{inline_md(e.get("time_span",""))}</dd>'
                      f'<dt>演练机制</dt><dd>{iface.get("mechanism_tested") or md_to_html(e.get("mechanism_tested",""))}</dd>'
                      f'<dt>可替换性</dt><dd>{iface.get("substitutability") or md_to_html(e.get("substitutability",""))}</dd>'
                      f'<dt>反向义务</dt><dd>{iface.get("counter_obligation") or md_to_html(e.get("counter_obligation",""))}</dd></dl></section>')
    label = '完整机制推导（v149 原文）' if e['type'] == '章节' else '词条正文'
    open_attr = '' if e['type'] == '章节' else ' open'
    parts.append(f'<details class="l3"{open_attr}><summary>{label}</summary><div class="prose">{body_html}</div></details>')
    if e.get('children'):
        items = []
        for c in e['children']:
            if c.startswith('~'):
                items.append(f'<li class="missing">{html.escape(c[1:])} <span class="tag">原型未收录</span></li>')
            else:
                ce = id2entry[c]
                items.append(f'<li><a class="entry-link" href="{c}.html" data-id="{c}">{html.escape(ce["source"].split()[-1])}　{html.escape(ce["title"])}</a><span class="csum">{html.escape(ce["summary"])}</span></li>')
        parts.append('<section class="children"><h2>本节词条</h2><ul>' + ''.join(items) + '</ul></section>')
    if e.get('related'):
        rel = ''.join(f'<a class="entry-link chip" href="{r}.html" data-id="{r}">{html.escape(id2entry[r]["title"])}</a>'
                      for r in e['related'] if r in id2entry)
        parts.append(f'<section class="related"><h2>相关词条</h2><div class="chips">{rel}</div></section>')
    if backlinks:
        bl = ''.join(f'<a class="entry-link chip" href="{b}.html" data-id="{b}">{html.escape(id2entry[b]["title"])}</a>' for b in sorted(backlinks))
        parts.append(f'<section class="backlinks"><h2>反向链接（引用了本词条）</h2><div class="chips">{bl}</div></section>')
    return PAGE.format(title=html.escape(e['title']), content='\n'.join(parts))

def index_page(entries):
    cards = []
    for e in entries:
        tags = ' '.join(['t-' + e['type'], 'l-' + e['layer']] + ['p-' + p for p in e.get('paths', [])] + ['v-' + v for v in e.get('variables', [])])
        cards.append(f'''<a class="card {tags}" href="{e['id']}.html">
<div class="card-top"><span class="badge type-{e['type']}">{e['type']}</span><span class="src">{e['source']}</span></div>
<h3>{html.escape(e['title'])}</h3><p>{html.escape(e['summary'])}</p></a>''')
    types = sorted({e['type'] for e in entries})
    paths = sorted({p for e in entries for p in e.get('paths', [])})
    vars_ = sorted({v for e in entries for v in e.get('variables', [])})
    def chips(name, vals, pre):
        return '<div class="fgroup"><span class="flabel">' + name + '</span>' + ''.join(
            f'<button class="fchip" data-f="{pre}{v}">{v}</button>' for v in vals) + '</div>'
    content = f'''<header class="hero"><h1>《2072》知识库 · Part 4 机制词条原型</h1>
<p class="sub">词条 + 双向链接 + 悬停预览 + 渐进披露。{len(entries)} 个原型词条，源文本按节号构建时从 v149 提取，内容零改写。</p></header>
<div class="filters">{chips('类型', types, 't-')}{chips('路径', paths, 'p-')}{chips('变量', vars_, 'v-')}<button class="fchip clear" data-f="">清除筛选</button></div>
<div class="grid">{''.join(cards)}</div>'''
    return PAGE.format(title='词条总览', content=content)

# ---------- main ----------

def main():
    lines = load_v149()
    entries = [parse_entry(p) for p in sorted(glob.glob(os.path.join(ENTRY_DIR, '*.md')))]
    id2entry = {e['id']: e for e in entries}
    sec_map = {}
    for e in entries:
        if e.get('extract'):
            sec_map[e['extract'].replace('-intro', '').replace('-full', '')] = e['id']
    alias_map = sorted([(a, e['id']) for e in entries for a in e.get('aliases', [])],
                       key=lambda x: -len(x[0]))
    stats = {'resolved': [], 'unresolved': [], 'term_links': 0, 'term_edges': []}

    bodies = {}
    for e in entries:
        if e.get('extract'):
            sec = extract_section(lines, e['extract'])
            if sec is None:
                print(f'[错误] v149 中未找到节 {e["extract"]}（词条 {e["id"]}）', file=sys.stderr)
                sys.exit(1)
            raw = sec
        else:
            raw = e['body']
        h = md_to_html(raw)
        h = link_refs(h, sec_map, stats, e['id'])
        h = link_terms(h, alias_map, e['id'], stats)
        bodies[e['id']] = h

    # 事件词条接口声明字段：演练机制/可替换性/反向义务同样过节号链接解析（D-046③：真实超链接，构建时自动校验）
    ifaces = {}
    for e in entries:
        if e['type'] != '事件':
            continue
        ih = {}
        for field in ('mechanism_tested', 'substitutability', 'counter_obligation'):
            fh = md_to_html(e.get(field, ''))
            fh = link_refs(fh, sec_map, stats, e['id'])
            fh = link_terms(fh, alias_map, e['id'], stats)
            ih[field] = fh
        ifaces[e['id']] = ih

    backlinks = {}
    for src, _sec, tid in stats['resolved']:
        backlinks.setdefault(tid, set()).add(src)

    os.makedirs(OUT, exist_ok=True)
    for e in entries:
        with open(os.path.join(OUT, e['id'] + '.html'), 'w', encoding='utf-8') as f:
            f.write(entry_page(e, bodies[e['id']], backlinks.get(e['id'], set()), id2entry, ifaces.get(e['id'])))
    with open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(index_page(entries))
    data = {e['id']: {'title': e['title'], 'summary': e['summary'], 'type': e['type']} for e in entries}
    with open(os.path.join(OUT, 'data.js'), 'w', encoding='utf-8') as f:
        f.write('window.ENTRIES=' + json.dumps(data, ensure_ascii=False) + ';')
    for asset in ('style.css', 'app.js'):
        src = os.path.join(BASE, 'assets', asset)
        with open(src, encoding='utf-8') as fi, open(os.path.join(OUT, asset), 'w', encoding='utf-8') as fo:
            fo.write(fi.read())

    # ---------- 关联数据库（构建产物，词条 md 是唯一录入点） ----------
    edges = []
    seen_edge = set()
    def add_edge(src, dst, kind):
        k = (src, dst, kind)
        if k in seen_edge:
            return
        seen_edge.add(k)
        edges.append({'from': src, 'to': dst, 'kind': kind})
    for src, sec, tid in stats['resolved']:
        add_edge(src, tid, 'ref')          # 正文节号引用
    for src, tid in stats['term_edges']:
        add_edge(src, tid, 'term')         # 概念术语自动链接
    for e in entries:
        for r in e.get('related', []):
            if r in id2entry:
                add_edge(e['id'], r, 'related')   # 显式声明
        for c in e.get('children', []):
            if not c.startswith('~') and c in id2entry:
                add_edge(e['id'], c, 'child')     # 索引子项
    graph = {
        'built_from': 'entries/*.md + 2072_v149.md（本文件为构建产物，勿手工编辑）',
        'nodes': [{k: e.get(k) for k in ('id', 'title', 'type', 'layer', 'source', 'paths', 'domain', 'variables')} for e in entries],
        'edges': edges,
        'unresolved_refs': [{'from': s, 'section': sec} for s, sec in stats['unresolved']],
    }
    with open(os.path.join(OUT, 'graph.json'), 'w', encoding='utf-8') as f:
        json.dump(graph, f, ensure_ascii=False, indent=1)

    # ---------- entries.json：Astro 渲染层数据出口（2026-07-17，网站化落地 D-051①） ----------
    # 原则：build.py 仍是唯一解析器（extract/-full/-intro、节号链接、术语链接、反向链接），
    # Astro 只消费本文件做渲染，不重写任何解析逻辑。链接保持 "<id>.html" 形式，由 Astro 端统一改写为站内路由。
    export = []
    for e in entries:
        item = {k: e.get(k) for k in ('id', 'title', 'type', 'layer', 'source', 'extract',
                                       'paths', 'domain', 'variables', 'aliases', 'related',
                                       'children', 'note', 'time_span')}
        item['summary'] = e['summary']
        item['summary_html'] = inline_md(e['summary'])
        item['overview_html'] = md_to_html(e['overview'])
        # 英文层（D-070 双语同推）：三字段可缺（未翻译词条为 None），渲染层据此回退中文
        item['title_en'] = e.get('title_en') or None
        item['summary_en'] = e.get('summary_en') or None
        item['summary_en_html'] = inline_md(e['summary_en']) if e.get('summary_en') else None
        item['overview_en_html'] = md_to_html(e['overview_en']) if e.get('overview_en') else None
        item['note_html'] = inline_md(e['note']) if e.get('note') else None
        item['body_html'] = bodies[e['id']]
        if e['id'] in ifaces:
            item['interface_html'] = ifaces[e['id']]
        item['backlinks'] = sorted(backlinks.get(e['id'], set()))
        export.append(item)
    entries_json = {
        'built_from': f'entries/*.md + {os.path.basename(V149)}（构建产物，勿手工编辑；链接为 <id>.html 形式，渲染层负责改写路由）',
        'base_doc': os.path.basename(V149),
        'vars': VARS,
        'entries': export,
        'unresolved_refs': graph['unresolved_refs'],
    }
    with open(os.path.join(OUT, 'entries.json'), 'w', encoding='utf-8') as f:
        json.dump(entries_json, f, ensure_ascii=False, indent=1)

    # ---------- fulldoc.json：全文阅读视图数据出口（2026-07-17，门户重构） ----------
    # 按一级章→二级节切分基准文档全文，正文过同一套 md_to_html + 节号链接 + 术语链接管线。
    # 独立 stats（fd_stats），不污染词条图谱；"目录"章跳过（导航由站点自动生成）。
    CH_NUM = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7}
    def _chapter_slug(title):
        if title.startswith('前言'):
            return 'preface'
        if title.startswith('目录'):
            return None
        if title.startswith('速览页'):
            return 'overview'
        m = re.match(r'^第([一二三四五六七])部分', title)
        if m:
            return f'part{CH_NUM[m.group(1)]}'
        if title.startswith('附录A'):
            return 'appendix-a'
        if title.startswith('结语'):
            return 'epilogue'
        if title.startswith('关键字词典'):
            return 'dictionary'
        return None
    chapters, cur, cursec = [], None, None
    for l in lines:
        m1 = re.match(r'^#\s+(.*)$', l)
        m2 = re.match(r'^##\s+(.*)$', l) if not m1 else None
        if m1:
            cur = {'title': m1.group(1).strip(), 'intro': [], 'sections': []}
            chapters.append(cur)
            cursec = None
            continue
        if m2 and cur is not None:
            cursec = {'title': m2.group(1).strip(), 'lines': []}
            cur['sections'].append(cursec)
            continue
        (cursec['lines'] if cursec is not None else cur['intro'] if cur is not None else []).append(l)
    fd_stats = {'resolved': [], 'unresolved': [], 'term_links': 0, 'term_edges': []}
    def _render_doc(md_text, self_id):
        h = md_to_html(md_text)
        h = link_refs(h, sec_map, fd_stats, self_id)
        h = link_terms(h, alias_map, self_id, fd_stats)
        return h
    fd_chapters = []
    for ch in chapters:
        cslug = _chapter_slug(ch['title'])
        if cslug is None:
            continue
        fc = {'slug': cslug, 'title': ch['title'],
              'intro_html': _render_doc('\n'.join(ch['intro']).strip(), f'doc-{cslug}'),
              'sections': []}
        ov_count = 0
        for s in ch['sections']:
            mm = re.match(r'^([0-9A]+\.\d+)[　\s]+(.*)$', s['title'])
            mo = re.match(r'^速览([一二三四])[　\s]+(.*)$', s['title'])
            if mm:
                sec_no, stitle = mm.group(1), mm.group(2)
                sslug = sec_no.lower().replace('.', '-')
            elif mo:
                ov_count += 1
                sec_no, stitle = s['title'].split('　')[0] if '　' in s['title'] else f'速览{mo.group(1)}', mo.group(2)
                sslug = f'overview-{CH_NUM[mo.group(1)]}'
            else:
                sec_no, stitle = '', s['title']
                sslug = f'{cslug}-s{len(fc["sections"])+1}'
            fc['sections'].append({'slug': sslug, 'sec_no': sec_no, 'title': stitle,
                                    'html': _render_doc('\n'.join(s['lines']).strip(), f'doc-{sslug}')})
        fd_chapters.append(fc)
    fulldoc = {
        'built_from': f'{os.path.basename(V149)}（构建产物，勿手工编辑；全文阅读视图，内容零改写）',
        'base_doc': os.path.basename(V149),
        'chapters': fd_chapters,
    }
    with open(os.path.join(OUT, 'fulldoc.json'), 'w', encoding='utf-8') as f:
        json.dump(fulldoc, f, ensure_ascii=False, indent=1)
    n_secs = sum(len(c['sections']) for c in fd_chapters)
    print(f'全文阅读视图：{len(fd_chapters)} 章 / {n_secs} 节 → site/fulldoc.json'
          f'（节号链接解析 {len(fd_stats["resolved"])}，未收录 {len(set(s for _, s in fd_stats["unresolved"]))} 个节号，术语链接 {fd_stats["term_links"]} 处）')

    import sqlite3, tempfile, shutil
    dbp = os.path.join(OUT, 'entries.db')
    tmp = os.path.join(tempfile.gettempdir(), 'entries_build.db')  # 挂载盘不支持 SQLite 锁，先本地建库再拷回
    if os.path.exists(tmp):
        os.remove(tmp)
    db = sqlite3.connect(tmp)
    db.executescript('''
CREATE TABLE nodes(id TEXT PRIMARY KEY, title TEXT, type TEXT, layer TEXT, source TEXT,
                   paths TEXT, domain TEXT, variables TEXT, summary TEXT);
CREATE TABLE edges(src TEXT, dst TEXT, kind TEXT);
CREATE TABLE unresolved(src TEXT, section TEXT);
CREATE VIEW backlink_count AS SELECT dst AS id, COUNT(*) AS n FROM edges GROUP BY dst;
CREATE VIEW orphans AS SELECT id, title FROM nodes WHERE id NOT IN (SELECT dst FROM edges) AND id NOT IN (SELECT src FROM edges);
''')
    for e in entries:
        db.execute('INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?,?)',
                   (e['id'], e['title'], e['type'], e['layer'], e['source'],
                    ','.join(e.get('paths', [])), e.get('domain', ''),
                    ','.join(e.get('variables', [])), e['summary']))
    db.executemany('INSERT INTO edges VALUES(?,?,?)', [(x['from'], x['to'], x['kind']) for x in edges])
    db.executemany('INSERT INTO unresolved VALUES(?,?)', [(s, sec) for s, sec in stats['unresolved']])
    db.commit()
    orphans = list(db.execute('SELECT id FROM orphans'))
    db.close()
    shutil.copyfile(tmp, dbp)
    os.remove(tmp)

    print(f'构建完成：{len(entries)} 个词条 → site/')
    print(f'关联数据库：graph.json（节点{len(entries)}/边{len(edges)}）+ entries.db（视图：backlink_count、orphans）')
    if orphans:
        print(f'  孤儿词条（无出入边）：{", ".join(o[0] for o in orphans)}')
    print(f'节号引用解析：{len(stats["resolved"])} 个已解析为词条链接；{len(stats["unresolved"])} 个未收录（原型范围外，正式迁移时构建报错）')
    for src, sec in stats['unresolved']:
        print(f'  - [{src}] → {sec}节（未收录）')

    print(f'概念术语自动链接：{stats["term_links"]} 处')

if __name__ == '__main__':
    main()
