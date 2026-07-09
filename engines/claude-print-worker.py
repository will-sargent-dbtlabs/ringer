#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import sys


SCRUB_EXACT = {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDECODE"}
SCRUB_PREFIXES = ("CLAUDE_CODE_",)


def child_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in list(env):
        if key in SCRUB_EXACT or any(key.startswith(prefix) for prefix in SCRUB_PREFIXES):
            del env[key]
    env.setdefault("TERM", "xterm-256color")
    return env


def resolve_claude_bin(env: dict[str, str]) -> str:
    requested = os.environ.get("CLAUDE_PTY_BIN", "claude")
    if os.sep in requested:
        return requested
    resolved = shutil.which(requested, path=env.get("PATH"))
    if resolved is None:
        raise RuntimeError(f"Claude CLI not found: {requested}")
    return resolved


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("claude-print-worker: expected exactly one prompt argument", file=sys.stderr)
        return 2

    prompt = argv[1]
    env = child_env()
    try:
        claude_bin = resolve_claude_bin(env)
    except RuntimeError as exc:
        print(f"claude-print-worker: {exc}", file=sys.stderr)
        return 1

    args = [
        claude_bin,
        "-p",
        prompt,
        "--permission-mode",
        "bypassPermissions",
        "--model",
        "sonnet",
        "--output-format",
        "text",
    ]
    try:
        os.execvpe(claude_bin, args, env)
    except OSError as exc:
        print(f"claude-print-worker: exec failed: {exc}", file=sys.stderr)
        return 127


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
