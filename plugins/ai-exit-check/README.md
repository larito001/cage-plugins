# AI 出口与地区检测

从 Cage 当前运行环境探测 Google、Anthropic 和 OpenAI 的服务响应，展示出口 IP、地区线索、边缘节点、连通性和一致性比较。包含一个工作台页面和两个 MCP 工具。

源码来自 Claude-Cage 的 `internal/hostbridge/defaults/ai-exit-check` 预装插件，按 MIT 许可发布，许可原文见 LICENSE。本市场维护者为 larito001。

## 运行方式

- 环境内插件，使用 Python 3.10 或更新版本及标准库，无需 API 密钥或第三方 Python 包。
- `check_ai_exit_regions` 执行检测，可指定预期国家代码与出口标识。
- `list_exit_routes` 列出默认出口以及 `/run/account-routes/<账号标识>/browser.sock` 中当前可访问的独立账号出口；没有这些套接字时仍可检测默认出口。
- 仅检测网络，不更改代理、账号配置或网络规则。

## 网络与结果边界

执行检测会请求 ipinfo.io、api.ip.sb、ipwho.is、www.youtube.com、antigravity.google、daily-cloudcode-pa.googleapis.com、gemini.google.com、claude.ai、api.anthropic.com、chatgpt.com、auth.openai.com 和 api.openai.com 的公开端点。这些服务会看到请求出口 IP；插件不需要登录凭据。

结果依据地理数据库、公开页面、追踪端点和未认证 API 的返回信息推断。部分端点可能不返回 IP 或地区，边缘节点位置也不等于账号地区。检测不能证明账号可用、模型调用成功或所有应用请求都使用相同出口。
