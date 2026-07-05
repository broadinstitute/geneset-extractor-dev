#!/usr/bin/env python3
"""Compatibility entrypoint for building the combined tumor+normal DE inputs.

The implementation is owned by DIG:
``geneset_extractors.workflows.kidsfirst_prepare.merge_de_inputs``.

This wrapper keeps the original CLI so existing run scripts keep working, but the
logic now lives in DIG (branch two-repo standard). The canonical entry point is
``geneset-extractors workflows kidsfirst_prepare`` (see run/run_kf_de_study.sh),
which builds tumor + normal matrices and emits combined_counts.tsv +
sample_metadata.tsv in one call.

Requires the DIG environment (``geneset_extractors`` importable): invoke with the
DIG venv Python, e.g. ``dig-gene-set-extractors/.venv/bin/python prepare_de_inputs.py``.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from geneset_extractors.workflows.kidsfirst_prepare import merge_de_inputs


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tumor_counts", required=True)
    p.add_argument("--normal_counts", required=True)
    p.add_argument("--tumor_metadata", default=None)
    p.add_argument("--study_id", required=True)
    p.add_argument("--out_dir", required=True)
    p.add_argument("--gene_map_tsv", default=None,
                   help="TSV with gene_id and gene_symbol columns")
    args = p.parse_args()

    merge_de_inputs(
        Path(args.tumor_counts),
        Path(args.normal_counts),
        Path(args.tumor_metadata) if args.tumor_metadata else None,
        args.study_id,
        Path(args.out_dir),
        gene_map_path=Path(args.gene_map_tsv) if args.gene_map_tsv else None,
    )


if __name__ == "__main__":
    main()
