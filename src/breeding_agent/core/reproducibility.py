"""Write simple reproducibility provenance files."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable, Mapping


COMMANDS_FILENAME = "commands.sh"
CHECKSUMS_FILENAME = "checksums.sha256"


def write_reproducibility_bundle(
    *,
    outdir: Path,
    commands: Iterable[Mapping[str, str]],
    checksum_files: Iterable[Path],
) -> tuple[Path, Path]:
    """Write commands and SHA-256 checksums for a completed workflow run."""

    provenance_dir = outdir / "provenance"
    provenance_dir.mkdir(parents=True, exist_ok=True)

    commands_file = provenance_dir / COMMANDS_FILENAME
    checksums_file = provenance_dir / CHECKSUMS_FILENAME

    _write_commands(commands_file, commands)
    _write_checksums(checksums_file, checksum_files)

    return commands_file, checksums_file


def _write_commands(commands_file: Path, commands: Iterable[Mapping[str, str]]) -> None:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
    ]
    for command in commands:
        name = command.get("name", "command")
        command_text = command.get("command", "")
        if not command_text:
            continue
        lines.extend([f"# {name}", command_text, ""])

    commands_file.write_text("\n".join(lines), encoding="utf-8")
    commands_file.chmod(0o755)


def _write_checksums(
    checksums_file: Path,
    checksum_files: Iterable[Path],
) -> None:
    lines = []
    for path in checksum_files:
        if not path.exists():
            raise FileNotFoundError(f"Cannot checksum missing file: {path}")
        lines.append(f"{_sha256(path)}  {path}")

    checksums_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
