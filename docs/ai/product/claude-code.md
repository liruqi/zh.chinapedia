---
title: Claude Code
description: 包含 2026-03-31 源代码泄漏事件更新
date: 2026-03-31
sources:
  - Google AI Overview
  - Byteiota (2026-03-31)
  - Dev.to (2026-03-31)
  - LowCode Agency (2026-03-31)
---

# Claude Code

**Claude Code** 是由 Anthropic 开发的智能 AI 编码工具,直接嵌入你的开发环境。与简单的自动补全工具不同,它可以读取你的代码库、规划复杂功能、编辑多个文件,并自主执行终端命令来修复 bug 和构建功能[^1]。

## Key Capabilities

- **Full Codebase Context**: 自动索引项目文件,无需手动上传上下文
- **Terminal Integration**: 直接从命令行运行构建、测试和 git 操作(如创建提交和 PR)
- **Plan Mode**: 在编写代码前审查结构化变更计划,确保符合意图[^2]
- **Agentic Workflows**: 可生成子代理并行处理任务(如研究竞品、管理 bug 待办清单)
- **Customization**: 通过 `CLAUDE.md` 文件存储项目规则,或创建 "Skills" 自动化部署等重复工作流[^3]

## Ways to Use Claude Code

- **Terminal (CLI)**: 在本地运行 Claude 的主要方式[^4]
- **VS Code Extension**: 提供图形界面,支持并排差异对比和行内批注[^5]
- **Desktop App**: 独立应用,适合希望跳过终端的用户,提供 PR 监控和服务器预览的视觉工具[^6][^7]
- **Web Interface**: 在 https://claude.ai/code 使用,运行在 Anthropic 管理的云基础设施上,支持远程工作[^8]

## Pricing & Access

Claude Code 通常包含在 Anthropic 的付费计划中:

- **Pro**: 20 美元/月
- **Max**: 100–200 美元/月(更高使用限额)
- **Team & Enterprise**: 按席位定价,含额外安全和管理功能
- **Console**: 按标准 API 费率计费(即用即付)[^9]

## Getting Started

- **Installation**[^10]:
  - macOS/Linux: `curl -fsSL https://claude.ai | sh`
  - Windows: `irm https://claude.ai/install.ps1 | iex`(PowerShell)
- **Authentication**: 在终端运行 `claude`,按浏览器提示登录
- **Initialization**: 在项目文件夹中运行 `/init` 初始化环境

## 2026-03-31 源代码泄漏事件

### 事件概述

2026 年 3 月 31 日,Anthropic 的 Claude Code 源代码因 **npm 包配置错误** 意外公开。安全研究员 **Chaofan Shou** 发现发布的 npm 包中包含 source map 文件,该文件指向一个 R2 存储桶,暴露了完整的未混淆 TypeScript 代码库[^11]。

> **重要区分**:泄漏的是 **Claude Code CLI 工具的源代码**,而非 Claude AI 模型本身。模型权重、训练数据和核心基础设施未受影响[^12][^13]。

### 泄漏规模

- **512,000+ 行** TypeScript 代码
- **~1,900 个** 文件
- **~40 个** 权限控制的工具(base tool definition alone 29,000 行)
- **46,000 行** 查询引擎(query engine)
- 多代理编排系统、IDE bridge、持久化内存系统
- 未发布功能:如 "Kairos" 模式和 "Buddy" 伴侣系统

原始泄漏版本的代码存档于 Radicle 网络[^15]。社区基于泄漏代码重写为 [claw-code](https://github.com/instructkr/claw-code),当前 ⭐ **62K+**、⑂ **64K+**[^14]*(数据截至 2026-04-01)*。

### 技术原因

Claude Code 使用 **Bun** 作为运行时,默认生成 source map 文件。由于 `.npmignore` 或 `package.json` 的 `files` 字段配置错误,`.map` 文件被包含在生产发布的 npm 包中。source map 直接引用了 R2 存储桶中的原始 TypeScript 源码,导致完整代码库公开[^16]。

这与同一日发生的 **Axios npm 供应链攻击**(受感染维护者账户部署 RAT)形成对比——此次泄漏是配置失误,而非针对性攻击[^17]。

### 影响评估

| 项目 | 状态 |
|------|------|
| Claude AI 模型权重 | ✅ 未泄漏 |
| 训练数据 | ✅ 未泄漏 |
| API 密钥 | ✅ 未泄漏 |
| 用户数据 | ✅ 未泄漏 |
| Claude Code CLI 源码 | ⚠️ 已公开 |

**对用户的影响**:
- **API 用户 / SaaS 构建者**:无直接风险,API 密钥和数据未暴露
- **Claude Code 用户**:工具功能不受影响,可继续正常使用
- **企业客户**:核心基础设施和模型能力保持安全

**对 Anthropic 的影响**[^18][^19]:
- 知识产权暴露:内部架构、工具实现、未发布功能细节公开
- 竞争情报流失:竞争对手可研究其 CLI 设计
- 信任影响:五天内的第二起重大配置失误(3 月 26 日 CMS 配置错误曾暴露 Claude Mythos 模型细节)

### 用户建议

- **无需特殊行动**:继续正常使用 Claude Code
- **npm 发布者**:运行 `npm pack --dry-run` 验证发布内容;确保 `.map` 文件被排除[^20]
- **谨慎下载**:泄漏仓库可能携带恶意软件;仅通过可信分析师的技术文章了解架构[^21]
- **关注官方更新**:Anthropic 可能发布安全建议或工具更新[^22]

### 技术亮点(值得学习)

尽管是意外泄漏,代码库展示了高质量的工程实践[^23]:

- **工具系统**:~40 个权限隔离的工具,base definition 达 29K 行
- **查询引擎**:46K 行,处理所有 LLM API 调用、流式传输、缓存
- **多代理编排**:支持 "swarms" 并行任务
- **IDE Bridge**:JWT 认证通道连接 VS Code/JetBrains 扩展
- **技术栈**:Bun(运行时) + React+Ink(终端 UI) + Zod v4(验证) + ~50 个 slash 命令
- **懒加载**:OpenTelemetry、gRPC 等重型依赖按需加载

## 脚注

[^1]: Anthropic. (n.d.). [Claude Code Overview](https://code.claude.com/docs/en/overview). Claude Code Documentation.
[^2]: Anthropic. (n.d.). [How Claude Code Works](https://code.claude.com/docs/en/how-claude-code-works). Claude Code Documentation.
[^3]: Anthropic. (n.d.). [Skills Documentation](https://code.claude.com/docs/en/skills). Claude Code Documentation.
[^4]: Anthropic. (n.d.). [Quickstart Guide](https://code.claude.com/docs/en/quickstart). Claude Code Documentation.
[^5]: Anthropic. (n.d.). [VS Code Extension](https://code.claude.com/docs/en/vs-code). Claude Code Documentation.
[^6]: Anthropic. (n.d.). [Use Claude Code Desktop](https://code.claude.com/docs/en/desktop). Claude Code Documentation.
[^7]: Anthropic. (n.d.). [Get started with the desktop app](https://code.claude.com/docs/en/desktop-quickstart). Claude Code Documentation.
[^8]: Anthropic. (n.d.). [Claude Code on the Web](https://code.claude.com/docs/en/claude-code-on-the-web). Claude Code Documentation.
[^9]: Anthropic. (n.d.). [Console & API Pricing](https://claude.com/product/claude-code). Claude Product Page.
[^10]: Anthropic. (n.d.). [Advanced setup](https://code.claude.com/docs/en/setup). Claude Code Documentation.
[^11]: Byteiota. (2026-03-31). ["Claude Code Source Leaked via npm: 512K Lines Exposed"](https://byteiota.com/claude-code-source-leaked-via-npm-512k-lines-exposed/). Retrieved 2026-04-01.
[^12]: Dev.to. (2026-03-31). ["Claude Code's Entire Source Code Was Just Leaked via npm Source Maps — Here's What's Inside"](https://dev.to/gabrielanhaia/claude-codes-entire-source-code-was-just-leaked-via-npm-source-maps-heres-whats-inside-cjo). Retrieved 2026-04-01.
[^13]: LowCode Agency. (2026-03-31). ["Claude Code Source Code Leaked? Here's what it contains"](https://www.lowcode.agency/blog/claude-code-source-code-leaked). Retrieved 2026-04-01.
[^14]: LowCode Agency. (2026-03-31). *Note: Community rewrite at [github.com/instructkr/claw-code](https://github.com/instructkr/claw-code) (62K★, 64K⑂ as of 2026-04-01)*.
[^15]: Original leak archive (Radicle): unavailable after content removal.
[^16]: SocRadar. (2026-03-31). ["Claude Code Leak: What You Need to Know"](https://socradar.io/blog/claude-code-leak-what-to-know/). Retrieved 2026-04-01.
[^17]: Penligent.ai. (2026-03-31). ["Claude Code Source Map Leak, What Was Exposed and What It Means"](https://www.penligent.ai/hackinglabs/claude-code-source-map-leak-what-was-exposed-and-what-it-means/). Retrieved 2026-04-01.
[^18]: VentureBeat. (2026-03-31). ["Claude Code's source code appears to have leaked: here's what we know"](https://venturebeat.com/technology/claude-codes-source-code-appears-to-have-leaked-heres-what-we-know/). Retrieved 2026-04-01.
[^19]: Analytics India Magazine. (2026-03-31). ["Anthropic Accidentally Leaks Claude Code Source Code"](https://analyticsindiamag.com/ai-news/anthropic-accidentally-leaks-claude-code-source-code). Retrieved 2026-04-01.
[^20]: Unix geeks. (2026-03-31). [`npm pack --dry-run`: verify package contents before publish](https://docs.npmjs.com/cli/v10/commands/npm-pack#dry-run). Retrieved 2026-04-01.
[^21]: Cybernews. (2026-03-31). ["Full source code for Anthropic's Claude Code leaks"](https://cybernews.com/security/anthropic-claude-code-source-leak/). Retrieved 2026-04-01.
[^22]: Anthropic. (2026-04-01). [Official Updates](https://claude.ai/). Claude Website.
[^23]: Additional analysis: Binance Square (2026-03-31) ["AI TRENDS | Anthropic's Claude Code Source Map Leak Raises Security Concerns"](https://www.binance.com/en/square/post/03-31-2026-ai-trends-anthropic-s-claude-code-source-map-leak-raises-security-concerns-307441743455202). Retrieved 2026-04-01.

**Learning resources**:

[^24]: freeCodeCamp. ["The Claude Code Handbook"](https://www.freecodecamp.org/news/claude-code-handbook/). Retrieved 2026-04-01.
[^25]: Product Talk. ["Claude Code: What It Is and How It's Different"](https://www.producttalk.org/claude-code-what-it-is-and-how-its-different/). Retrieved 2026-04-01.
[^26]: Leo Godin (Medium). ["Claude Code is Great"](https://leo-godin.medium.com/claude-code-is-great-6db35d8685f0). Retrieved 2026-04-01.
[^27]: Tech With Tim (YouTube). ["Introducing Claude Code"](https://www.youtube.com/watch?v=AJpK3YTTKZ4). Retrieved 2026-04-01.
[^28]: YouTube. ["Claude Code - Full Tutorial for Beginners"](https://www.youtube.com/watch?v=ntDIxaeo3Wg). Retrieved 2026-04-01.
