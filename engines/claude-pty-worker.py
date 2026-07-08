#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any


TRUST_KEYS = (
    "hasCompletedOnboarding",
    "hasTrustDialogAccepted",
    "hasCompletedProjectOnboarding",
    "hasCompletedClaudeInChromeOnboarding",
)
SCRUB_EXACT = {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDECODE"}
SCRUB_PREFIXES = ("CLAUDE_CODE_",)


def child_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in list(env):
        if key in SCRUB_EXACT or any(key.startswith(prefix) for prefix in SCRUB_PREFIXES):
            del env[key]
    env.setdefault("TERM", "xterm-256color")
    return env


def load_claude_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(loaded, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return loaded


def set_true(data: dict[str, Any], key: str) -> bool:
    if data.get(key) is True:
        return False
    data[key] = True
    return True


def seed_claude_trust(cwd: Path) -> None:
    config_path = Path.home() / ".claude.json"
    data = load_claude_config(config_path)
    changed = False

    for key in TRUST_KEYS:
        changed = set_true(data, key) or changed

    projects = data.get("projects")
    if projects is None:
        projects = {}
        data["projects"] = projects
        changed = True
    if not isinstance(projects, dict):
        raise RuntimeError(f"{config_path}: projects must be a JSON object")

    project_key = str(cwd.resolve())
    project = projects.get(project_key)
    if project is None:
        project = {}
        projects[project_key] = project
        changed = True
    if not isinstance(project, dict):
        raise RuntimeError(f"{config_path}: projects[{project_key!r}] must be a JSON object")
    changed = set_true(project, "hasTrustDialogAccepted") or changed
    changed = set_true(project, "hasCompletedProjectOnboarding") or changed

    if not changed:
        return

    tmp_path = config_path.with_name(config_path.name + ".ringer.tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp_path, config_path)
    except Exception:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise


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
        print("claude-pty-worker: expected exactly one prompt argument", file=sys.stderr)
        return 2

    prompt = argv[1]
    env = child_env()
    try:
        seed_claude_trust(Path.cwd())
        claude_bin = resolve_claude_bin(env)
    except RuntimeError as exc:
        print(f"claude-pty-worker: {exc}", file=sys.stderr)
        return 1

    args = [
        claude_bin,
        prompt,
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        "Write",
    ]
    try:
        os.execvpe(claude_bin, args, env)
    except OSError as exc:
        print(f"claude-pty-worker: exec failed: {exc}", file=sys.stderr)
        return 127


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
