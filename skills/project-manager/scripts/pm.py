#!/usr/bin/env python3
"""Mode B Lite PM — thin entrypoint.

Refuses to run under Python < 3.13 before importing pm_lib: surface
matching (git_ops.is_authorized_path) relies on PurePosixPath.full_match,
added in 3.13, and a partial import under an older interpreter would fail
with a confusing traceback instead of a clear message.
"""

from __future__ import annotations

import sys


def main() -> int:
    if sys.version_info < (3, 13):
        sys.stderr.write(
            "pm: requires Python 3.13 or newer (PurePosixPath.full_match is required "
            f"for authorized-surface matching); found {sys.version.split()[0]}\n"
        )
        return 2

    from pm_lib import cli

    return cli.main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
