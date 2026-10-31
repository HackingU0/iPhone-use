#!/usr/bin/env python3
"""Install iPhone Use into Claude Desktop: a local MCP server plus two skills ready to upload.

Claude Desktop reads local servers from claude_desktop_config.json, so the server is
registered there; skills live in the account and are uploaded as ZIP files in Customize >
Skills, so this only builds the two archives. Phone state stays in ~/.local/share/iphone-use,
shared with the Codex, WorkBuddy and Doubao Work installs.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import claude_text


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# workbuddy/install.py: packaging, the PATH a GUI app's child needs, the start-up check and the
# config merge; doubao/install.py: which files each port's runtime needs.
shared = load("workbuddy_install", "workbuddy/install.py")
doubao = load("doubao_install", "doubao/install.py")
InstallError = shared.InstallError
NAME = "iphone-use-claude"
SERVER = "iphone_use"
SKILLS = ("iphone-use", "iphone-use-setup")
MARKER = ".claude-install.json"
ENTRY = "claude/claude_server.py"
RUNTIME_FILES = ("claude_server.py", "claude_text.py")
UPLOADS = "skill-uploads"
CONFIG = Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"


def stage(target):
    """Copy the upstream install package into target, with Claude wording, entrypoint and skill archives."""
    package = shared.packaging()
    version = package.validate()["version"]
    for source, relative in package.package_files():
        if relative.parts[0] in shared.CODEX_ONLY:
            continue
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if relative.parts[0] == "skills" and relative.suffix == ".md":
            destination.write_text(claude_text.skill_text(relative.as_posix(), source.read_text()))
        elif relative.as_posix() == shared.SCREEN_PAGE:
            destination.write_text(claude_text.screen_html(source.read_text()))
        else:
            shutil.copy2(source, destination)
    for directory, names in (("workbuddy", shared.RUNTIME_FILES), ("doubao", doubao.RUNTIME_FILES), ("claude", RUNTIME_FILES)):
        (target / directory).mkdir()
        for name in names:
            shutil.copy2(ROOT / directory / name, target / directory / name)
    (target / UPLOADS).mkdir()
    for name in SKILLS:
        archive(target / "skills" / name, target / UPLOADS / f"{name}.zip")
    (target / MARKER).write_text(json.dumps({"name": NAME, "version": version, "source": str(ROOT)}, indent=2) + "\n")
    return version


def archive(directory, path):
    """A skill as Claude's upload takes it: the skill folder itself at the top of the ZIP."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as bundle:
        for file in sorted(directory.rglob("*")):
            if file.is_file():
                bundle.write(file, (Path(directory.name) / file.relative_to(directory)).as_posix())


def server_entry(install_dir, python, analytics):
    """The config entry: absolute interpreter, and the PATH a GUI app does not pass on."""
    entry = shared.server_entry(install_dir, python, analytics)
    return {**entry, "args": [str(install_dir / ENTRY)]}


def install(install_dir, config_path, python, analytics=False, force=False):
    if not config_path.parent.is_dir():
        raise InstallError(f"{config_path.parent} does not exist. Start Claude Desktop once, or pass --config.")
    if install_dir.exists() and not (install_dir / MARKER).is_file() and not force:
        raise InstallError(f"{install_dir} exists and was not installed by this script. Move it or pass --force.")
    config = shared.read_config(config_path)
    servers = config.setdefault("mcpServers", {})
    if SERVER in servers and not shared.ours(servers[SERVER], install_dir) and not force:
        raise InstallError(f"{config_path} already has a different '{SERVER}' server. Remove it or pass --force.")
    entry = server_entry(install_dir, python, analytics)
    with tempfile.TemporaryDirectory(prefix="iphone-use-stage-") as staging:
        staged = Path(staging) / NAME
        staged.mkdir()
        version = stage(staged)
        # Prove the package starts under Claude Desktop's reduced environment before anything is replaced.
        served, tools = shared.handshake({**entry, "args": [str(staged / ENTRY)]})
        if served != version:
            raise InstallError(f"Staged server reports {served}, expected {version}.")
        shared.replace_directory(staged, install_dir)
    servers[SERVER] = entry
    changed = shared.write_config(config_path, config)
    return {"version": version, "tools": tools, "install_dir": str(install_dir), "config": str(config_path), "config_changed": changed,
            "entry": entry, "skills": [str(install_dir / UPLOADS / f"{name}.zip") for name in SKILLS]}


def uninstall(install_dir, config_path, force=False):
    """Remove the config entry and the installed server. The skills are removed in Claude itself."""
    removed = []
    if config_path.exists():
        config = shared.read_config(config_path)
        servers = config.get("mcpServers", {})
        if SERVER in servers and (shared.ours(servers[SERVER], install_dir) or force):
            del servers[SERVER]
            shared.write_config(config_path, config)
            removed.append(f"{config_path}: {SERVER}")
    if install_dir.exists():
        if not (install_dir / MARKER).is_file() and not force:
            raise InstallError(f"{install_dir} was not installed by this script. Remove it yourself or pass --force.")
        shutil.rmtree(install_dir)
        removed.append(str(install_dir))
    return removed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=Path.home() / ".local/share" / NAME, help="where the server is installed")
    parser.add_argument("--config", type=Path, default=CONFIG, help="Claude Desktop's claude_desktop_config.json")
    parser.add_argument("--python", default=sys.executable, help="interpreter Claude Desktop starts the server with (3.9+)")
    parser.add_argument("--analytics", action="store_true", help="keep upstream's anonymous usage statistics enabled")
    parser.add_argument("--force", action="store_true", help="replace an existing server entry or directory this script did not create")
    parser.add_argument("--uninstall", action="store_true", help="remove the server entry and the installed server")
    args = parser.parse_args()
    install_dir = args.dir.expanduser().resolve()
    config_path = args.config.expanduser().absolute()
    try:
        if args.uninstall:
            removed = uninstall(install_dir, config_path, args.force)
            print("\n".join(["Removed:"] + removed) if removed else "Nothing to remove.")
            print(f"In Claude, Customize > Skills: remove the skills {', '.join(SKILLS)}. Quit Claude (⌘Q) and open it again.")
            return 0
        if sys.platform != "darwin":
            raise InstallError("iPhone Use needs macOS with Xcode.")
        python = shutil.which(args.python) or args.python
        if not Path(python).is_absolute() or not os.access(python, os.X_OK):
            raise InstallError(f"--python must resolve to an executable: {args.python}")
        result = install(install_dir, config_path, python, args.analytics, args.force)
    except (InstallError, claude_text.Drift) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"iPhone Use {result['version']} installed for Claude Desktop ({result['tools']} tools).")
    print(f"  server  {result['install_dir']}")
    print(f"  config  {result['config']} -> mcpServers.{SERVER}" + ("" if result["config_changed"] else " (unchanged)"))
    if not all(shutil.which(name) for name in ("node", "npm")):
        print("warning: node or npm was not found on PATH; install Node.js 20.19+ and run this script again.")
    print("\nIn Claude, Customize > Skills > Upload skill, once for each, then switch both on:")
    for path in result["skills"]:
        print(f"  {path}")
    print("\nQuit Claude completely (⌘Q), open it again, and start a new chat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
