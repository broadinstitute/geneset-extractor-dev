#!/usr/bin/env python3
"""Fetch IGVF processed differential-expression files for one or more datasets.

Released IGVF data is open (no API key). This mirrors the documented convention:
  metadata: GET https://api.data.igvf.org/<datasetId>/         -> <studyId>/<datasetId>/<datasetId>.metadata.json
  file:     GET https://api.data.igvf.org/tabular-files/<datasetId>/@@download/<datasetId>.<ext>

The file extension (csv.gz / tsv.gz) is read from the dataset metadata (file_format), and a
sources.tsv mapping each local file to its canonical IGVF URL is written per analysis set so
provenance refresh can point at the true external input.

Usage:
  # one dataset under an analysis set:
  ./fetch_igvf_inputs.py --analysis_set IGVFDS6924DJAZ --dataset IGVFFI0068OWUG [--out_root inputs/IGVF]
  # many at once from a TSV with columns analysis_set_id, dataset_id:
  ./fetch_igvf_inputs.py --worklist worklist.tsv [--out_root inputs/IGVF]
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen

PORTAL = "https://api.data.igvf.org"


def fetch_json(url: str) -> dict:
    with urlopen(url, timeout=120) as resp:  # noqa: S310 (trusted host)
        return json.loads(resp.read().decode("utf-8"))


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Use curl -L to follow the @@download redirect to S3.
    subprocess.run(["curl", "-fsSL", "-o", str(dest), url], check=True)


def fetch_dataset(analysis_set: str, dataset: str, out_root: Path) -> dict[str, str]:
    out_dir = out_root / analysis_set / dataset
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = fetch_json(f"{PORTAL}/{dataset}/")
    (out_dir / f"{dataset}.metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    fmt = str(meta.get("file_format", "")).strip() or "tsv"
    href = str(meta.get("href", "")).strip() or f"/tabular-files/{dataset}/@@download/{dataset}.{fmt}.gz"
    ext = href.split("@@download/")[-1].split(".", 1)[-1] if "@@download/" in href else f"{fmt}.gz"
    local = out_dir / f"{dataset}.{ext}"
    download(f"{PORTAL}{href}" if href.startswith("/") else href, local)
    return {
        "analysis_set_id": analysis_set,
        "dataset_id": dataset,
        "local_path": str(local),
        "source_uri": f"https://data.igvf.org/tabular-files/{dataset}/",
        "content_type": str(meta.get("content_type", "")),
        "file_format": fmt,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis_set")
    ap.add_argument("--dataset")
    ap.add_argument("--worklist", help="TSV with columns analysis_set_id, dataset_id")
    ap.add_argument("--out_root", default="inputs/IGVF")
    args = ap.parse_args()

    out_root = Path(args.out_root).expanduser().resolve()
    jobs: list[tuple[str, str]] = []
    if args.worklist:
        with open(args.worklist, encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                a = str(row.get("analysis_set_id", "")).strip()
                d = str(row.get("dataset_id", "")).strip()
                if a and d:
                    jobs.append((a, d))
    elif args.analysis_set and args.dataset:
        jobs.append((args.analysis_set, args.dataset))
    else:
        ap.error("provide --analysis_set and --dataset, or --worklist")

    records: list[dict[str, str]] = []
    for analysis_set, dataset in jobs:
        print(f"fetching {analysis_set}/{dataset} ...", file=sys.stderr)
        records.append(fetch_dataset(analysis_set, dataset, out_root))

    # Write a per-analysis-set source map for provenance refresh.
    by_set: dict[str, list[dict[str, str]]] = {}
    for rec in records:
        by_set.setdefault(rec["analysis_set_id"], []).append(rec)
    for analysis_set, recs in by_set.items():
        sm = out_root / analysis_set / "source_map.tsv"
        with sm.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, delimiter="\t", fieldnames=["local_path", "source_uri"], lineterminator="\n")
            w.writeheader()
            for rec in recs:
                w.writerow({"local_path": rec["local_path"], "source_uri": rec["source_uri"]})
    print(f"done: {len(records)} file(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
