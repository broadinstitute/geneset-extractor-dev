from __future__ import annotations

import argparse
from pathlib import Path

from .discovery import discover_submissions
from .adoption import adopt, adoption_status
from .adoption_workspace import DEFAULT_BASE_BRANCH, create_workspace, submit_workspace, verify_workspace
from .coordinated import coordinated_validate
from .legacy_compare import compare_gmt
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
    adopt_parser = commands.add_parser("adopt", help="Create an isolated workspace for adopting a legacy library.")
    adopt_parser.add_argument("--existing", required=True, help="Legacy directory; it is never modified.")
    adopt_parser.add_argument("--library-id", required=True)
    adopt_parser.add_argument("--display-name")
    adopt_parser.add_argument("--pattern", default="generic", choices=["gtex", "motrpac", "hubmap", "lincs_l1000", "generic"])
    adopt_parser.add_argument("--output", help="Legacy low-level mode: new adopted submission directory; defaults to --library-id.")
    adopt_parser.add_argument("--workspace", help="Required for isolated adoption: fresh-clone workspace directory.")
    adopt_parser.add_argument("--dig-repo")
    adopt_parser.add_argument("--github-user", help="GitHub username used to infer both contributor forks.")
    adopt_parser.add_argument("--dig-fork", help="Contributor DIG fork URL.")
    adopt_parser.add_argument("--wrapper-fork", help="Contributor wrapper fork URL.")
    adopt_parser.add_argument("--base-branch", default=DEFAULT_BASE_BRANCH, help="Upstream baseline and pull-request target branch (default: main).")
    adopt_parser.add_argument("--allow-upstream-origin", action="store_true", help="Advanced maintainer/test override; allow a canonical repository as origin for this isolated workspace.")
    comparison = commands.add_parser("compare-legacy", help="Compare legacy and regenerated GMT outputs.")
    comparison.add_argument("--library", help="Adopted library directory; discovers the first legacy/new GMT pair.")
    comparison.add_argument("--legacy")
    comparison.add_argument("--new")
    comparison.add_argument("--mode", default="set_equivalent", choices=["exact", "set_equivalent", "report_only"])
    status = commands.add_parser("adoption-status", help="Show adoption progress without bypassing normal validation.")
    status.add_argument("--library", required=True)
    verify = commands.add_parser("verify-adoption", help="Verify an isolated adoption workspace.")
    verify.add_argument("--workspace", required=True)
    submit = commands.add_parser("submit-adoption", help="Commit and push a verified isolated adoption workspace.")
    submit.add_argument("--workspace", required=True)
    submit.add_argument("--yes", action="store_true", help="Confirm the one local commit/push operation.")
    submit.add_argument("--allow-upstream-origin", action="store_true", help="Advanced maintainer override; never enabled implicitly.")
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
    if args.command == "adopt":
        if args.workspace:
            if args.output:
                parser.error("--workspace and --output are mutually exclusive")
            try:
                created = create_workspace(
                    existing=Path(args.existing), workspace=Path(args.workspace), library_id=args.library_id,
                    display_name=args.display_name, pattern=args.pattern, github_user=args.github_user,
                    dig_fork=args.dig_fork, wrapper_fork=args.wrapper_fork, base_branch=args.base_branch,
                    allow_upstream_origin=args.allow_upstream_origin,
                )
            except ValueError as exc:
                parser.error(str(exc))
            print("Adoption workspace ready:\n\n"
                  f"  {created}\n\n"
                  "Next:\n"
                  f"  cd {created}\n"
                  "  codex\n\n"
                  "Then tell your agent: Follow AI_ADOPTION_PROMPT.md.\n\n"
                  "No existing repositories or legacy files were modified.")
            return 0
        output = Path(args.output or args.library_id)
        created = adopt(Path(args.existing), output, args.library_id, args.display_name, args.pattern, Path(args.dig_repo) if args.dig_repo else None)
        print(f"created adopted submission {created}")
        return 0
    if args.command == "compare-legacy":
        legacy = Path(args.legacy) if args.legacy else None
        regenerated = Path(args.new) if args.new else None
        library = Path(args.library) if args.library else None
        if library and (legacy is None or regenerated is None):
            inventory_path = library / "adoption/inventory.json"
            if not inventory_path.exists():
                parser.error("--library requires adoption/inventory.json, or pass --legacy and --new")
            import json
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            outputs = inventory.get("gene_set_outputs", [])
            if not outputs:
                parser.error("no legacy GMT output was inventoried; pass --legacy and --new")
            legacy = Path(inventory["legacy_root"]) / str(outputs[0]["path"])
            candidates = [path for path in library.rglob("*.gmt") if "adoption" not in path.parts]
            if not candidates:
                parser.error("no regenerated GMT found; pass --new explicitly")
            regenerated = candidates[0]
        if legacy is None or regenerated is None:
            parser.error("pass --legacy and --new, or --library")
        report = library / "adoption/comparison_report.tsv" if library else None
        ok, rows = compare_gmt(legacy, regenerated, args.mode, report)
        if library:
            summary = library / "adoption/comparison_summary.md"
            counts = {status: sum(row["status"] == status for row in rows) for status in ("unchanged", "different", "missing", "new")}
            summary.write_text(
                "# Legacy comparison summary\n\n"
                + f"- Total legacy/new set names: {len(rows)}\n"
                + "\n".join(f"- {status}: {count}" for status, count in counts.items())
                + "\n",
                encoding="utf-8",
            )
        print(f"legacy comparison: {sum(row['status'] == 'unchanged' for row in rows)}/{len(rows)} unchanged")
        return 0 if ok else 1
    if args.command == "adoption-status":
        for name, ok, detail in adoption_status(Path(args.library)):
            print(f"{'✓' if ok else '✗'} {name}: {detail}")
        return 0
    if args.command == "verify-adoption":
        try:
            ok, messages = verify_workspace(Path(args.workspace))
        except (OSError, ValueError) as exc:
            print(f"ERROR: {exc}")
            return 2
        print("Adoption verification: " + ("PASS" if ok else "FAILED"))
        for message in messages:
            print(message)
        return 0 if ok else 1
    if args.command == "submit-adoption":
        try:
            ok, messages = submit_workspace(Path(args.workspace), yes=args.yes, allow_upstream_origin=args.allow_upstream_origin)
        except (OSError, ValueError) as exc:
            print(f"ERROR: {exc}")
            return 2
        for message in messages:
            print(message)
        return 0 if ok else 1
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
