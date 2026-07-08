#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def toml_string(value: object) -> str:
    return json.dumps(str(value))


FAKETTY_WORKER = r"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def parse_spec(spec: str) -> tuple[str, str]:
    output = ""
    text = ""
    for line in spec.splitlines():
        if line.startswith("TTY_FILE: "):
            output = line.removeprefix("TTY_FILE: ").strip()
        elif line.startswith("TTY_TEXT: "):
            text = line.removeprefix("TTY_TEXT: ")
    if not output:
        raise ValueError("missing TTY_FILE")
    return output, text


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("faketty-worker: missing prompt", file=sys.stderr, flush=True)
        return 2
    if not os.isatty(0):
        print("faketty-worker: stdin is not a tty", file=sys.stderr, flush=True)
        return 7
    output, text = parse_spec(argv[-1])
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text + "\n", encoding="utf-8")
    print(f"faketty-worker: wrote {output}", flush=True)
    while True:
        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
"""


SENTINEL_WORKER = r"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def main(argv: list[str]) -> int:
    if not os.isatty(0):
        print("sentinel-worker: stdin is not a tty", file=sys.stderr, flush=True)
        return 7
    done_sentinel = os.environ.get("RINGER_DONE_SENTINEL")
    if not done_sentinel:
        print("sentinel-worker: missing RINGER_DONE_SENTINEL", file=sys.stderr, flush=True)
        return 8
    target = Path(done_sentinel)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("done\n", encoding="utf-8")
    print(f"sentinel-worker: wrote {done_sentinel}", flush=True)
    while True:
        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
"""


class PtyEngineEndToEndTests(unittest.TestCase):
    def write_faketty_worker(self, root: Path) -> Path:
        worker_path = root / "faketty_worker.py"
        worker_path.write_text(textwrap.dedent(FAKETTY_WORKER).lstrip(), encoding="utf-8")
        return worker_path

    def write_sentinel_worker(self, root: Path) -> Path:
        worker_path = root / "sentinel_worker.py"
        worker_path.write_text(textwrap.dedent(SENTINEL_WORKER).lstrip(), encoding="utf-8")
        return worker_path

    def write_config(self, root: Path, worker_path: Path) -> Path:
        config_path = root / "config.toml"
        config_path.write_text(
            "\n".join(
                [
                    f"state_dir = {toml_string(root / 'state')}",
                    "",
                    "[eval]",
                    'backend = "jsonl"',
                    f"jsonl_path = {toml_string(root / 'runs.jsonl')}",
                    "",
                    "[artifact]",
                    "enabled = false",
                    "",
                    "[engines.faketty]",
                    f"bin = {toml_string(sys.executable)}",
                    "pty = true",
                    "args_template = [",
                    f"  {toml_string(worker_path)},",
                    '  "{spec}",',
                    "]",
                    "sandbox_args = []",
                    "full_access_args = []",
                    "",
                    "[engines.faketty-no-pty]",
                    f"bin = {toml_string(sys.executable)}",
                    "pty = false",
                    "args_template = [",
                    f"  {toml_string(worker_path)},",
                    '  "{spec}",',
                    "]",
                    "sandbox_args = []",
                    "full_access_args = []",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return config_path

    def write_sentinel_config(self, root: Path, worker_path: Path) -> Path:
        config_path = root / "sentinel-config.toml"
        config_path.write_text(
            "\n".join(
                [
                    f"state_dir = {toml_string(root / 'state')}",
                    "",
                    "[eval]",
                    'backend = "jsonl"',
                    f"jsonl_path = {toml_string(root / 'runs.jsonl')}",
                    "",
                    "[artifact]",
                    "enabled = false",
                    "",
                    "[engines.sentinel-pty]",
                    f"bin = {toml_string(sys.executable)}",
                    "pty = true",
                    "args_template = [",
                    f"  {toml_string(worker_path)},",
                    '  "{spec}",',
                    "]",
                    "sandbox_args = []",
                    "full_access_args = []",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return config_path

    def run_ringer(self, manifest_path: Path, config_path: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "ringer.py",
                "run",
                str(manifest_path),
                "--config",
                str(config_path),
                "--no-dashboard",
                "--identity",
                "pty-test",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )

    def write_manifest(self, path: Path, workdir: Path, engine: str, key: str) -> None:
        path.write_text(
            json.dumps(
                {
                    "run_name": f"{key}-run",
                    "workdir": str(workdir),
                    "max_parallel": 1,
                    "worktrees": False,
                    "tasks": [
                        {
                            "key": key,
                            "engine": engine,
                            "spec": "TTY_FILE: tty.txt\nTTY_TEXT: hello from faketty",
                            "check": (
                                "grep -q 'hello from faketty' tty.txt || "
                                "{ echo FAIL: tty.txt missing expected content; exit 1; }"
                            ),
                            "expect_files": ["tty.txt"],
                            "timeout_s": 3,
                        }
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def write_sentinel_manifest(self, path: Path, workdir: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "run_name": "sentinel-run",
                    "workdir": str(workdir),
                    "max_parallel": 1,
                    "worktrees": False,
                    "tasks": [
                        {
                            "key": "sentinel-task",
                            "engine": "sentinel-pty",
                            "spec": "write the done sentinel and then keep running",
                            "check": "true",
                            "timeout_s": 5,
                        }
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def test_pty_engine_completes_on_expect_files_and_non_pty_variant_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            home = root / "home"
            ringer_home = root / "ringer-home"
            home.mkdir()
            ringer_home.mkdir()
            worker_path = self.write_faketty_worker(root)
            config_path = self.write_config(root, worker_path)

            env = os.environ.copy()
            env["HOME"] = str(home)
            env["RINGER_HOME"] = str(ringer_home)
            env["XDG_CONFIG_HOME"] = str(root / "xdg-config")

            pty_manifest = root / "pty-manifest.json"
            pty_workdir = root / "work-pty"
            self.write_manifest(pty_manifest, pty_workdir, "faketty", "pty-task")

            pty_proc = self.run_ringer(pty_manifest, config_path, env)
            pty_output = pty_proc.stdout + pty_proc.stderr
            self.assertEqual(0, pty_proc.returncode, pty_output)
            self.assertRegex(
                pty_output,
                re.compile(r"^pty-task\s+pass\s+PASS\s+1\s+", re.MULTILINE),
                pty_output,
            )
            self.assertEqual(
                "hello from faketty\n",
                (pty_workdir / "pty-task" / "tty.txt").read_text(encoding="utf-8"),
            )
            pty_log = (pty_workdir / "pty-task" / "worker.log").read_bytes()
            self.assertIn(b"(pty)", pty_log)
            self.assertNotIn(b"< /dev/null", pty_log)
            self.assertIn(b"faketty-worker: wrote tty.txt", pty_log)

            nonpty_manifest = root / "nonpty-manifest.json"
            nonpty_workdir = root / "work-nonpty"
            self.write_manifest(nonpty_manifest, nonpty_workdir, "faketty-no-pty", "nonpty-task")

            nonpty_proc = self.run_ringer(nonpty_manifest, config_path, env)
            nonpty_output = nonpty_proc.stdout + nonpty_proc.stderr
            self.assertEqual(1, nonpty_proc.returncode, nonpty_output)
            self.assertRegex(
                nonpty_output,
                re.compile(r"^nonpty-task\s+fail\s+FAIL\s+2\s+", re.MULTILINE),
                nonpty_output,
            )
            nonpty_log = (nonpty_workdir / "nonpty-task" / "worker.log").read_text(
                encoding="utf-8"
            )
            self.assertIn("< /dev/null", nonpty_log)
            self.assertIn("faketty-worker: stdin is not a tty", nonpty_log)

    def test_pty_engine_completes_on_done_sentinel_without_deliverables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            home = root / "home"
            ringer_home = root / "ringer-home"
            home.mkdir()
            ringer_home.mkdir()
            worker_path = self.write_sentinel_worker(root)
            config_path = self.write_sentinel_config(root, worker_path)

            env = os.environ.copy()
            env["HOME"] = str(home)
            env["RINGER_HOME"] = str(ringer_home)
            env["XDG_CONFIG_HOME"] = str(root / "xdg-config")

            manifest_path = root / "sentinel-manifest.json"
            workdir = root / "work-sentinel"
            self.write_sentinel_manifest(manifest_path, workdir)

            proc = self.run_ringer(manifest_path, config_path, env)
            output = proc.stdout + proc.stderr
            self.assertEqual(0, proc.returncode, output)
            self.assertRegex(
                output,
                re.compile(r"^sentinel-task\s+pass\s+PASS\s+1\s+", re.MULTILINE),
                output,
            )
            taskdir = workdir / "sentinel-task"
            sentinel_log = (taskdir / "worker.log").read_text(encoding="utf-8")
            self.assertIn("(pty)", sentinel_log)
            self.assertIn("sentinel-worker: wrote", sentinel_log)
            self.assertNotIn("worker timed out", sentinel_log)
            self.assertTrue((taskdir / ".ringer_done").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
