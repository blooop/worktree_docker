"""Thin wrapper around wtd that forces --no-docker.

This keeps all core logic / UX (flags, autocomplete, interactive
selection, etc.) centralized in `worktree_docker.py` while providing a
`wt` executable for users who only want local git worktree management.
"""

from __future__ import annotations

import sys

from . import worktree_docker as _wtd


def main(argv=None) -> int:  # noqa: D401
    # Prepend --no-docker so behavior is consistent.
    # Preserve user-provided args order after the injected flag.
    args = ["--no-docker"]
    if argv is None:
        args.extend(sys.argv[1:])
    else:
        args.extend(argv)
    return _wtd.main(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
