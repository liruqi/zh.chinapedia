RivonClaw 是一个构建在 OpenClaw 之上的开源桌面端应用和 UI 层，旨在将长期运行的 AI Agent（人工智能代理）转变为个人的“数字管家”。 [^1] [^2] 

## 核心功能与特点

* 易于操作：它将复杂的 OpenClaw 封装成易于安装和使用的桌面程序。 用户可以通过系统托盘启动，并通过本地 Web 面板（默认端口 3210）进行管理。
* 自然语言配置：用户可以使用通俗易懂的语言编写规则。无需编程背景，系统会随着时间的推移学习用户的偏好。
* 多渠道集成：支持快速配置不同的 LLM（大语言模型）提供商（如 Gemini）和消息渠道（如 WhatsApp、Slack）。
* 安全防护：通过插件在 AI 调用工具执行前拦截并验证文件路径，保护本地文件系统的安全。
* 技能市场：内置技能市场（Skills Market），允许用户安装和管理不同的 AI 技能。 [^1] [^3] 

## 技术栈与开源信息

* 开发者：由 GitHub 用户 [gaoyangz77](https://github.com/gaoyangz77/rivonclaw) 开发。
* 技术架构：采用 Monorepo 结构，桌面端使用 Electron 40，管理面板使用 React 19 + Vite 6，数据存储于 SQLite。
* 环境要求：需要 Node.js (≥ 24) 和 pnpm (10.6.2) 进行构建。 [^1] [^3] 


[^1]: [https://github.com](https://github.com/gaoyangz77/rivonclaw#:~:text=RivonClaw%20wraps%20OpenClaw%20into%20a%20desktop%20app,the%20agent%20learn%20your%20preferences%20over%20time.)
[^2]: [https://winstall.app](https://winstall.app/apps?q=publisher:%20RivonClaw)
[^3]: [https://github.com](https://github.com/gaoyangz77/easyclaw/blob/main/README.zh-CN.md)
