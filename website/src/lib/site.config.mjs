// 站点配置（渲染层，不涉词条内容）
export const site = {
  title: '2072',
  tagline: '一部关于 2026—2076 年的世界观文档',
};

// giscus 评论（基于 GitHub Discussions）。启用步骤（Sean 宿主侧，一次性）：
// 1. GitHub 仓库 Settings → General → Features 勾选 Discussions
// 2. 安装 https://github.com/apps/giscus 到本仓库
// 3. 打开 https://giscus.app，选仓库 Sean2047/2072 与分类（建议 Announcements 或 General），
//    页面下方生成的代码里有 data-repo-id 与 data-category-id，填到下面两个字段后重新部署
export const giscus = {
  repo: 'Sean2047/2072',
  repoId: '',        // ← 从 giscus.app 获取后填入
  category: 'General',
  categoryId: '',    // ← 从 giscus.app 获取后填入
  mapping: 'pathname',
  lang: 'zh-CN',
};
