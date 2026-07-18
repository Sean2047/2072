# 2072 知识库网站（Astro 渲染层）

建立：2026-07-17。落地 D-051①（Astro + GitHub Actions 自动构建部署）。

## 架构：两段式

```
website_prototype/entries/*.md ──┐
2072_vNNN.md（基准文档）──────────┤→ build.py → site/entries.json + graph.json
                                  │  check_entries.py → site/jianyu.json（并做校验闸门）
                                  └────────────→ 本项目（Astro）→ dist/ 静态站点
```

- **build.py 是唯一解析器**：原文抽取（extract/-intro/-full）、节号→链接、术语链接、反向链接全部在 Python 侧；本项目只消费 `site/entries.json` 等产物做渲染，不重写任何解析逻辑。
- 词条源文件与内容仍归 `website_prototype/`，本项目零内容——改词条不需要动这里。

## 本地构建

```
python3 ../website_prototype/build.py        # 产出 site/entries.json 等
python3 ../website_prototype/check_entries.py  # 产出 site/jianyu.json + 校验
npm install
npm run build     # 或 npm run dev 起开发服务器
```

环境变量：`DATA_DIR`（覆盖数据目录，默认 `../website_prototype/site`）、`ASTRO_BASE`（部署路径前缀，CI 里为 `/2072`，本地默认 `/`）。

## 页面

- `/` 词条总览：层/类型/路径/变量筛选 + 领域下拉 + 全文搜索
- `/entries/<id>/` 词条页：三层渐进披露（摘要→概述→完整原文）；事件词条渲染接口声明四字段；本节词条/相关词条/反向链接（ref/term/related 三类入边）
- `/graph/` 知识图谱：canvas 力导向，按边类型与节点层过滤
- `/dict/` 关键字词典：77 术语 + "见于"列（构建自动重生成）

- `/objections/` 反对文集、`/documents/` 文内文献（D-074增区，导航九项）：占位页+登记表篇目列表；
  外部作品经 `website_prototype/external_works.json` 登记后，被指向词条页与全文分节页自动渲染指针区，
  词条页另支持可选 `intro_plain` 入口段（渲染于三层披露之前）。站点页脚含 CC BY-NC-ND 4.0 许可声明。

i18n：Astro i18n 路由已配置（zh 默认无前缀，en 预留 `/en/`，D-050 翻译后置）。

## 部署

`.github/workflows/deploy.yml`（仓库根）：push 到 main → build.py + check_entries.py（词条校验失败即构建失败）→ astro build → GitHub Pages。
首次启用需在 GitHub 仓库 Settings → Pages → Source 选 "GitHub Actions"。

## VM 注意（Cowork 会话）

npm/astro 不要直接在挂载目录跑（慢且有锁风险）：把 website/ 拷到 /tmp 构建，DATA_DIR 指回挂载的 site/ 即可；产物 dist/ 不入版本管理，无需拷回。
