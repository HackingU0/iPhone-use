"""Text and widget page for Claude Desktop, told from what the WorkBuddy port already rewrites.

The upstream passages that name Codex-only tools are the ones workbuddy/host_text.py lists.
Each list here gives, for the same passages in the same order, what holds in Claude Desktop,
plus the few passages that assume the model can run commands on this Mac: Claude's own code
execution runs in a cloud sandbox, which reaches neither the phone nor the shared state.

The widget page is Doubao Work's: Claude Desktop is an MCP Apps host that forwards a view's
tool calls and admits no loopback origin, the same two facts the Doubao Work page is built on.
"""
import hashlib
from pathlib import Path
import sys

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "workbuddy"), str(Path(__file__).resolve().parents[1] / "doubao")]
import host_text as base
import doubao_text

Drift = base.Drift
retell = doubao_text.retell

# Upstream's way out when a tool binding is missing is a command on this Mac. Claude has none.
NO_FALLBACK = ("For an unavailable MCP binding use the skill's direct Runtime fallback with the same operation lock.",
               "Claude's own code execution runs in a cloud sandbox, not on this Mac, so there is no direct Runtime fallback here: "
               "for an unavailable pua_ tool ask the user to check the iphone_use server in Claude's Settings > Developer and start a new chat.")

INSTRUCTIONS = retell(base.INSTRUCTIONS, [
    "A screenshot arrives as an image in the same result. If no image is visible in the result, take one fresh pua_observe(mode=screenshot): image.path is a file on this Mac that Claude's code execution sandbox cannot open, and image metadata or base64 text is not a viewed screenshot. ",
    "Claude shows the live iPhone screen as an app view in the chat, opened by pua_screen(): READY does not open it. After the first READY in a chat call pua_screen() once so the user can watch; an open view follows the phone by itself, so do not call pua_screen again to refresh it. ",
    "ask the user (with Claude's question tool when this chat offers one; otherwise ask in your reply and end the turn), first option exactly 已完成继续. Wait for the actual user answer; a skipped, timed-out or preselected question is not confirmation.",
], "INSTRUCTIONS") + [NO_FALLBACK]

TOOL_DESCRIPTIONS = {
    "pua_screen": retell(base.TOOL_DESCRIPTIONS["pua_screen"], [
        "Open the live iPhone screen as an app view in the Claude chat.",
        "READY does not open it: call this once after the first READY in a chat.",
    ], "pua_screen"),
}

ASK = "向用户提问（本对话有 Claude 的提问工具时用它；没有时在回复里直接问并结束本回合，等用户下一条消息）"
SANDBOX = "Claude 对话自带的代码执行运行在云端沙箱里，不在这台 Mac 上，访问不到 USB、`~/.local/share/iphone-use` 和 `image.path`"
SKILLS = {
    "skills/iphone-use/SKILL.md": retell(base.SKILLS["skills/iphone-use/SKILL.md"], [
        "Claude 把手机屏幕显示为对话里的 App 视图，由 `pua_screen()` 打开，READY 不会打开它。本对话第一次 READY 成功后调用一次 `pua_screen()` 让用户观看；视图打开后自己跟随手机，暂停 / 恢复预览沿用同一个视图。已有视图时直接继续，不为刷新再调用 `pua_screen()`，也不要为打开画面重复 READY。",
        f"必须{ASK}，首个选项固定「已完成继续」，第二个可为「暂时无法完成」。提问被跳过、超时或预选不是用户答复；",
        f"Claude 中直接调用 `pua_*` 工具，截图作为图片块随同一结果返回；点击、输入等失败结果同样附带图片块。如果结果里没有看到图片，重新取一次 `pua_observe(mode=\"screenshot\")`，不要尝试读取 `image.path`：{SANDBOX}。不能把图片元数据或 base64 当成看过截图。",
    ], "skills/iphone-use/SKILL.md") + [
        # Claude can do much without the phone. The description is what tells a phone task apart.
        doubao_text.SKILLS["skills/iphone-use/SKILL.md"][-1],
    ],
    "skills/iphone-use/references/authentication.md": retell(base.SKILLS["skills/iphone-use/references/authentication.md"], [
        """在 Claude 中，本对话有提问工具时按它当前的实际 schema 填写；没有时在回复里直接问并结束本回合。例如当前明确显示 Face ID 时：

- 问题：当前 App 需要 Face ID 验证。请在 iPhone 上完成认证并停留在目标页面；完成后选择「已完成继续」，我会接着读取剩余明细。
- 选项：「已完成继续」、「暂时无法完成」""",
        "以用户实际提交的选项或明确回复为准；提问被跳过、超时、没有答复，或工具在用户作答前就返回，都不能当作完成。",
    ], "skills/iphone-use/references/authentication.md"),
    "skills/iphone-use/references/tool-fallback.md": retell(base.SKILLS["skills/iphone-use/references/tool-fallback.md"], [
        "普通版提供 18 个模型工具，Claude 中由本地 MCP 服务 `iphone_use` 提供，名为 `pua_*`；先查看本回合实际可调用的工具，不能只从 tools/list、文档或先前聊天推断已经绑定。Claude 桌面端版由 `claude/install.py` 写入 `claude_desktop_config.json`；安装或更新后需要完全退出 Claude（⌘Q）再打开，并新开对话；",
        f"截图作为图片块随结果返回；结果里没有看到图片时重新取一次 `pua_observe(mode=\"screenshot\")`，不要读取 `image.path` / `error.observation.image.path`（{SANDBOX}），也不要把 base64 文本当成截图。",
        f"{SANDBOX}。所以在 Claude 对话里下面两种代码入口都不可用：缺少 `pua_*` 工具时，请用户在 Claude「设置 > 开发者」里确认 `iphone_use` 正在运行，然后新开对话，不要在沙箱里运行这些命令。用户自己在 Mac 终端里运行时，`<PLUGIN_ROOT>` 是安装目录，默认 `~/.local/share/iphone-use-claude`，以 `claude_desktop_config.json` 中 `iphone_use` 的实际路径为准。",
    ], "skills/iphone-use/references/tool-fallback.md"),
    "skills/iphone-use-setup/SKILL.md": retell(base.SKILLS["skills/iphone-use-setup/SKILL.md"], [
        "Claude 中 READY 不会打开手机屏幕；取得 READY 后调用一次 `pua_screen()` 在对话里打开，已有视图时不再调用，也不要重复 READY。",
        f"并必须{ASK}，",
    ], "skills/iphone-use-setup/SKILL.md"),
}

# Appended to the skill so the model knows what is specific to this host.
SKILL_NOTES = {
    "skills/iphone-use/SKILL.md": f"""
## 在 Claude 桌面端中使用

- 工具名为 `pua_*`，由 Claude 桌面端的本地 MCP 服务 `iphone_use` 提供，只在 Mac 上的 Claude 桌面端可用，网页版和手机 App 里没有。本回合没有这些工具时，请用户在「设置 > 开发者」确认 `iphone_use` 正在运行，必要时完全退出 Claude（⌘Q）再打开，然后新开对话。
- {SANDBOX}。所有手机操作和截图都通过 `pua_*` 工具完成，不要在沙箱里运行本技能提到的 `python3` / `sh` 命令。
- 手机屏幕是对话里的 App 视图，由 `pua_screen()` 打开。视图没有画面不影响控制通道，也不是任务失败；按工具返回的观察继续。
- 运行数据在 `~/.local/share/iphone-use`，与 Codex 版、WorkBuddy 版、豆包工作版共用同一份配置、构建和操作锁；返回 `device_busy` 时可能是另一个宿主正在操作手机。
""",
    "skills/iphone-use-setup/SKILL.md": f"""
## 在 Claude 桌面端中使用

- 工具名为 `pua_*`，由本地 MCP 服务 `iphone_use` 提供。本回合没有这些工具时，请用户在「设置 > 开发者」确认 `iphone_use` 正在运行并新开对话。
- 下载、签名配置、构建和启动都用 `pua_setup` / `pua_doctor` 完成。{SANDBOX}，不要在沙箱里执行安装或构建命令；需要用户在 Mac 上操作时（Xcode 登录、信任、开发者模式、在终端运行安装器），说明具体步骤并等待。
- 安装器已把 node、npm、git 和 Xcode 命令所在目录写进 `claude_desktop_config.json` 中 `iphone_use` 的 `env.PATH`。`pua_doctor` 报告缺少 node / npm 而本机实际已安装时，请用户在源码目录重新运行 `python3 claude/install.py` 刷新路径，再完全退出并重新打开 Claude，不要重装 Node。
- 运行数据在 `~/.local/share/iphone-use`；Codex 版、WorkBuddy 版或豆包工作版已经配置并构建过时直接复用，不重新 fetch / configure / build。
""",
}

SCREEN_SCRIPT = doubao_text.SCREEN_SCRIPT
SDK_FRAME_CALL = doubao_text.SDK_FRAME_CALL
screen_html = doubao_text.screen_html


def screen_uri(upstream):
    """A host may cache the page by URI; a changed page needs a new one."""
    revision = hashlib.sha1((SCREEN_SCRIPT + SDK_FRAME_CALL).encode()).hexdigest()[:8]
    return upstream.replace(".html", f"-claude-{revision}.html")


def skill_text(relative, text, strict=True):
    """A packaged skill file as Claude should read it; other files pass through."""
    text = base.rewrite(text, SKILLS.get(relative, ()), relative, strict)
    return text.rstrip("\n") + "\n" + SKILL_NOTES[relative] if relative in SKILL_NOTES else text


def adapt_server(module, strict=True):
    """Apply the host wording to an imported upstream iphone_use module."""
    module.INSTRUCTIONS = base.rewrite(module.INSTRUCTIONS, INSTRUCTIONS, "INSTRUCTIONS", strict)
    for tool in module.TOOLS:
        if tool["name"] in TOOL_DESCRIPTIONS:
            tool["description"] = base.rewrite(tool["description"], TOOL_DESCRIPTIONS[tool["name"]], tool["name"], strict)
