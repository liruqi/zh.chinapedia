---
slug: en-openclaw-enable-controlui-lan-access
title: Enabling OpenClaw Control UI for LAN Access
authors: [liruqi]
tags: [openclaw, self-hosting, guide]
---


Accessing the OpenClaw Control UI from other devices on your local network requires a few manual configuration changes to the gateway settings. 

By default, OpenClaw might be restricted to local access for security. To enable LAN access (e.g., accessing from your phone or another laptop at `http://192.168.1.x:18789`), you need to update your configuration file.

### Configuration Changes

You need to modify the `gateway` section of your OpenClaw configuration. Specifically, ensure that `bind` is set to `lan` and that the `controlUi` section includes the correct `allowedOrigins`.

The final configuration should look like this:

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

### Key Settings Explained

*   **`bind: "lan"`**: Sets the gateway to listen on all local network interfaces instead of just the loopback interface.
*   **`allowedOrigins`**: You must explicitly list the IP address or hostname of your server here. Browsers enforce CORS, and the Control UI won't be able to talk to the gateway if its origin isn't allowed.
*   **`allowInsecureAuth`**: Set this to `true` if you are not using HTTPS on your local network (common for internal home labs).
*   **`dangerouslyDisableDeviceAuth`**: This skips device-specific authentication checks, making it easier to connect from multiple devices on the LAN. Use with caution in public networks.

Once you have applied these changes, restart your OpenClaw service `openclaw gateway restart` for the new settings to take effect.
