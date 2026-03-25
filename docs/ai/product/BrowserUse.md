---
title: "Browser Use"
---

Browser Use 是一个领先的开源 Python 库，旨在让 AI 智能体（AI Agents）能够像人类一样自主地操作网页浏览器。它由 Magnus Müller 和 Gregor Zunic 创建，目前在 GitHub 上已获得超过 8 万颗星。 [^1] [^2] [^3] 

## 核心功能与工作原理

* 自主交互：AI 智能体可以接收自然语言指令，例如“在 Hacker News 上查找排名前三的帖子”，然后自动打开浏览器、导航页面、点击按钮、填写表单并提取数据。
* 视觉与 DOM 结合：它通过 [Chrome DevTools Protocol (CDP)](https://github.com/browser-use/browser-use/blob/main/AGENTS.md) 控制浏览器，将页面的 HTML 结构信息与视觉截图结合，帮助 AI 理解复杂的交互逻辑。
* 多模型支持：兼容 OpenAI (GPT-4o)、Anthropic (Claude)、Google (Gemini) 以及通过 Ollama 运行的本地模型。官方推荐使用其专门优化的 ChatBrowserUse 模型，速度比普通模型快 3-5 倍。
* 隐身与反爬：支持隐身浏览器模式、验证码识别及 195 多个国家的代理，以规避网站的自动化检测。 [^1] [^3] [^4] [^5] [^6] [^7] [^8] [^9] 

## 主要组件

   1. [Browser Use 开源库](https://github.com/browser-use/browser-use)：免费使用的 Python 核心库，适合开发者在本地构建自动化脚本。
   2. [Browser Use Cloud](https://cloud.browser-use.com/)：托管服务平台，提供可扩展的云端浏览器基础设施，无需本地配置环境。
   3. [Browser Use CLI](https://docs.browser-use.com/open-source/browser-use-cli)：命令行工具，支持快速执行单次任务或启动持久化的浏览器会话。
   4. [Workflow Use](https://github.com/browser-use/workflow-use)：用于创建确定性的、具备自愈能力的 RPA 2.0 工作流。 [^1] [^4] [^10] [^11] [^12] [^13] [^14] [^15] 

## 快速上手示例 (Python)

安装后，可以通过几行代码启动一个简单的 AI 任务： [^5] [^16] 

```python
from browser_use import Agent, Browser, ChatBrowserUse
import asyncio

async def main():
    agent = Agent(
        task="在 Google 上搜索 'Python 教程' 并告诉我第一个搜索结果的标题",
        llm=ChatBrowserUse()
    )
    await agent.run()

asyncio.run(main())
```

(注：运行前需配置 BROWSER_USE_API_KEY 环境变量) [^4] [^7] 

[^1]: [https://github.com](https://github.com/browser-use/browser-use)
[^2]: [https://www.infoworld.com](https://www.infoworld.com/article/3812644/browser-use-an-open-source-ai-agent-to-automate-web-based-tasks.html#:~:text=Browser%20Use%20is%20an%20open%2Dsource%20project%20created,to%20make%20websites%20accessible%20to%20AI%20agents.)
[^3]: [https://github.com](https://github.com/browser-use/browser-use/blob/main/README.md)
[^4]: [https://github.com](https://github.com/browser-use/browser-use/blob/main/AGENTS.md)
[^5]: [https://vercel.com](https://vercel.com/marketplace/browseruse)
[^6]: [https://www.thoughtworks.com](https://www.thoughtworks.com/en-in/radar/languages-and-frameworks/browser-use)
[^7]: [https://docs.browser-use.com](https://docs.browser-use.com/open-source/quickstart)
[^8]: https://browser-use.com
[^9]: [https://docs.browser-use.com](https://docs.browser-use.com/cloud/quickstart)
[^10]: [https://docs.browser-use.com](https://docs.browser-use.com/cloud/introduction)
[^11]: [https://cloud.browser-use.com](https://cloud.browser-use.com/#:~:text=AI%20Browser%20automation.%20The%20infrastructure%20behind%20the%20state%20of%20the%20art%20agent.)
[^12]: [https://docs.browser-use.com](https://docs.browser-use.com/open-source/browser-use-cli)
[^13]: [https://github.com](https://github.com/browser-use/browser-use/releases)
[^14]: [https://github.com](https://github.com/browser-use/workflow-use)
[^15]: [https://gologin.com](https://gologin.com/blog/browser-use-technical-expert-review-tests/)
[^16]: [https://browser-use.com](https://browser-use.com/pricing)
