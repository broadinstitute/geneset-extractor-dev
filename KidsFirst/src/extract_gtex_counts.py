#!/usr/bin/env python3
"""Compatibility entrypoint for the GTEx normal count-matrix extraction.

The implementation is owned by DIG:
``geneset_extractors.workflows.kidsfirst_prepare.extract_gtex_matrix``.

This wrapper keeps the original CLI so existing run scripts keep working, but the
logic now lives in DIG (branch two-repo standard). The canonical entry point is
``geneset-extractors workflows kidsfirst_prepare`` (see run/run_kf_de_study.sh),
which can extract the GTEx normal matrix as part of preparing the combined DE inputs.

Requires the DIG environment (``geneset_extractors`` importable): invoke with the
DIG venv Python, e.g. ``dig-gene-set-extractors/.venv/bin/python extract_gtex_counts.py``.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from geneset_extractors.workflows.kidsfirst_prepare import extract_gtex_matrix


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--gct", required=True, help="GTEx GCT .gz file")
    p.add_argument("--sample_attrs", required=True,
                   help="GTEx_Analysis_v10_Annotations_SampleAttributesDS.txt")
    p.add_argument("--tissue", required=True, help="SMTSD value, e.g. 'Whole Blood'")
    p.add_argument("--out_tsv", required=True)
    args = p.parse_args()

    extract_gtex_matrix(
        Path(args.gct),
        Path(args.sample_attrs),
        args.tissue,
        Path(args.out_tsv),
    )


if __name__ == "__main__":
    main()
