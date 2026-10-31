# iPhone Use for Claude 桌面端

把 [iPhone Use](../README.md) 接入 macOS 上的 Claude 桌面端（Claude Desktop）：同一套 MCP 服务、同一套技能，让 Claude 通过 USB 操作真实 iPhone，并在对话里显示手机实时画面。

这个目录叠加在原版（Codex 版）、[WorkBuddy 版](../workbuddy/README.md) 和 [豆包工作版](../doubao/README.md) 之上，复用后两者的适配代码。依赖与 [安装依赖](../README.md#安装依赖) 相同：macOS、完整 Xcode、USB 连接的 iPhone、Python 3.9+、Node.js 20.19+ / 22.12+ / 24+。本地 MCP 服务只在 Mac 上的 Claude 桌面端可用，claude.ai 网页版和手机 App 里没有这些工具。

## 安装

先打开过一次 Claude 桌面端，然后在源码目录运行：

```sh
python3 claude/install.py
```

安装器把服务放到 `~/.local/share/iphone-use-claude`，确认它能启动，再把 `iphone_use` 合并进 `~/Library/Application Support/Claude/claude_desktop_config.json`。然后在 Claude 里完成两步，安装器无法代劳：

1. **上传技能。** 「自定义（Customize）> 技能（Skills）」→「上传技能」，分别选安装器打印的 `~/.local/share/iphone-use-claude/skill-uploads/iphone-use.zip` 和 `iphone-use-setup.zip`，上传后把两个技能都打开。技能需要「代码执行与文件创建」处于开启状态；Team / Enterprise 账号可能还要管理员先允许技能。`.local` 是隐藏目录，在文件选择框里按 ⌘⇧G 粘贴路径最快。
2. **重启 Claude。** 完全退出（⌘Q，不是关窗口）再打开。「设置 > 开发者」里应能看到 `iphone_use` 在运行；新对话输入框的工具菜单里应列出它的工具。

在新对话里输入：

> 用 iphone-use-setup 帮我配置通过 USB 连接的 iPhone，验证 READY，然后显示手机屏幕。

已经用 Codex 版、WorkBuddy 版或豆包工作版配置过的手机不需要重新签名和构建：几个宿主共用 `~/.local/share/iphone-use` 里的设备配置、WDA 构建和操作锁。

Claude 第一次调用每个工具时会请求许可；手机任务会连续调用很多次，选「始终允许」比较省事。点按、输入这类会改变手机状态的工具，是否每次确认由你决定。

## 安装器做了什么

| 位置 | 内容 |
| --- | --- |
| `~/.local/share/iphone-use-claude/` | 原版安装包（服务、USB 工具、屏幕 widget），WorkBuddy 版和豆包工作版的适配代码，Claude 入口 `claude/claude_server.py` |
| `…/skill-uploads/*.zip` | 两个技能的上传包：ZIP 顶层是技能文件夹本身，文件夹名与 `SKILL.md` 的 `name` 一致 |
| `claude_desktop_config.json` | 在 `mcpServers` 里合并一项 `iphone_use`，其他服务和设置原样保留，改动前留一份 `claude_desktop_config.json.bak-*` |

写入前会用配置里同样的命令和环境启动一次服务，确认 `initialize` 与 `tools/list` 正常，失败则不改动任何文件。配置文件不是合法 JSON、已有不是本安装器写入的 `iphone_use`、或安装目录不是本安装器创建的，都会停下，除非加 `--force`。

注册项与 WorkBuddy 版相同：解释器用绝对路径；`env.PATH` 写入 node、npm、git、Xcode 命令所在目录（GUI 应用启动子进程时 PATH 只有系统目录）；`NO_PROXY` 包含本地回环；匿名使用统计默认关闭，想保留原版默认行为用 `--analytics` 安装。

## 与 Codex 版的差异

| | Codex | Claude 桌面端 |
| --- | --- | --- |
| 安装 | `sh scripts/install.sh`，经 Codex CLI 注册插件 | `python3 claude/install.py`，再上传两个技能、重启 Claude |
| 认证接管时的提问 | `request_user_input_async` | 有提问工具时用它，没有时在回复里直接问并结束本回合 |
| 截图 | 经 `functions.exec` 转发图片块 | 图片块随工具结果直接返回 |
| 工具缺失时的代码入口 | 运行 `scripts/phone.py` 或导入 Runtime | 没有：Claude 的代码执行在云端沙箱，访问不到这台 Mac |
| 手机屏幕 | 侧边栏，READY 打开并复用 | 对话里的 MCP App 视图，`pua_screen()` 打开 |
| 视图底部的刷新 / 主屏幕 / 截图按钮 | 有 | 有 |

服务说明和技能中点名 Codex 专用工具、或让模型在 Mac 上运行命令的几段，由 [claude_text.py](claude_text.py) 逐段替换，替换的是 WorkBuddy 版已经列出的同一批段落，另加一句关于代码入口的说明；控制工具的名称、参数和行为与原版完全一致。原版改写了其中某一段，或几个版本的段落对不上时，安装器和测试会报出具体是哪一段。

## Claude 桌面端怎么托管这个服务

Claude 桌面端托管本地服务和 MCP App 的方式与豆包工作一致，所以入口 [claude_server.py](claude_server.py) 直接用豆包工作版的适配，只换了文字：

- **一个常驻进程。** Claude 启动时按配置启动服务，一直用到退出，所有对话共用。
- **只有 `pua_screen` 打开画面。** Claude 在调用带界面的工具时把视图显示在对话里。原版让 READY 也带画面，那样每次 READY 都会多一个视图；入口去掉了这一处，并在说明里告诉模型：本对话第一次 READY 后调用一次 `pua_screen()`。
- **视图自己的工具调用由 Claude 转发**，取帧和底部三个按钮按原版的方式工作。取帧和按钮调用的工具声明为只对视图可见（`_meta.ui.visibility = ["app"]`），模型看不到它们。
- **画面每秒 4 次取帧，按采集节奏回放。** 入口把手机端画面流设为每秒 30 帧、半尺寸，每次应答带回上次之后的所有帧，页面按采集时的间隔依次画出来，画面比手机慢约 0.3 秒。视图的安全策略不放行任何额外来源，不开本机端口。
- **手机端服务不随应用退出。** 保持 WDA 运行的 worker 归属 launchd，Claude 退出后仍在，下次不用重新启动。需要停止时用 `pua_setup(action="stop")`。

使用期间手机要保持解锁亮屏；长时间使用时把自动锁定设为「永不」。

## 排查

- **新对话里没有工具。** 看「设置 > 开发者」里 `iphone_use` 的状态和日志；日志也在 `~/Library/Logs/Claude/mcp-server-iphone_use.log`。修改配置后一定要完全退出 Claude 再打开。
- **`pua_doctor` 说找不到 node / npm。** 换过 Node 安装位置时重新运行 `python3 claude/install.py`，再重启 Claude。
- **想看 Claude 向服务发了什么**（只记方法名、工具名和资源地址，不记参数、结果和画面）：

  ```sh
  mkdir -p ~/.local/share/iphone-use/claude && touch ~/.local/share/iphone-use/claude/trace
  ```

  重启 Claude，重现问题，然后看 `~/.local/share/iphone-use/claude/host.log`。删除 `trace` 文件并重启即停止记录。

## 更新与卸载

```sh
git pull --ff-only
python3 claude/install.py
```

更新后完全退出 Claude 再打开；技能内容有变化时，在「自定义 > 技能」里删除旧技能并重新上传新的 ZIP。卸载会移除配置里的 `iphone_use` 和安装目录，保留 `~/.local/share/iphone-use` 中的手机配置与构建；两个技能在 Claude 的「自定义 > 技能」里删除：

```sh
python3 claude/install.py --uninstall
```

## 测试

```sh
python3 -m unittest discover -s claude/tests -v
```

测试在临时目录里完整安装一遍并启动服务，配置文件写在临时目录，手机的 USB 画面流用一个替身脚本，不接触真实的 Claude 配置和手机。
