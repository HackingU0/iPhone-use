#!/usr/bin/env python3
"""Claude Desktop MCP stdio entrypoint: the upstream server, adapted to how Claude Desktop hosts it.

Claude Desktop starts each server in claude_desktop_config.json when the app starts and
keeps it until the app quits, and it hosts MCP Apps views that call the server's tools
themselves and may reach only the origins the view declares. Doubao Work treats a server
the same way, so this is its entrypoint with Claude's wording: one server for every chat,
frames kept between two polls for the view to play back, no loopback listener, and a
worker for the phone service that outlives the server. The installer puts the PATH this
needs into the config entry's env.
"""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "doubao")]
import claude_text
import mcp_stdio as doubao


class Trace(doubao.Trace):
    """Doubao Work's request log, kept in <state>/claude while <state>/claude/trace exists."""
    HOST = "claude"


def adapt(server, strict=True):
    """Adjust an imported upstream iphone_use module for Claude Desktop."""
    doubao.adapt(server, strict, claude_text)


if __name__ == "__main__":
    sys.exit(doubao.main(claude_text, Trace))
