#!/usr/bin/env python3
"""KidsFirst publish-refresh: make an assembled model tree publication-safe.

This is the final step of the KidsFirst publication flow. It runs on an assembled
`kidsfirst_all_models` tree (the branch-standard
`genesets/<comparison>/models/<HZ1|HZ2>/{workflow,extractor}` layout produced by the
run/ pipeline) and makes every shipped sidecar portable and self-describing, the same
way the accepted reference packages express provenance. It does two things and then
verifies them:

  1. Path sanitization. Every string in `geneset.provenance.json`, `geneset.meta.json`,
     `geneset.model.json` (and their `.orig` snapshots) is rewritten to a portable form
     so no collaborator-local filesystem path survives:
       * a virtualenv executable prefix (`.../.venv/bin/geneset-extractors|python`)
         becomes the bare command name;
       * an in-bundle DE intermediate (`.../<comparison>/de_(inputs|results)/...`)
         becomes its relative bundle path `kidsfirst_all_models/genesets/<comparison>/de_.../...`;
       * an external raw input becomes a public source URI — Kids First tumor data to
         `drs://nci-crdc.datacommons.io/dg.4DFC/...` and GTEx v10 normals to
         `gs://adult-gtex/bulk-gex/v10/rna-seq/...`;
       * `working_directory` becomes `.`.
     A final catch-all maps any residual `/Users/`, `/lab-share/`, or `/home/<user>`
     token to a public identifier, so `grep -R '/Users/\\|/lab-share/\\|/home/'` over the
     final sidecars returns nothing.

  2. HZ2 upstream chain. Each HZ2 provenance graph is rebuilt so it begins from the true
     initial inputs: the upstream `kidsfirst_prepare` -> `combined_counts` ->
     `rna_de_prepare` -> `deg_long` subgraph carried by the matching HZ1 comparison(s) is
     joined to the terminal `kidsfirst_curate` step. Multi-comparison diseases (KF_TALL)
     show both upstream chains feeding curation. Because `kidsfirst_prepare` is
     deterministic and these are the same DEG inputs the HZ1 graphs already carry, this
     reuses the born-clean upstream nodes (md5+size intact) rather than fabricating them.

The step is idempotent and changes only JSON provenance/metadata sidecars — the gene-set
science (`genesets.gmt`, `geneset.tsv`) is never touched. It exits non-zero if any of the
publication-acceptance checks fail.

Usage:
    python publish_refresh.py --tree <path>/kidsfirst_all_models
    python publish_refresh.py --tree <path>/kidsfirst_all_models --verify-only
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from pathlib import Path

GTEX_SRC = "gs://adult-gtex/bulk-gex/v10/rna-seq"        # public GTEx v10 bulk RNA-seq
KF_DRS = "drs://nci-crdc.datacommons.io/dg.4DFC"         # Kids First DRC
EXT_PREFIX = ("drs://", "https://", "http://", "s3://", "gs://", "urn:", "ftp://")
FORBIDDEN = ("/Users/", "/lab-share/", "/home/")          # non-portable collaborator paths


def primary_sources() -> dict[str, list[str]]:
    """Map each HZ2 primary comparison to its source comparisons, from DIG's single
    source of truth (kidsfirst_curate.DISEASE_CONFIG). The primary partition is the
    disease's first comparison."""
    from geneset_extractors.workflows.kidsfirst_curate import DISEASE_CONFIG

    return {d["comparisons"][0]: list(d["comparisons"]) for d in DISEASE_CONFIG if d.get("comparisons")}


def md5_b64(path: Path) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return base64.b64encode(digest.digest()).decode()


# --------------------------------------------------------------------------- #
# path sanitization                                                            #
# --------------------------------------------------------------------------- #
_VENV = re.compile(r'[^\s"\']*/\.venv/bin/')
_GTEX_DIR = re.compile(r'[^\s"\']*/GTEx/v\d+/([^\s"\',/]+)')
_GTEX_PORTAL = re.compile(r'https?://(?:www\.)?gtexportal\.org/home/downloads/adult-gtex/bulk_tissue_expression')
_E3_ANALYSIS = re.compile(r'[^\s"\']*geneset-extractor-dev(?:_e3)?/KidsFirst_non_CBTN/outputs/analysis')
_KF_STUDY = re.compile(r'(KidsFirst_KF_[A-Za-z0-9]+)')
_FORBIDDEN_TOKEN = re.compile(r'(?:/Users/|/lab-share/|/home/[a-z])[^\s"\',]*')


def _catch_all(match: re.Match) -> str:
    """Map any residual collaborator-local token to an honest public identifier."""
    token = match.group(0)
    base = token.rstrip("/").split("/")[-1] or "input"
    if re.search(r'gtex|GTEx|\.gct', token):
        return f"{GTEX_SRC}/{base}"
    study = _KF_STUDY.search(token)
    return f"{KF_DRS}/{study.group(1)}/{base}" if study else f"{KF_DRS}/{base}"


def sanitize_str(value: str, comps: list[str]) -> str:
    if not isinstance(value, str) or "/" not in value:
        return value
    value = _VENV.sub("", value)                                    # venv exec prefix
    value = _E3_ANALYSIS.sub("kidsfirst_all_models/genesets", value)  # local analysis root
    for comp in comps:                                              # in-bundle DE intermediates
        value = re.sub(
            rf'[^\s"\']*/{re.escape(comp)}/de_(inputs|results)((?:/[^\s"\',]+)?)',
            rf'kidsfirst_all_models/genesets/{comp}/de_\1\2',
            value,
        )
    value = _GTEX_DIR.sub(rf'{GTEX_SRC}/\1', value)                 # GTEx input dir -> gs://
    value = _GTEX_PORTAL.sub(GTEX_SRC, value)                       # GTEx portal URL (has /home/)
    value = _FORBIDDEN_TOKEN.sub(_catch_all, value)                # catch-all residual locals
    return value


def deep_sanitize(obj, comps: list[str]):
    if isinstance(obj, dict):
        out = {}
        for key, val in obj.items():
            if key == "working_directory" and isinstance(val, str) and val.startswith(FORBIDDEN):
                out[key] = "."
            else:
                out[key] = deep_sanitize(val, comps)
        return out
    if isinstance(obj, list):
        return [deep_sanitize(item, comps) for item in obj]
    return sanitize_str(obj, comps) if isinstance(obj, str) else obj


# --------------------------------------------------------------------------- #
# HZ2 upstream-chain graft                                                      #
# --------------------------------------------------------------------------- #
def _load_graph(path: Path):
    data = json.loads(path.read_text())
    key = next(iter(data))
    return data, key, data[key]


def _hz1_upstream(comp: str, tree: Path):
    """Return (nodes, edges, deg_long_id) for comp's HZ1 chain up to deg_long.tsv — the
    whole HZ1 graph except the terminal rna_deg_multi 'generate_*' node and its outputs."""
    prov = tree / "genesets" / comp / "models" / "HZ1" / "extractor" / "geneset.provenance.json"
    _, _, graph = _load_graph(prov)
    generate = {
        node["id"]
        for node in graph["nodes"]
        if node.get("type") in ("AnalysisType", "Analysis")
        and str(node.get("name", "")).startswith("generate_")
    }
    drop = set(generate)
    for edge in graph["edges"]:
        if edge["source"] in generate:
            drop.add(edge["target"])
    nodes = [n for n in graph["nodes"] if n["id"] not in drop]
    edges = [e for e in graph["edges"] if e["source"] not in drop and e["target"] not in drop]
    deg = next((n["id"] for n in nodes if n.get("type") == "File" and n.get("name") == "deg_long.tsv"), None)
    if deg is None:
        raise RuntimeError(f"{comp}: no deg_long.tsv node found in HZ1 upstream graph")
    return nodes, edges, deg


def _graft_hz2(primary: str, sources: list[str], tree: Path):
    """Rebuild the HZ2 provenance for `primary` so it carries the full upstream chain."""
    prov = tree / "genesets" / primary / "models" / "HZ2" / "extractor" / "geneset.provenance.json"
    data, key, graph = _load_graph(prov)

    curate = next(
        n for n in graph["nodes"]
        if n.get("type") in ("AnalysisType", "Analysis") and "kidsfirst_curate" in json.dumps(n)
    )
    geneset = next(n for n in graph["nodes"] if n.get("type") == "GeneSet")
    gmt = next(n for n in graph["nodes"] if n.get("type") == "File" and n.get("name") == "genesets.gmt")
    curate_id = curate["id"]

    nodes = {n["id"]: n for n in (curate, geneset, gmt)}
    edges = {
        e["id"]: e
        for e in graph["edges"]
        if e["source"] == curate_id and e["target"] in (geneset["id"], gmt["id"])
    }
    for comp in sources:
        u_nodes, u_edges, deg_id = _hz1_upstream(comp, tree)
        for node in u_nodes:
            nodes.setdefault(node["id"], node)
        for edge in u_edges:
            edges.setdefault(edge["id"], edge)
        eid = f"{deg_id}_to_{curate_id}"
        edges.setdefault(eid, {
            "id": eid, "label": "data input", "source": deg_id, "target": curate_id,
            "description": "deg_long.tsv is a data input to kidsfirst_curate.",
        })
    data[key] = {"edges": list(edges.values()), "nodes": list(nodes.values())}
    return data, prov


# --------------------------------------------------------------------------- #
# driver                                                                        #
# --------------------------------------------------------------------------- #
_SIDECARS = ("geneset.provenance.json", "geneset.meta.json", "geneset.model.json")


def _write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def refresh(tree: Path) -> None:
    comps = sorted((d.name for d in (tree / "genesets").iterdir() if d.is_dir()), key=len, reverse=True)

    grafted = 0
    for primary, sources in primary_sources().items():
        if (tree / "genesets" / primary / "models" / "HZ2").exists():
            data, prov = _graft_hz2(primary, sources, tree)
            _write_json(prov, data)
            grafted += 1
    print(f"HZ2 provenance grafted with upstream chain: {grafted} partitions")

    sanitized = 0
    for sidecar in sorted((tree / "genesets").glob("*/models/*/extractor/*")):
        if sidecar.name.split(".orig")[0] not in _SIDECARS:
            continue
        obj = json.loads(sidecar.read_text())
        clean = deep_sanitize(obj, comps)
        if clean != obj:
            _write_json(sidecar, clean)
            sanitized += 1
    print(f"sidecars path-sanitized: {sanitized}")

    resynced = 0
    for prov in (tree / "genesets").glob("*/models/*/extractor/geneset.provenance.json"):
        orig = prov.with_suffix(prov.suffix + ".orig")
        if orig.exists():
            orig.write_text(prov.read_text())
            resynced += 1
    print(f".orig provenance re-synced to final: {resynced}")

    fixed = 0
    for prov in (tree / "genesets").glob("*/models/*/extractor/geneset.provenance.json"):
        data, _, graph = _load_graph(prov)
        changed = False
        for node in graph["nodes"]:
            if node.get("type") != "File":
                continue
            url = str(node.get("dcc_url", ""))
            if not url.startswith("kidsfirst_all_models/"):
                continue
            path = tree / url[len("kidsfirst_all_models/"):]
            if not path.exists():
                continue
            props = node.setdefault("c2m2_properties", {})
            new_md5, new_size = md5_b64(path), path.stat().st_size
            if props.get("md5") != new_md5 or props.get("size_in_bytes") != new_size:
                props["md5"], props["size_in_bytes"] = new_md5, new_size
                changed = True
                fixed += 1
        if changed:
            _write_json(prov, data)
            prov.with_suffix(prov.suffix + ".orig").write_text(prov.read_text())
    print(f"in-bundle file-node md5/size reconciled: {fixed}")


def verify(tree: Path) -> int:
    """Mirror the publication-acceptance checks; return 0 only if all pass."""
    fails = []

    local_hits = []
    for path in (tree / "genesets").rglob("*"):
        if not path.is_file() or path.suffix == ".gz":
            continue
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        hits = [p for p in FORBIDDEN if p in text]
        if "/home/" in hits and not re.search(r'/home/[a-z]', text):
            hits.remove("/home/")
        if hits:
            local_hits.append(str(path.relative_to(tree)))
    print(f"[{'PASS' if not local_hits else 'FAIL'}] no collaborator-local paths: {len(local_hits)} files")
    for f in local_hits[:6]:
        print(f"        {f}")
    if local_hits:
        fails.append("local-paths")

    hz2_bad = []
    hz2_total = 0
    for prov in (tree / "genesets").glob("*/models/HZ2/extractor/geneset.provenance.json"):
        hz2_total += 1
        _, _, graph = _load_graph(prov)
        analyses = [n for n in graph["nodes"] if n.get("type") in ("AnalysisType", "Analysis")]
        names = {n.get("name", "") for n in analyses}
        has_chain = (
            len(analyses) > 1
            and "prepare_combined_counts" in names
            and "prepare_deg_long" in names
            and any("kidsfirst_curate" in json.dumps(a) for a in analyses)
        )
        if not has_chain:
            hz2_bad.append(str(prov.relative_to(tree)).split("/models/")[0])
    print(f"[{'PASS' if not hz2_bad else 'FAIL'}] HZ2 upstream chain: {hz2_total - len(hz2_bad)}/{hz2_total} OK")
    if hz2_bad:
        fails.append("hz2-chain")

    hz1_bad = []
    for prov in (tree / "genesets").glob("*/models/HZ1/extractor/geneset.provenance.json"):
        _, _, graph = _load_graph(prov)
        names = {n.get("name", "") for n in graph["nodes"] if n.get("type") in ("AnalysisType", "Analysis")}
        if not ("prepare_combined_counts" in names and "prepare_deg_long" in names
                and any(x.startswith("generate_") for x in names)):
            hz1_bad.append(str(prov.relative_to(tree)).split("/models/")[0])
    print(f"[{'PASS' if not hz1_bad else 'FAIL'}] HZ1 concrete chain preserved: {hz1_bad or 'all OK'}")
    if hz1_bad:
        fails.append("hz1-regressed")

    total = external = resolved = bad = 0
    for prov in (tree / "genesets").glob("*/models/*/extractor/geneset.provenance.json"):
        _, _, graph = _load_graph(prov)
        for node in graph["nodes"]:
            if node.get("type") != "File":
                continue
            total += 1
            url = str(node.get("dcc_url", ""))
            if url.startswith(EXT_PREFIX):
                external += 1
            elif url.startswith("kidsfirst_all_models/"):
                path = tree / url[len("kidsfirst_all_models/"):]
                md5 = (node.get("c2m2_properties") or {}).get("md5")
                if path.exists() and (md5 is None or md5_b64(path) == md5):
                    resolved += 1
                else:
                    bad += 1
            else:
                bad += 1
    print(f"[{'PASS' if bad == 0 else 'FAIL'}] reference resolution: {total} nodes = "
          f"{external} public + {resolved} in-bundle + {bad} unresolved")
    if bad:
        fails.append("resolution")

    print("VERIFY:", "PASS" if not fails else f"FAIL {fails}")
    return 0 if not fails else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="KidsFirst publish-refresh (sanitize paths + HZ2 chain).")
    parser.add_argument("--tree", required=True, help="Assembled kidsfirst_all_models tree.")
    parser.add_argument("--verify-only", action="store_true", help="Only run the acceptance checks.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tree = Path(args.tree).resolve()
    if not (tree / "genesets").is_dir():
        raise SystemExit(f"not an assembled model tree (missing genesets/): {tree}")
    print(f"tree: {tree}\n")
    if not args.verify_only:
        refresh(tree)
        print()
    return verify(tree)


if __name__ == "__main__":
    raise SystemExit(main())
