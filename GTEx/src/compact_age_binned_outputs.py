from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


LONG_TOPK_PATTERN = re.compile(
    r"rna_deg_multi__comparison=(age\d+_\d+)__signature=([A-Z]{2}\d+)__score_mode=[A-Za-z0-9_]+__(pos|neg|abs)__topk=\d+"
)
LONG_MASS_PATTERN = re.compile(
    r"rna_deg_multi__comparison=(age\d+_\d+)__signature=([A-Z]{2}\d+)__score_mode=[A-Za-z0-9_]+__(pos|neg|abs)__hpd_mass=[A-Za-z0-9.]+__k=\d+"
)
LONG_BASE_PATTERN = re.compile(
    r"rna_deg_multi__comparison=(age\d+_\d+)__signature=([A-Z]{2}\d+)__score_mode=[A-Za-z0-9_]+"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extractor_out", required=True)
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--model_out")
    return parser.parse_args()


def rename_comparison_dirs(extractor_out: Path) -> None:
    for path in sorted(extractor_out.glob("comparison=*")):
        if not path.is_dir():
            continue
        target = extractor_out / path.name.removeprefix("comparison=")
        if target.exists():
            continue
        path.rename(target)


def shorten_text(text: str) -> str:
    text = LONG_TOPK_PATTERN.sub(lambda m: f"{m.group(2)}__{m.group(1)}__{m.group(3)}", text)
    text = LONG_MASS_PATTERN.sub(lambda m: f"{m.group(2)}__{m.group(1)}__{m.group(3)}", text)
    text = LONG_BASE_PATTERN.sub(lambda m: f"{m.group(2)}__{m.group(1)}", text)
    text = text.replace("comparison=age", "age")
    return text


def rewrite_text_file(path: Path) -> bool:
    raw = path.read_bytes()
    had_crlf = b"\r\n" in raw
    try:
        original = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False
    updated = shorten_text(original)
    if updated == original and not had_crlf:
        return False
    path.write_text(updated, encoding="utf-8", newline="\n")
    return True


def rewrite_manifest(manifest_path: Path) -> bool:
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
        fieldnames = list(rows[0].keys()) if rows else []
    changed = False
    for row in rows:
        for column in ("path", "meta_path", "provenance_path"):
            value = str(row.get(column, ""))
            updated = value.replace("comparison=age", "age")
            if updated != value:
                row[column] = updated
                changed = True
    if not changed:
        return False
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return True


def main() -> int:
    args = parse_args()
    extractor_out = Path(args.extractor_out)
    model_out = Path(args.model_out) if args.model_out else extractor_out.parent

    rename_comparison_dirs(extractor_out)

    manifest_path = extractor_out / "manifest.tsv"
    if manifest_path.exists():
        rewrite_manifest(manifest_path)

    workflow_dir = model_out / "workflow"
    if workflow_dir.exists():
        for path in workflow_dir.rglob("*"):
            if path.is_file():
                rewrite_text_file(path)

    for path in extractor_out.rglob("*"):
        if path.is_file():
            rewrite_text_file(path)

    run_log = model_out / "run.log"
    if run_log.exists():
        rewrite_text_file(run_log)

    commands_md = model_out / "commands.md"
    if commands_md.exists():
        rewrite_text_file(commands_md)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
