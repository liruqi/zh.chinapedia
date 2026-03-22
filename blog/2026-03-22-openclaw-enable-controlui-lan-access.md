---
slug: openclaw-enable-controlui-lan-access
title: 开启 OpenClaw 控制界面的局域网访问
authors: [liruqi]
tags: [openclaw, 自托管, 指南]
---


如果您在家庭服务器或专用机器上运行 OpenClaw，您可能希望从局域网（LAN）中的其他设备（例如手机或其他笔记本电脑）访问其控制界面。这需要对 `gateway` 部分进行一些配置调整。

默认情况下，出于安全考虑，OpenClaw 可能被限制为仅供本地访问。要开启局域网访问（例如通过 `http://192.168.1.x:18789` 访问），您需要更新配置文件。

### 配置更改

您需要修改 OpenClaw 配置中的 `gateway` 部分。具体请确保将 `bind` 设置为 `lan`，并确保 `controlUi` 部分包含正确的 `allowedOrigins`。

最终配置应如下所示：

```json
{
  "gateway": {
    "port": 18789,
    "mode": "local",
    "bind": "lan",
    "controlUi": {
      "allowedOrigins": [
        "http://localhost:18789",
        "http://127.0.0.1:18789",
        "http://192.168.1.165:18789"
      ],
      "allowInsecureAuth": true,
      "dangerouslyDisableDeviceAuth": true
    }
  }
}
```

### 关键设置说明

*   **`bind: "lan"`**：设置网关在所有本地网络接口上监听，而不仅限于回环接口 (127.0.0.1)。
*   **`allowedOrigins`**：您必须在此处显式列出服务器的 IP 地址或主机名。浏览器强制执行 CORS 策略，如果其来源未被允许，控制界面将无法与网关通信。
*   **`allowInsecureAuth`**：如果您在局域网中不使用 HTTPS（家庭实验室常用），请将其设置为 `true`。
*   **`dangerouslyDisableDeviceAuth`**：这会跳过特定设备的身份验证检查，使从局域网上的多个设备连接更加容易。在公共网络中请谨慎使用。

完成这些更改后，请重启您的 OpenClaw 服务：执行 `openclaw gateway restart` 以使新设置生效。
