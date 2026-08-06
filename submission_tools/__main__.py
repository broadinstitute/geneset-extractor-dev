from __future__ import annotations

import argparse
from pathlib import Path

from .discovery import discover_submissions
from .coordinated import coordinated_validate
from .receipt import write_receipt
from .scaffold import scaffold
from .validator import validate_submission


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m submission_tools")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Statically validate a new-format submission.")
    validate.add_argument("--submission", required=True, help="submission.yaml or its library directory")
    validate.add_argument("--quiet", action="store_true")
    validate.add_argument("--dig-repo")
    validate.add_argument("--dig-python", default=None)
    validate.add_argument("--smoke", action="store_true")
    validate.add_argument("--development-dig-checkout", action="store_true")
    validate.add_argument("--receipt-out")
    discover = commands.add_parser("discover", help="List new-format submissions, optionally limited to changed paths.")
    discover.add_argument("--repo-root", default=".")
    discover.add_argument("--changed-files", help="Newline-delimited changed-path file; omit to list all submissions.")
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
    if args.command == "discover":
        changed_paths = None
        if args.changed_files:
            changed_paths = Path(args.changed_files).read_text(encoding="utf-8").splitlines()
        for root in discover_submissions(Path(args.repo_root), changed_paths):
            print(root)
        return 0
    if args.dig_repo:
        result = coordinated_validate(Path(args.submission), Path(args.dig_repo), dig_python=args.dig_python or __import__("sys").executable, smoke=args.smoke, development_dig_checkout=args.development_dig_checkout)
    else:
        result = validate_submission(Path(args.submission))
    if args.receipt_out:
        submission_path = Path(args.submission) / "submission.yaml" if Path(args.submission).is_dir() else Path(args.submission)
        write_receipt(submission_path, Path(args.dig_repo or "."), {"ok": result.ok, "issues": [issue.__dict__ for issue in result.issues]}, Path(args.receipt_out), list(__import__("sys").argv))
    if not args.quiet:
        for issue in result.issues:
            print(f"{issue.level}: {issue.code}: {issue.message}")
        print("valid" if result.ok else "invalid")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
