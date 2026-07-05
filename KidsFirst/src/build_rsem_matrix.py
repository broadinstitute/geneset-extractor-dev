#!/usr/bin/env python3
"""Compatibility entrypoint for the KidsFirst tumor RSEM count-matrix build.

The implementation is owned by DIG:
``geneset_extractors.workflows.kidsfirst_prepare.build_tumor_matrix``.

This wrapper keeps the original CLI so existing run scripts keep working, but the
logic now lives in DIG (branch two-repo standard). The canonical entry point is
``geneset-extractors workflows kidsfirst_prepare`` (see run/run_kf_de_study.sh),
which builds the tumor matrix + normal matrix + combined DE inputs in one call.

Requires the DIG environment (``geneset_extractors`` importable): invoke with the
DIG venv Python, e.g. ``dig-gene-set-extractors/.venv/bin/python build_rsem_matrix.py``.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from geneset_extractors.workflows.kidsfirst_prepare import build_tumor_matrix


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--rsem_dir", required=True)
    p.add_argument("--manifest_tsv", default=None)
    p.add_argument("--out_tsv", required=True)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--filter_column", default=None,
                   help="Manifest column to filter on (e.g. 'diagnosis_slug' for CBTN)")
    p.add_argument("--filter_value", default=None,
                   help="Value to keep (e.g. 'low_grade_glioma')")
    args = p.parse_args()

    build_tumor_matrix(
        Path(args.rsem_dir),
        Path(args.manifest_tsv) if args.manifest_tsv else None,
        Path(args.out_tsv),
        args.workers,
        args.filter_column,
        args.filter_value,
    )


if __name__ == "__main__":
    main()
