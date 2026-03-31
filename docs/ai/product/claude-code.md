---
title: Claude Code
description: Google AI Overview 搜索结果的 Claude Code 介绍
date: 2025-03-31
source: Google AI Overview
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
