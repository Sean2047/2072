// 2072 知识库网站（D-051①：Astro + GitHub Actions 自动构建部署）
// 数据流：website_prototype/build.py 产出 site/entries.json 等 → 本项目只做渲染层，不重写解析逻辑。
// 本地开发 base='/'；CI 部署到 GitHub Pages 时由 ASTRO_BASE 注入 '/2072'。
import { defineConfig } from 'astro/config';

export default defineConfig({
  site: process.env.ASTRO_SITE ?? 'https://sean2047.github.io',
  base: process.env.ASTRO_BASE ?? '/',
  trailingSlash: 'always',
  // i18n 路由预留（D-050：英文版规划先行、翻译后置）：中文默认无前缀，英文将来落 /en/
  i18n: {
    defaultLocale: 'zh',
    locales: ['zh', 'en'],
    routing: { prefixDefaultLocale: false },
  },
});
