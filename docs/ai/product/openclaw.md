---
title: OpenClaw
tags: [oss]
---

OpenClaw（俗称“小龙虾”）是一款在 2026 年初迅速走红的开源、自托管自主 AI 智能体（AI Agent）项目。它由奥地利工程师 [Peter Steinberger](../../person/@steipete.md) 开发，旨在让用户在自己的设备上运行一个能“真正做事”的 AI 助手。 [^1] [^2] [^3] 

## 核心功能与特点

* 自主执行任务：与普通的聊天机器人不同，OpenClaw 可以操作浏览器、读写本地文件、运行 shell 命令、管理日程、甚至处理电子邮件。
* 多渠道接入：用户可以通过常用的聊天软件（如 WhatsApp、Telegram、Discord、微信/飞书等）向 AI 发送指令，就像给真人助理发信息一样。
* 开源与自托管：基于 MIT 协议开源，支持在 Windows、macOS、Linux、甚至 [QNAP NAS](https://www.qnap.com/th-th/how-to/tutorial/article/how-to-install-and-run-openclaw-formerly-clawdbot-and-moltbot-on-qnap-ubuntu-linux-station) 等硬件上运行，用户掌握自己的数据和 API 密钥。
* 插件系统（Skills）：拥有一个名为 "Skills" 的插件系统，允许开发者扩展 AI 的能力（如接入特定的软件或服务）。 [^1] [^3] [^4] [^5] [^6] [^7] [^8] 

## 发展历程

   1. 更名史：最初命名为 Clawdbot，后因 Anthropic 公司（Claude 开发者）提出商标异议，简短更名为 Moltbot，最终于 2026 年 1 月定名为 OpenClaw。
   2. 病毒式传播：2026 年初在 GitHub 上爆火，星标（Star）数迅速突破 30 万，成为当年增长最快的开源项目之一。
   3. 开发者动向：2026 年 2 月，创始人 [Peter Steinberger](../../person/@steipete.md) 宣布加入 OpenAI，项目随后移交给独立基金会进行社区化运作。 [^1] [^4] [^6] [^9] [^10] [^11] 

## 中国市场的"龙虾热"
OpenClaw 在中国引发了极高的关注，甚至出现了“养龙虾”热潮：

* 大厂入局：腾讯、百度、阿里等云厂商纷纷推出一键部署服务或相关产品。
* 政策支持：深圳市龙岗区曾发布“龙虾十条”政策，支持相关 AI 智能体产业的发展。
* 周边生态：市场上出现了贴有龙虾标志的“OpenClaw 专用主机”，以及大量的付费安装和培训课程。 [^4] [^12] 

## 安全警告与争议
由于 OpenClaw 需要获取较高的系统权限来执行任务，其安全性也备受争议：

* 安全风险：存在因配置不当导致 API 密钥泄露或黑客远程控制系统的风险。工信部曾发布预警，建议审慎使用。
* 使用限制：中国官方已限制国有企业和政府机构在办公环境下使用该软件。
* 防护方案：NVIDIA 推出了 NemoClaw，旨在通过隔离环境和安全护栏来降低 OpenClaw 的运行风险。 [^1] [^4] [^12] [^13] [^14] 

[^1]: [https://en.wikipedia.org](https://en.wikipedia.org/wiki/OpenClaw)
[^2]: [https://cloud.tencent.com](https://cloud.tencent.com/developer/article/2626160#:~:text=OpenClaw%28%E6%9B%BE%E7%94%A8%E5%90%8D%20Clawdbot%29%E6%98%AF%E4%B8%80%E6%AC%BE%202026%20%E5%B9%B4%E7%88%86%E7%81%AB%E7%9A%84%E5%BC%80%E6%BA%90%E4%B8%AA%E4%BA%BA%20AI%20%E5%8A%A9%E6%89%8B%2CGitHub%20%E6%98%9F%E6%A0%87%E5%B7%B2%E8%B6%85%E8%BF%87%2010%20%E4%B8%87%E9%A2%97.)
[^3]: [https://www.kdnuggets.com](https://www.kdnuggets.com/openclaw-explained-the-free-ai-agent-tool-going-viral-already-in-2026)
[^4]: [https://zh.wikipedia.org](https://zh.wikipedia.org/zh-cn/OpenClaw)
[^5]: https://docs.openclaw.ai
[^6]: [https://openclaw.ai](https://openclaw.ai/blog/introducing-openclaw)
[^7]: [https://www.qnap.com](https://www.qnap.com/th-th/how-to/tutorial/article/how-to-install-and-run-openclaw-formerly-clawdbot-and-moltbot-on-qnap-ubuntu-linux-station)
[^8]: [https://1password.com](https://1password.com/blog/from-magic-to-malware-how-openclaws-agent-skills-become-an-attack-surface#:~:text=Even%20OpenAI%27s%20documentation%20describes%20the%20same%20basic,SKILL.md%20file%20plus%20optional%20scripts%20and%20assets.)
[^9]: [https://medium.com](https://medium.com/@hugolu87/openclaw-vs-claude-code-in-5-mins-1cf02124bc08#:~:text=OpenClaw%2C%20a%20popular%20open%2Dsource%20AI%20agent%2C%20was,earlier%20due%20to%20trademark%20complaints%20from%20Anthropic.)
[^10]: [https://github.com](https://github.com/openclaw)
[^11]: [https://github.com](https://github.com/openclaw/openclaw)
[^12]: [https://www.bbc.com](https://www.bbc.com/zhongwen/articles/c93wvdn91kxo/trad)
[^13]: [https://www.nvidia.com](https://www.nvidia.com/en-eu/ai/nemoclaw/)
[^14]: [https://www.cnbc.com](https://www.cnbc.com/2026/03/17/nvidia-ceo-jensen-huang-says-openclaw-is-definitely-the-next-chatgpt.html)
