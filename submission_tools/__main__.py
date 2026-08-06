from __future__ import annotations

import argparse
from pathlib import Path

from .scaffold import scaffold
from .validator import validate_submission


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m submission_tools")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Statically validate a new-format submission.")
    validate.add_argument("--submission", required=True, help="submission.yaml or its library directory")
    validate.add_argument("--quiet", action="store_true")
    create = commands.add_parser("scaffold", help="Create a new, small submission wrapper skeleton.")
    create.add_argument("--library-id", required=True)
    create.add_argument("--display-name", required=True)
    create.add_argument("--pattern", required=True, choices=["gtex", "motrpac", "hubmap", "lincs_l1000", "generic"])
    create.add_argument("--output", required=True, help="New library directory; it must not already exist.")
    args = parser.parse_args(argv)
    if args.command == "scaffold":
        scaffold(Path(args.output), args.library_id, args.display_name, args.pattern)
        print(f"created {Path(args.output)}")
        return 0
    result = validate_submission(Path(args.submission))
    if not args.quiet:
        for issue in result.issues:
            print(f"{issue.level}: {issue.code}: {issue.message}")
        print("valid" if result.ok else "invalid")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
