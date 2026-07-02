#!/usr/bin/env python3
"""Enrich a geneset.provenance.json with library/source metadata.

Populates the optional provenance fields (resource, study_id, pipeline, preprocessing,
input_files) added to the CFDE provenance schema, so each graph records the originating
resource and study, the end-to-end analysis pipeline, the immediate input files, and the
scripting/preprocessing applied before the workflow. Pure post-processing; the graph stays
schema-valid (only documented optional fields + description text are touched).

Importable: enrich_provenance(path, resource=..., study_id=..., pipeline=..., preprocessing=..., input_files=...)
CLI: enrich_provenance.py <provenance.json> --resource IGVF --study_id IGVFDS... --pipeline "..." --preprocessing "..."
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def enrich_provenance(
    path: str | Path,
    *,
    resource: str,
    study_id: str,
    pipeline: str,
    preprocessing: str,
    input_files: list[str] | None = None,
) -> dict:
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    gid = next(iter(payload))
    graph = payload[gid]
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    analysis_ids = {n["id"] for n in nodes if n.get("type") == "AnalysisType"}
    input_ids = {
        e["source"]
        for e in edges
        if e.get("target") in analysis_ids and e.get("label") in ("data input", "metadata input")
    }
    if input_files is None:
        input_files = sorted({n.get("name", "") for n in nodes if n.get("id") in input_ids and n.get("name")})

    annot = (
        f" [resource={resource}; study={study_id}; pipeline={pipeline}; "
        f"preprocessing={preprocessing}]"
    )
    for n in nodes:
        if n.get("type") == "AnalysisType":
            c = n.setdefault("c2m2_properties", {})
            c["resource"] = resource
            c["study_id"] = study_id
            c["pipeline"] = pipeline
            c["preprocessing"] = preprocessing
            if input_files:
                c["input_files"] = list(input_files)
            desc = str(n.get("description", ""))
            if "[resource=" not in desc:
                n["description"] = desc + annot
        elif n.get("type") == "File" and n.get("id") in input_ids:
            c = n.setdefault("c2m2_properties", {})
            c["resource"] = resource
            c["study_id"] = study_id

    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("provenance_json")
    ap.add_argument("--resource", required=True)
    ap.add_argument("--study_id", required=True)
    ap.add_argument("--pipeline", required=True)
    ap.add_argument("--preprocessing", required=True)
    ap.add_argument("--input_files", help="comma-separated; default: auto-detect from graph")
    args = ap.parse_args()
    files = [x.strip() for x in args.input_files.split(",")] if args.input_files else None
    enrich_provenance(
        args.provenance_json,
        resource=args.resource,
        study_id=args.study_id,
        pipeline=args.pipeline,
        preprocessing=args.preprocessing,
        input_files=files,
    )
    print(f"enriched {args.provenance_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
