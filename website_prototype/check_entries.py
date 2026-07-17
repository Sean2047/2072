# -*- coding: utf-8 -*-
"""词条层校对与对齐脚本（与 check_2072.py 双轨并行，D-046③/D-049）。

用法:
  python3 check_entries.py                # 全量检查
  python3 check_entries.py --update-lock  # 确认漂移已消化后，刷新原文哈希基线

检查项:
  [S] frontmatter schema（必填字段、取值域、ID 唯一性）
  [L] layer 与重整工作文件第2节分派清单对账
  [D] 原文漂移检测（extract 哈希 vs entries.lock.json 基线）
  [R] 引用分级（真悬空=节号在 v149 不存在，报错；待切分=存在但无词条，提示）
  [C] 切分进度对账（按分派清单统计已切分/待切分）
  [J] 概念术语"见于"表重生成（登记项12：替代词典过时的"见于"列）→ site/jianyu.json
  [V] source 字段可验证性格式校验（D-051③：须含"§节号 第N段"或"词典"等可定位锚点，否则告警）
退出码: 有 ERROR 为 1，否则 0。
"""
import os, re, sys, json, glob, hashlib
from build import parse_entry, extract_section, load_v149, ENTRY_DIR, BASE, SEC_REF

LOCK = os.path.join(BASE, 'entries.lock.json')
PROJ = os.path.join(BASE, '..')

VALID_TYPE = {'概念', '章节', '事件', '索引'}
VALID_LAYER = {'理论', '事件', '技术'}
VALID_PATHS = {'A1', 'A2', 'B1', 'B2', 'C', 'D', 'E', '全路径'}
VALID_VARS = {f'V{i}' for i in range(1, 9)}
REQUIRED = ('id', 'title', 'type', 'layer', 'source', 'summary', 'overview')
EVENT_REQUIRED = ('time_span', 'mechanism_tested', 'substitutability', 'counter_obligation')  # 接口声明四字段（D-046③升级版模板）
DOMAIN_LIST = os.path.join(BASE, 'domain清单.md')

errors, warns, infos = [], [], []

def load_domain_whitelist():
    """解析 domain清单.md：已登记域表格首列 + 待登记列表中的技术/xx 条目（D-051②）。
    经济/xx 全系列蓝图预批，不需逐条登记（清单文件末尾维护规则已声明）。"""
    if not os.path.exists(DOMAIN_LIST):
        warns.append('[S] domain清单.md 缺失，domain 取值域校验跳过')
        return None
    text = open(DOMAIN_LIST, encoding='utf-8').read()
    explicit = set()
    for m in re.finditer(r'^\|\s*((?:经济|技术|地缘|总纲|社会|地理)/[^\s|]+)\s*\|', text, re.M):
        explicit.add(m.group(1))
    for m in re.finditer(r'^-\s*((?:经济|技术|地缘|总纲|社会|地理)/[^\s（(，,]+)', text, re.M):
        explicit.add(m.group(1))
    return explicit

DOMAIN_WHITELIST = load_domain_whitelist()

def domain_valid(d):
    if not d:
        return True  # domain 非必填字段，缺失不在此处报错
    if d.startswith('经济/'):
        return True  # 蓝图预批
    if DOMAIN_WHITELIST is None:
        return True  # 清单缺失时不阻塞（已告警）
    return d in DOMAIN_WHITELIST

def latest_workfile():
    cands = glob.glob(os.path.join(PROJ, '2072_重整工作文件_v*.md'))
    def ver(p):
        m = re.search(r'_v(\d+)\.md$', p)
        return int(m.group(1)) if m else -1
    return max(cands, key=ver) if cands else None

def parse_assignment(path):
    """解析第2节归属清单：{节号: layer}。决定归属取单元格内首个 理论|技术|事件。
    注：VM 挂载缓存可能把宿主刚编辑的文件按旧长度截断（多字节字符切半），
    这里用容错解码避免崩溃，并在发现坏字节时告警（清单表通常不在截断点附近）。"""
    raw = open(path, 'rb').read()
    text = raw.decode('utf-8', errors='replace')
    if '�' in text:
        warns.append(f'[L] {os.path.basename(path)} 读取到坏字节（疑似挂载缓存截断）——清单解析继续，结果需人工复核；'
                     f'可稍后重跑或在宿主侧确认文件完整')
    amap = {}
    for line in text.split('\n'):
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 5 or cells[0] in ('节号', '---') or set(cells[0]) <= {'-'}:
            continue
        sec = cells[0].replace('–', '-')
        m = re.search(r'(理论|技术|事件)', cells[3])
        if m and re.match(r'^(\d+\.\d+(\.\d+(-\d+\.\d+\.\d+)?)?|[A-Z]\.\d|速览.)$', sec):
            amap[sec] = m.group(1)
    return amap

def v149_headings(lines):
    hs = set()
    for l in lines:
        m = re.match(r'^#{2,4}\s+(\d+\.\d+(?:\.\d+){0,2})　', l)
        if m:
            hs.add(m.group(1))
    return hs

def main():
    update_lock = '--update-lock' in sys.argv
    lines = load_v149()
    headings = v149_headings(lines)
    entries = [parse_entry(p) for p in sorted(glob.glob(os.path.join(ENTRY_DIR, '*.md')))]
    wf = latest_workfile()
    amap = parse_assignment(wf) if wf else {}
    if not amap:
        warns.append('[L] 未能从重整工作文件解析分派清单，layer 对账跳过')

    # [S] schema
    ids = {}
    for e in entries:
        eid = e.get('id', '?')
        if eid in ids:
            errors.append(f'[S] 词条 ID 重复：{eid}')
        ids[eid] = e
        for k in REQUIRED:
            if not e.get(k):
                errors.append(f'[S] {eid}: 缺必填字段 {k}')
        if e.get('type') not in VALID_TYPE:
            errors.append(f'[S] {eid}: type 取值非法 "{e.get("type")}"')
        if e.get('layer') not in VALID_LAYER:
            errors.append(f'[S] {eid}: layer 取值非法 "{e.get("layer")}"')
        if e.get('type') == '事件':
            for k in EVENT_REQUIRED:
                if not e.get(k):
                    errors.append(f'[S] {eid}: 事件词条缺接口声明字段 {k}（第3节模板/D-046③）')
        for p in e.get('paths', []):
            if p not in VALID_PATHS:
                errors.append(f'[S] {eid}: paths 取值非法 "{p}"')
        for v in e.get('variables', []):
            if v not in VALID_VARS:
                errors.append(f'[S] {eid}: variables 取值非法 "{v}"')
        if not domain_valid(e.get('domain', '')):
            errors.append(f'[S] {eid}: domain "{e.get("domain")}" 不在 domain清单.md 登记范围（D-051②），先登记再使用')
        for r in e.get('related', []):
            if r not in {x.get('id') for x in entries}:
                errors.append(f'[S] {eid}: related 指向不存在的词条 "{r}"')

    # [L] layer 对账（仅 extract 型词条；概念词条无对应清单行）
    for e in entries:
        sec = (e.get('extract') or '').replace('-intro', '').replace('-full', '')
        if not sec or not amap:
            continue
        assigned, probe = None, sec
        while assigned is None and probe.count('.') >= 1:  # 三/四级节逐级回退继承二级节分派
            assigned = amap.get(probe)
            if probe.count('.') == 1:
                break
            probe = probe.rsplit('.', 1)[0]
        if assigned is None:
            warns.append(f'[L] {e["id"]}: 节 {sec} 不在分派清单中')
        elif assigned != e['layer']:
            errors.append(f'[L] {e["id"]}: layer="{e["layer"]}" 与分派清单 "{assigned}"（节{sec}）不符')

    # [D] 原文漂移
    lock = json.load(open(LOCK, encoding='utf-8')) if os.path.exists(LOCK) else {}
    new_lock = {}
    for e in entries:
        if not e.get('extract'):
            continue
        text = extract_section(lines, e['extract'])
        if text is None:
            errors.append(f'[D] {e["id"]}: v149 中找不到节 {e["extract"]}')
            continue
        h = hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]
        new_lock[e['id']] = {'section': e['extract'], 'hash': h}
        old = lock.get(e['id'])
        if old and old['hash'] != h:
            warns.append(f'[D] {e["id"]}: 节 {e["extract"]} 原文已变动——summary/overview 需人工复核后 --update-lock')
        elif not old and not update_lock:
            infos.append(f'[D] {e["id"]}: 无哈希基线（首次运行请 --update-lock 建立）')
    if update_lock:
        json.dump(new_lock, open(LOCK, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        infos.append(f'[D] 哈希基线已更新：{len(new_lock)} 条 → entries.lock.json')

    # [R] 引用分级（事件层扩展：接口声明四字段中的source_text prose也纳入扫描——事件层方法文档v1第2节登记的已知缺口，本轮随事件层批量顺手核销）
    entried_secs = {e['extract'].replace('-intro', '').replace('-full', '') for e in entries if e.get('extract')}
    for e in entries:
        raw = e['body'] if not e.get('extract') else (extract_section(lines, e['extract']) or '')
        texts = [raw]
        if e.get('type') == '事件':
            for k in ('mechanism_tested', 'substitutability', 'counter_obligation'):
                if e.get(k):
                    texts.append(e[k])
        for text in texts:
            for m in SEC_REF.finditer(text):
                sec = m.group(1)
                if sec in entried_secs:
                    continue
                if sec in headings:
                    infos.append(f'[R] {e["id"]} → {sec}节：待切分（清单内，构建时高亮）')
                else:
                    errors.append(f'[R] {e["id"]} → {sec}节：真悬空（v149 无此节）')

    # [V] source 字段可验证性格式校验（D-051③/登记项⑥：summary/overview 的机制判断须可定位回原文）
    for e in entries:
        eid = e.get('id', '?')
        src = e.get('source', '')
        if not src:
            continue  # 缺失已由 [S] 报错
        if not re.search(r'§|词典|第[一二三四五六七八九十\d]+段', src):
            warns.append(f'[V] {eid}: source "{src}" 未见"§节号/第N段/词典"等可定位锚点，不满足D-051③可验证性要求')

    # [C] 切分进度（仅统计三级节可切分单元；索引词条按二级节计）
    lvl2 = [s for s in amap if re.match(r'^\d+\.\d+$', s)]
    done2 = {s for s in lvl2 if any(x == s or x.startswith(s + '.') for x in entried_secs)}
    infos.append(f'[C] 分派清单二级节 {len(lvl2)} 个，已有词条覆盖（含部分覆盖）{len(done2)} 个：{", ".join(sorted(done2)) or "无"}')

    # [J] "见于"表重生成
    concepts = [e for e in entries if e.get('aliases')]
    if concepts:
        sec_texts, cur = {}, None
        for l in lines:
            m = re.match(r'^#{2,3}\s+(\d+\.\d+(?:\.\d+)?)　', l)
            if m:
                cur = m.group(1)
                sec_texts[cur] = []
            elif cur:
                sec_texts[cur].append(l)
        jianyu = {}
        for c in concepts:
            hits = [s for s, ls in sec_texts.items()
                    if any(a in '\n'.join(ls) for a in c['aliases'])]
            jianyu[c['id']] = {'title': c['title'], 'aliases': c['aliases'], 'seen_in': sorted(hits)}
            infos.append(f'[J] {c["title"]}: 现行文本见于 {len(hits)} 节（词典"见于"列勿沿用，登记项12）')
        outp = os.path.join(BASE, 'site', 'jianyu.json')
        os.makedirs(os.path.dirname(outp), exist_ok=True)
        json.dump(jianyu, open(outp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # 报告
    print(f'check_entries：{len(entries)} 词条 | 对账基准：{os.path.basename(wf) if wf else "无"}')
    for x in errors: print('ERROR ', x)
    for x in warns:  print('WARN  ', x)
    for x in infos:  print('INFO  ', x)
    print(f'结果：{len(errors)} 错误 / {len(warns)} 警告 / {len(infos)} 提示')
    sys.exit(1 if errors else 0)

if __name__ == '__main__':
    main()
