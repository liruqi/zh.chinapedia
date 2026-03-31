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

# Claude Code Overview

**Claude Code** 是由 [Anthropic](https://code.claude.com/docs/en/overview) 开发的智能 AI 编码工具，直接嵌入你的开发环境。与简单的自动补全工具不同，它可以读取你的代码库、规划复杂功能、编辑多个文件，并自主执行终端命令来修复 bug 和构建功能。

## Key Capabilities

- **Full Codebase Context**: 自动索引项目文件，无需手动上传上下文
- **Terminal Integration**: 直接从命令行运行构建、测试和 git 操作（如创建提交和 PR）
- **Plan Mode**: 在编写代码前审查结构化变更计划，确保符合意图
- **Agentic Workflows**: 可生成子代理并行处理任务（如研究竞品、管理 bug 待办清单）
- **Customization**: 通过 `CLAUDE.md` 文件存储项目规则，或创建 "Skills" 自动化部署等重复工作流

## Ways to Use Claude Code

- **Terminal (CLI)**: 在本地运行 Claude 的主要方式
- **VS Code Extension**: 提供图形界面，支持并排差异对比和行内批注
- **Desktop App**: 独立应用，适合希望跳过终端的用户，提供 PR 监控和服务器预览的视觉工具
- **Web Interface**: 在 https://claude.ai/code 使用，运行在 Anthropic 管理的云基础设施上，支持远程工作

## Pricing & Access

Claude Code 通常包含在 Anthropic 的付费计划中：

- **Pro**: 20 美元/月
- **Max**: 100–200 美元/月（更高使用限额）
- **Team & Enterprise**: 按席位定价，含额外安全和管理功能
- **Console**: 按标准 API 费率计费（即用即付）

## Getting Started

- **Installation**:
  - macOS/Linux: `curl -fsSL https://claude.ai | sh`
  - Windows: `irm https://claude.ai/install.ps1 | iex`（PowerShell）
- **Authentication**: 在终端运行 `claude`，按浏览器提示登录
- **Initialization**: 在项目文件夹中运行 `/init` 初始化环境

## 2026-03-31 源代码泄漏事件

### 事件概述

2026 年 3 月 31 日，Anthropic 的 Claude Code 源代码因 **npm 包配置错误** 意外公开。安全研究员 **Chaofan Shou** 发现发布的 npm 包中包含 source map 文件，该文件指向一个 R2 存储桶，暴露了完整的未混淆 TypeScript 代码库。

> **重要区分**：泄漏的是 **Claude Code CLI 工具的源代码**，而非 Claude AI 模型本身。模型权重、训练数据和核心基础设施未受影响。

### 泄漏规模

- **512,000+ 行** TypeScript 代码
- **~1,900 个** 文件
- **~40 个** 权限控制的工具（base tool definition  alone 29,000 行）
- **46,000 行** 查询引擎（query engine）
- 多代理编排系统、IDE bridge、持久化内存系统
- 未发布功能：如 "Kairos" 模式和 "Buddy" 伴侣系统

泄漏代码已存档至 GitHub 仓库（如 [github.com/instructkr/claude-code](https://github.com/instructkr/claude-code)），数小时内获得 **1,100+ stars** 和 **1,900+ forks**。

### 技术原因

Claude Code 使用 **Bun** 作为运行时，默认生成 source map 文件。由于 `.npmignore` 或 `package.json` 的 `files` 字段配置错误，`.map` 文件被包含在生产发布的 npm 包中。source map 直接引用了 R2 存储桶中的原始 TypeScript 源码，导致完整代码库公开。

这与同一日发生的 **Axios npm 供应链攻击**（受感染维护者账户部署 RAT）形成对比——此次泄漏是配置失误，而非针对性攻击。

### 影响评估

| 项目 | 状态 |
|------|------|
| Claude AI 模型权重 | ✅ 未泄漏 |
| 训练数据 | ✅ 未泄漏 |
| API 密钥 | ✅ 未泄漏 |
| 用户数据 | ✅ 未泄漏 |
| Claude Code CLI 源码 | ⚠️ 已公开 |

**对用户的影响**：
- **API 用户 / SaaS 构建者**：无直接风险，API 密钥和数据未暴露
- **Claude Code 用户**：工具功能不受影响，可继续正常使用
- **企业客户**：核心基础设施和模型能力保持安全

**对 Anthropic 的影响**：
- 知识产权暴露：内部架构、工具实现、未发布功能细节公开
- 竞争情报流失：竞争对手可研究其 CLI 设计
- 信任影响：五天内的第二起重大配置失误（3 月 26 日 CMS 配置错误曾暴露 Claude Mythos 模型细节）

### 用户建议

- **无需特殊行动**：继续正常使用 Claude Code
- **npm 发布者**：运行 `npm pack --dry-run` 验证发布内容；确保 `.map` 文件被排除
- **谨慎下载**：泄漏仓库可能携带恶意软件；仅通过可信分析师的技术文章了解架构
- **关注官方更新**：Anthropic 可能发布安全建议或工具更新

### 技术亮点（值得学习）

尽管是意外泄漏，代码库展示了高质量的工程实践：

- **工具系统**：~40 个权限隔离的工具，base definition 达 29K 行
- **查询引擎**：46K 行，处理所有 LLM API 调用、流式传输、缓存
- **多代理编排**：支持 "swarms" 并行任务
- **IDE Bridge**：JWT 认证通道连接 VS Code/JetBrains 扩展
- **技术栈**：Bun（运行时）+ React+Ink（终端 UI）+ Zod v4（验证）+ ~50 个 slash 命令
- **懒加载**：OpenTelemetry、gRPC 等重型依赖按需加载

> **参考来源**：Byteiota (2026-03-31), Dev.to (2026-03-31), LowCode Agency (2026-03-31), Cybernews, VentureBeat, SocRadar, Analytics India Magazine, Binance Square, Penligent.ai

## 相关资源

- [Claude Code Overview - Claude Code Docs](https://code.claude.com/docs/en/overview)
- [Quickstart Guide](https://code.claude.com/docs/en/quickstart)
- [Terminal Guide](https://code.claude.com/docs/en/terminal-guide)
- [VS Code Extension](https://code.claude.com/docs/en/vs-code)
- [Claude Code on the Web](https://code.claude.com/docs/en/claude-code-on-the-web)
- [How Claude Code Works](https://code.claude.com/docs/en/how-claude-code-works)
- [Skills Documentation](https://code.claude.com/docs/en/skills)
- [The Claude Code Handbook](https://www.freecodecamp.org/news/claude-code-handbook/) (freeCodeCamp)
- [What It Is and How It's Different](https://www.producttalk.org/claude-code-what-it-is-and-how-its-different/) (Product Talk)
- [Medium: Claude Code is Great](https://leo-godin.medium.com/claude-code-is-great-6db35d8685f0)
- [YouTube: Introducing Claude Code](https://www.youtube.com/watch?v=AJpK3YTTKZ4)
- [YouTube: Full Tutorial for Beginners](https://www.youtube.com/watch?v=ntDIxaeo3Wg)
