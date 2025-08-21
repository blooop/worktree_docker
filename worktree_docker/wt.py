"""wt - Lightweight git worktree helper (no Docker)

This provides a subset of wtd focused purely on creating and managing
bare repos + git worktrees locally. It intentionally skips any Docker
image build or container launch logic.

Usage:
  wt owner/repo[@branch][#subfolder] [--open]
  wt --list
  wt --prune <owner/repo[@branch]>
  wt --help

Features:
  - Clones bare repositories (cached under ~/.wtd/workspaces)
  - Creates git worktrees per branch
  - Lists existing worktrees
  - Prunes (removes) a specific worktree + directory

Differences from wtd:
  - No Docker / Buildx / Compose
  - No extensions system
  - Just ensures a clean worktree exists and optionally opens a shell
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

# Reuse RepoSpec + helper directory functions from main module
from .worktree_docker import (  # type: ignore
    RepoSpec,
    get_workspaces_dir,
    get_repo_dir,
    get_worktree_dir,
    setup_bare_repo,
)


@dataclass
class WTConfig:
    repo_spec: RepoSpec
    shell: str = "bash"
    open_shell: bool = True


def list_worktrees() -> List[str]:
    workspaces = get_workspaces_dir()
    output: List[str] = []
    if not workspaces.exists():
        return output
    for owner_dir in workspaces.iterdir():
        if not owner_dir.is_dir():
            continue
        for repo_dir in owner_dir.iterdir():
            if not repo_dir.is_dir():
                continue
            for wt in repo_dir.glob("worktree-*"):
                if wt.is_dir():
                    branch = wt.name.replace("worktree-", "")
                    # heuristic: convert '-' back to '/' if folder with slash form exists in refs
                    branch_display = branch
                    output.append(f"{owner_dir.name}/{repo_dir.name}@{branch_display}")
    return sorted(set(output))


def create_worktree(spec: RepoSpec) -> Path:
    try:
        setup_bare_repo(spec)  # ensures bare repo
    except Exception as e:  # pragma: no cover - network/perm issues
        raise SystemExit(f"Failed to clone repository {spec.owner}/{spec.repo}: {e}")
    worktree_dir = get_worktree_dir(spec)
    repo_dir = get_repo_dir(spec)
    if worktree_dir.exists():
        logging.info("Worktree already exists: %s", worktree_dir)
        return worktree_dir
    logging.info("Creating worktree %s for %s", spec.branch, spec)
    try:
        subprocess.run(
            [
                "git",
                "-C",
                str(repo_dir),
                "worktree",
                "add",
                str(worktree_dir),
                spec.branch,
            ],
            check=True,
        )
    except subprocess.CalledProcessError:
        # branch may not exist yet -> create
        subprocess.run(
            [
                "git",
                "-C",
                str(repo_dir),
                "worktree",
                "add",
                "-b",
                spec.branch,
                str(worktree_dir),
            ],
            check=True,
        )
    return worktree_dir


def prune_worktree(spec: RepoSpec) -> int:
    worktree_dir = get_worktree_dir(spec)
    if not worktree_dir.exists():
        print(f"Worktree not found: {spec}")
        return 1
    print(f"Removing worktree: {worktree_dir}")
    subprocess.run(["rm", "-rf", str(worktree_dir)], check=False)
    # best-effort remove git registration
    repo_dir = get_repo_dir(spec)
    safe_branch = spec.branch.replace("/", "-")
    subprocess.run(
        [
            "git",
            "-C",
            str(repo_dir),
            "worktree",
            "remove",
            f"worktree-{safe_branch}",
        ],
        check=False,
        capture_output=True,
    )
    return 0


def parse_repo_spec(value: str) -> RepoSpec:
    return RepoSpec.parse(value)


def main(argv: Optional[List[str]] = None) -> int:  # noqa: D401
    parser = argparse.ArgumentParser(
        prog="wt",
        description="Lightweight git worktree helper (no Docker)",
    )
    parser.add_argument("repo_spec", nargs="?", help="owner/repo[@branch][#subfolder]")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run inside worktree")
    parser.add_argument("--list", action="store_true", help="List existing worktrees")
    parser.add_argument("--prune", metavar="SPEC", help="Remove the specified worktree")
    parser.add_argument(
        "--shell",
        default=os.environ.get("SHELL", "bash"),
        help="Shell to start when no command is provided (default: bash)",
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warn", "error"],
        default="info",
        help="Logging verbosity",
    )

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()), format="%(levelname)s: %(message)s"
    )

    if args.list:
        for line in list_worktrees():
            print(line)
        return 0

    if args.prune:
        spec = parse_repo_spec(args.prune)
        return prune_worktree(spec)

    if not args.repo_spec:
        parser.print_help()
        return 1

    spec = parse_repo_spec(args.repo_spec)
    worktree_dir = create_worktree(spec)

    # Apply subfolder if present
    exec_dir = worktree_dir
    if spec.subfolder:
        exec_dir = worktree_dir / spec.subfolder
        exec_dir.mkdir(parents=True, exist_ok=True)

    if args.command:
        # Run provided command directly
        cmd = args.command
        # Drop leading '--' if present
        if cmd and cmd[0] == "--":
            cmd = cmd[1:]
        return subprocess.run(cmd, cwd=exec_dir, check=False).returncode

    # Open interactive shell
    return subprocess.run([args.shell], cwd=exec_dir, check=False).returncode


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
