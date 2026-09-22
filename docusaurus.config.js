// @ts-check
// `@type` JSDoc annotations allow editor autocompletion and type checking
// (when paired with `@ts-check`).
// There are various equivalent ways to declare your Docusaurus config.
// See: https://docusaurus.io/docs/api/docusaurus-config

import { themes as prismThemes } from 'prism-react-renderer';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

// MediaWiki 在自己的 MathJax 配置里扩展了一批宏（\C \R \N \Z \Q \F \sgn …），
// 维基原文大量使用，但 KaTeX 不认识，页面上会渲染成红色 parse error。
// 这里把它们补上，新导入的条目不用再手工替换。
// 参考 https://en.wikipedia.org/wiki/Help:Displaying_a_formula
// docs/wow/capycraft 是 submodule，9711 篇魔兽数据，占全站 99.8%。
// 每次构建都要把这一万篇塞进 webpack，内存峰值非常高（默认堆会 OOM，
// 表现是 v8::FatalProcessOutOfMemory + zsh: abort），单次还要 30 分钟起。
// 改正文/样式时用  npm run build:slim  跳过它，一两分钟出结果；
// 正式发布不要加这个变量。产物写进 build-slim/，避免误把瘦身版发布出去。
const SKIP_WOW = process.env.SKIP_WOW === '1';
const DEFAULT_EXCLUDE = [
  '**/_*.{js,jsx,ts,tsx,md,mdx}',
  '**/_*/**',
  '**/*.test.{js,jsx,ts,tsx}',
  '**/__tests__/**',
];

const katexMacros = {
  '\\R': '\\mathbb{R}',
  '\\C': '\\mathbb{C}',
  '\\N': '\\mathbb{N}',
  '\\Z': '\\mathbb{Z}',
  '\\Q': '\\mathbb{Q}',
  '\\F': '\\mathbb{F}',
  '\\sgn': '\\operatorname{sgn}',
  '\\arccot': '\\operatorname{arccot}',
  '\\arcsec': '\\operatorname{arcsec}',
  '\\arccsc': '\\operatorname{arccsc}',
};

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: '中国百科',
  tagline: 'Dinosaurs are cool',
  favicon: 'img/favicon.ico',
  future: {
    v4: false,
    // 9711 篇 wow 页面用 webpack 编译，内存峰值很高（4G 堆会 OOM）。
    // 装了 @docusaurus/faster 之后用  npm run build:faster  打开：换成 Rspack + SWC，
    // 内存和时间都会明显下降。**没装这个包就别开**，Docusaurus 会直接报错退出。
    ...(process.env.FASTER === '1' ? { experimental_faster: true } : {}),
  },
  trailingSlash: false,

  // Set the production url of your site here
  url: 'https://zh.chinapedia.org',
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: '/',

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: 'liruqi', // Usually your GitHub org/user name.
  projectName: 'zh.chinapedia', // Usually your repo name.

  onBrokenLinks: 'log',

  // 瘦身材构建（SKIP_WOW=1）单独输出到 build-slim/，别覆盖正式产物
  outDir: SKIP_WOW ? 'build-slim' : 'build',

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'zh-Hans',
    locales: ['zh-Hans'],
  },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: './sidebars.js',
          routeBasePath: 'wiki',
          exclude: SKIP_WOW ? ['wow/**', ...DEFAULT_EXCLUDE] : DEFAULT_EXCLUDE,
          remarkPlugins: [remarkMath],
          rehypePlugins: [[rehypeKatex, { macros: katexMacros }]],
          // Please change this to your repo.
          // Remove this to remove the "edit this page" links.
          editUrl: ({ docPath }) => {
            if (docPath.startsWith('wow/capycraft/')) {
              return `https://github.com/liruqi/capycraft/edit/main/${docPath.substring(
                'wow/capycraft/'.length,
              )}`;
            }
            return `https://github.com/liruqi/zh.chinapedia/edit/main/docs/${docPath}`;
          },
        },
        blog: {
          showReadingTime: true,
          feedOptions: {
            type: ['rss', 'atom'],
            xslt: true,
          },
          // Please change this to your repo.
          // Remove this to remove the "edit this page" links.
          editUrl: 'https://github.com/liruqi/zh.chinapedia/edit/main/blog/',
          // Useful options to enforce blogging best practices
          onInlineTags: 'warn',
          onInlineAuthors: 'warn',
          onUntruncatedBlogPosts: 'ignore',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
      }),
    ],
  ],
  stylesheets: [
    {
      href: 'https://cdn.jsdelivr.net/npm/katex@0.16.47/dist/katex.min.css',
      type: 'text/css',
      integrity: 'sha384-nH0MfJ44wi1dd7w6jinlyBgljjS8EJAh2JBoRad8a3VDw2K69vfaaqm4WnR+gXtA',
      crossorigin: 'anonymous',
    },
  ],
  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      // Replace with your project's social card (used for Open Graph)
      image: 'img/docusaurus-social-card.jpg',
      // Global meta tags (including Twitter Card)
      metadata: [
        { name: 'twitter:card', content: 'summary_large_image' },
        { name: 'twitter:site', content: '@zhchinapedia' },
        { name: 'twitter:creator', content: '@zhchinapedia' },
        { name: 'og:locale', content: 'zh_CN' },
        { name: 'og:type', content: 'website' },
        { name: 'og:site_name', content: '中国百科' },
      ],
      colorMode: {
        respectPrefersColorScheme: true,
      },
      navbar: {
        title: '中国百科',
        logo: {
          alt: 'My Site Logo',
          src: 'img/logo.svg',
        },
        items: [
          {
            type: 'docSidebar',
            sidebarId: 'tutorialSidebar',
            position: 'left',
            label: '条目',
          },
          { to: '/blog', label: '博客', position: 'left' },
          {
            href: 'https://github.com/liruqi/zh.chinapedia',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },
      footer: {
        style: 'dark',
        links: [
          {
            title: 'Docs',
            items: [
              {
                label: '条目',
                to: '/wiki/intro',
              },
            ],
          },
          {
            title: 'Community',
            items: [
              {
                label: 'Stack Overflow',
                href: 'https://stackoverflow.com/questions/tagged/docusaurus',
              },
              {
                label: 'Discord',
                href: 'https://discordapp.com/invite/docusaurus',
              },
              {
                label: 'X',
                href: 'https://x.com/docusaurus',
              },
            ],
          },
          {
            title: 'More',
            items: [
              {
                label: 'Blog',
                to: '/blog',
              },
              {
                label: 'GitHub',
                href: 'https://github.com/liruqi/zh.chinapedia',
              },
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} 中国百科. Built with Docusaurus.`,
      },
      prism: {
        theme: prismThemes.github,
        darkTheme: prismThemes.dracula,
      },
    }),
};

export default config;
