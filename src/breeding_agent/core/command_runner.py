"""Small wrapper around subprocess for external bioinformatics commands."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence


def format_command(command: Sequence[str]) -> str:
    """Return a readable command string for logs."""

    return " ".join(str(part) for part in command)


def run_command(
    command: Sequence[str],
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    log_file: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run an external command without shell expansion.

    The workflow intentionally passes every command as ``list[str]`` and never
    uses ``shell=True``. stdout/stderr are streamed by the subprocess itself so
    long-running tools keep their native progress output visible.
    """

    if not command:
        raise ValueError("command must not be empty")

    print(f"[cmd] {format_command(command)}", flush=True)
    completed = subprocess.run(
        list(command),
        cwd=str(cwd) if cwd is not None else None,
        env=dict(env) if env is not None else None,
        capture_output=True,
        check=False,
        text=True,
    )

    if completed.stdout:
        print(completed.stdout, end="", flush=True)
    if completed.stderr:
        print(completed.stderr, end="", flush=True)

    if log_file is not None:
        _append_command_log(log_file, command, completed)

    completed.check_returncode()
    return completed


def _append_command_log(
    log_file: str | Path,
    command: Sequence[str],
    completed: subprocess.CompletedProcess[str],
) -> None:
    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n[{timestamp}] command: {format_command(command)}\n")
        handle.write(f"[{timestamp}] returncode: {completed.returncode}\n")
        handle.write("[stdout]\n")
        handle.write(completed.stdout or "")
        if completed.stdout and not completed.stdout.endswith("\n"):
            handle.write("\n")
        handle.write("[stderr]\n")
        handle.write(completed.stderr or "")
        if completed.stderr and not completed.stderr.endswith("\n"):
            handle.write("\n")
