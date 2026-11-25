# Cage 插件市场

这里收录 [Cage](https://github.com/Lee-xeo/Claude-Cage) 的插件。插件让环境里的 Claude 在你的电脑上多一项能力，例如运行命令、读取屏幕或操作某个应用。每个插件是一个标准的 MCP 服务，通过标准输入输出通信。

本 fork 当前保留 Blender、电脑操作、桌面控制、Linux 桌面和语音合成五种插件。下方清单与索引格式中的示例仅用于说明格式。

## 安装插件

在 Cage 侧栏打开「插件」→「插件市场」，按分类浏览并安装。Cage 从本仓库读取 `index.json`，下载对应的压缩包，核对 SHA-256 后放进插件目录。

运行在你电脑上的插件以你的系统账户权限运行，不受环境的隔离保护。调用前会弹出确认窗口，显示插件、工具和参数，你可以只允许这一次，也可以选择对该插件始终允许。安装前请阅读插件声明的权限，只安装你信任的插件。

## 提交插件

1. 在 `plugins/` 下新建一个以插件名命名的目录，放入清单 `plugin.json`、多语言说明 `i18n.json` 和程序文件。
2. 在仓库根目录的 `authors.json` 中登记你的插件名与 GitHub 用户名（如 `"my-plugin": "your-github-username"`）。
3. 运行 `python3 scripts/build.py`。它检查清单、作者与多语言说明，把插件打包到 `dist/`，并更新 `index.json`。
4. 把 `plugins/`、`authors.json`、`dist/`、`index.json` 的改动一起提交，按 [PR 模板](.github/PULL_REQUEST_TEMPLATE.md) 发起 Pull Request，并在 PR 描述中附带插件在 Cage 中的运行效果图。

修改已发布的插件时，必须同时提高 `plugin.json` 里的版本号。已发布版本的压缩包不会被改写；旧版本的压缩包可以从 `dist/` 删除。

### PR 规范与运行效果图

发起 Pull Request 时，请完整填写仓库自带的 [PR 模板](.github/PULL_REQUEST_TEMPLATE.md)，写明变更类型、插件运行位置（`host` / `guest`）及选择理由、权限与数据流向、实测平台和尚未验证的范围。

新增插件或涉及界面、交互与可见输出变更的 PR，**必须在 PR 描述中附带插件在 Cage 中的真实运行效果图**（截图、GIF 或短录屏）：

- **基本展示**：插件在 Cage「插件」页面加载成功的状态。
- **MCP 工具**：在 Cage 中实际调用工具并展示返回结果或联动效果（主机插件建议同时展示系统授权确认弹窗或本机实际效果）。
- **扩展页面（`contributes.views`）**：侧栏页面在 Cage 工作台中的真实界面展示（如有浅色/深色主题适配，建议一并附上）。
- **上传方式**：请直接将截图、GIF 或录屏拖入 GitHub PR 描述框上传，**不要将效果图文件提交进 `plugins/`、`targets/` 或 `dist/` 目录**，避免被打包进插件压缩包、增大用户下载体积。
- **隐私脱敏**：上传前请遮盖账号、API Key、令牌、代理订阅、本机敏感路径和内网地址等敏感信息。
- **豁免说明**：纯文档、构建脚本或 CI 维护等不涉及插件界面与可见行为的 PR 可不附效果图，在对应章节简要说明即可。

### 清单 `plugin.json`

插件有两种用途，可以兼有：给 Claude 提供工具（MCP 服务），或者给 Cage 加一个自己的页面。可以运行在你的电脑上（`"kind": "host"`），也可以运行在环境内（`"kind": "guest"`）。

```json
{
  "name": "system-status",
  "displayName": "System Status",
  "version": "0.1.0",
  "description": "Shows processor load, memory and disk use.",
  "icon": "icon.svg",
  "engines": { "cage": ">=0.1.8" },
  "kind": "guest",
  "permissions": [],
  "categories": ["system"],
  "contributes": {
    "mcpServers": [{ "id": "status", "command": ["python3", "server.py"] }],
    "views": [{ "id": "status", "title": "System Status", "entry": "view/index.html", "server": "status" }]
  }
}
```

清单各字段、页面的限制和页面与 Cage 之间的消息协议，见 Cage 仓库的[插件文档](https://github.com/Lee-xeo/Claude-Cage/blob/main/docs/plugins.md)。只有一个 MCP 服务的主机插件也可以用旧格式，只写 `command` 即可。

`permissions` 必须如实写明，没有就写空列表。可选值：`files`（读写文件）、`commands`（运行命令）、`screen`（查看屏幕）、`input`（控制键盘和鼠标）、`network`（访问网络）。

`categories` 是插件在市场里的分类，上架时必须写 1 到 3 个：`desktop`（桌面控制）、`developer`（开发）、`system`（系统与状态）、`network`（网络）、`files`（文件）、`productivity`（效率）、`example`（示例）。

带有按系统编译的程序的插件，放在 `targets/<目标>/<插件名>/` 下，每个目标一份，目标为 `darwin-arm64`、`darwin-x64`、`linux-arm64`、`linux-x64`、`win32-arm64` 或 `win32-x64`。不分系统的插件放在 `plugins/` 下。

### 作者归属 `authors.json`

仓库根目录的 [`authors.json`](authors.json) 记录每个插件的作者 GitHub 用户名。`scripts/build.py` 会按维护者名单自动生成 `index.json` 的 `author` 字段：官方维护的插件展示为「Cage 官方」，社区贡献的插件直接展示贡献者的 GitHub 用户名。不要把作者字段写进 `plugin.json`（较早的 Cage 读取清单时不接受未知字段）。

### 多国语言说明 `i18n.json`

Cage 客户端会根据当前界面语言自动显示插件名称与说明（若未匹配到对应语言，则回退到 `plugin.json` 中的默认英文 `displayName` 和 `description`）。

每个插件目录（含 `targets/<目标>/<插件名>/` 下的每个目标目录）都必须提供 `i18n.json`，完整包含 Cage 支持的全部 **15 种界面语言**；`scripts/build.py --check` 会校验语言是否齐全，并检查保留词与长度（`displayName` 不超过 80 字符，`description` 不超过 600 字符）：

```json
{
  "zh-CN": {
    "displayName": "系统状态",
    "description": "在独立页面和 Claude 工具中展示当前环境的处理器负载、内存与磁盘使用情况。"
  },
  "zh-TW": {
    "displayName": "系統狀態",
    "description": "在獨立頁面與 Claude 工具中顯示目前環境的處理器負載、記憶體與磁碟使用情況。"
  }
}
```

必须包含的 15 个语言代码（与 Cage 的 `languages.json` 一致）：

| 语言代码 | 语言 | 语言代码 | 语言 | 语言代码 | 语言 |
| --- | --- | --- | --- | --- | --- |
| `zh-CN` | 简体中文 | `ko` | 한국어 | `prs` | دری |
| `zh-TW` | 繁體中文 | `es` | Español | `am` | አማርኛ |
| `ru` | Русский | `my` | မြန်မာဘာသာ | `so` | Soomaali |
| `ar` | العربية | `be` | Беларуская | `ti` | ትግርኛ |
| `fa` | فارسی | `ps` | پښتو | `fr` | Français |

`plugin.json` 中的 `displayName` 和 `description` 请保持简洁的英文，不要把中英文混写在同一段里；多语言内容统一放在 `i18n.json` 中（同样不要写进 `plugin.json`，以兼容较早版本的 Cage）。

### 收录要求

- 权限如实声明。插件做了清单没有声明的事，会被移除。
- 按 [PR 模板](.github/PULL_REQUEST_TEMPLATE.md) 提交并附带运行效果图：新增插件或改动界面/交互的 PR 需在 PR 描述中附带插件在 Cage 中的真实运行效果图（截图、GIF 或短录屏），脱敏后直接拖入 PR 描述框上传，不把效果图提交进插件目录或压缩包。
- 必须填写作者与多语言说明：在 `authors.json` 登记有效的 GitHub 用户名，并在插件目录提供覆盖全部 15 种 Cage 界面语言的 `i18n.json`。
- 工具的名称、说明、参数说明以及 `i18n.json` 的文案只描述工具做什么，不提及模型运行在哪里，也不出现本产品的名字或 VM、guest 之类的词。打包脚本会检查清单、`i18n.json` 和 `tools.json`；工具的文字由应用在加载时检查，不合格的插件无法加载。
- 以 MIT 许可提交。本仓库采用 [MIT 许可](LICENSE)，提交插件即表示同意以该许可发布；插件带有第三方代码时，在插件目录里附上其许可。
- 源码可读。不收录只有二进制文件或混淆代码的插件。
- 插件目录里只有普通文件和文件夹，不含链接；打包后不超过 20 MB，解包后不超过 100 MB 且不超过 2000 个文件。
- 运行时不自行下载并执行未经锁定的代码。优先使用 `scripts/launcher.py` + `launch.json`：Python 服务通过 `scripts/vendor.py` 生成 `pylock.json`（记录每个预编译 wheel 的 `files.pythonhosted.org` 地址、大小与 SHA-256，在环境内首次启动时校验解包），轻量纯 JS 服务通过 `package-lock.json` 随包携带 `node_modules`（`npm ci --omit=dev --ignore-scripts`）。若直接通过 `npx` 或 `uv`/`uvx` 在启动时获取上游程序，必须写死精确版本：`npx --yes 包名@1.2.3`，或 `uvx`/`uv run --no-project` 配 `--from`/`--with 包名==1.2.3` 和 `--exclude-newer <日期>`。打包脚本会拒绝未写死版本、未匹配 `scripts/launcher.py` 或缺少哈希锁定的写法。

### 基于开源项目的插件

优先收录成熟的开源 MCP 服务，许可证必须允许再分发（MIT、Apache-2.0、BSD 等）；GPL、AGPL 等类许可暂不收录。这类插件：

- 在插件目录放上游的 `LICENSE` 原文，并在 `README.md` 写明上游项目、版本、许可证、链接、数据流向（联网目的地）和运行时依赖。
- 在插件目录放 `source.json`，打包脚本把它写进索引条目的 `source`，并按启动方式自动写入可选的 `runtime` 字段；Cage 在插件页的「信息」与「上游项目」里显示：

  ```json
  { "project": "microsoft/playwright-mcp", "version": "0.0.86", "license": "Apache-2.0", "url": "https://github.com/microsoft/playwright-mcp" }
  ```

  这些信息不要写进 `plugin.json`：较早的 Cage 读取清单时不接受未知字段。
- 上游默认开启使用统计时，用启动参数或一个小的启动文件关闭它，见 [`plugins/blender`](plugins/blender)。
- 需要访问用户电脑上的程序或设备（屏幕键鼠、Blender、本机浏览器预览）的用 `"kind": "host"`；能在环境内独立完成的（文档办公、浏览器、Git、网页抓取、SQLite、知识记忆等）优先用 `"kind": "guest"`，三个系统上的行为完全一致，且无需在电脑上安装 `uv` 等额外运行环境。

示例都不需要安装依赖，只用到 Python 标准库、Windows 自带的 PowerShell 或 Linux 桌面自带的 X11 库：

- [`plugins/desktop-control`](plugins/desktop-control)：主机插件，查看屏幕并使用键鼠。macOS 版在 `plugins/` 下，Windows 版按目标放在 `targets/win32-x64/` 和 `targets/win32-arm64/` 下，Linux 版（X11）放在 `targets/linux-x64/` 和 `targets/linux-arm64/` 下。三个版本读取同一份工具表 `tools.json`，工具名称和参数完全相同。
- [`plugins/linux-desktop`](plugins/linux-desktop)：环境内插件，用 `desktop-control` 的 Linux 版操作环境自己的桌面，工具名称前加 `desktop_`。

基于开源 MCP 服务的插件：

| 插件 | 上游与版本 | 许可证 | 运行位置 | 依赖与启动方式 |
| --- | --- | --- | --- | --- |
| [`blender`](plugins/blender) | [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp) 1.3.1 | MIT | 这台电脑 | 本机 `uv`、Blender 3.0+ 及随附的插件 |

## 索引格式

`index.json` 由脚本生成，不要手工修改。

```json
{
  "version": 1,
  "plugins": [
    {
      "name": "clock",
      "version": "0.1.4",
      "description": "Tells the current time on this computer.",
      "author": { "name": "Lee-xeo", "official": true },
      "i18n": { "zh-CN": { "displayName": "时钟", "description": "获取这台电脑上的当前时间。" } },
      "permissions": [],
      "icon": "https://raw.githubusercontent.com/larito001/cage-plugins/main/plugins/clock/icon.svg",
      "archive": "https://raw.githubusercontent.com/larito001/cage-plugins/main/dist/clock-0.1.4.tar.gz",
      "sha256": "…",
      "bytes": 887,
      "source": { "project": "上游项目，可选", "version": "…", "license": "MIT", "url": "https://…" }
    }
  ]
}
```
