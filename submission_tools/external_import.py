"""Scaffold a truthful multi-model wrapper for externally generated GMTs."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from .scaffold import scaffold
from .yaml_loader import load


HEADERS = {"model_id", "display_name", "source_gmt_path", "sha256", "description", "partition_id"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source(path: Path) -> dict[str, Any]:
    payload = load(path)
    source = payload.get("source", payload)
    if not isinstance(source, dict):
        raise ValueError("source manifest requires a source mapping")
    required = ("name", "uri_or_identifier", "release", "license", "access_restrictions", "organism", "genome_build", "assay", "data_type")
    missing = [key for key in required if not str(source.get(key, "")).strip()]
    if missing:
        raise ValueError(f"source manifest missing: {', '.join(missing)}")
    return dict(source)


def _models(path: Path, gmt_root: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        missing = HEADERS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"GMT manifest missing headers: {', '.join(sorted(missing))}")
        rows = list(reader)
    if not rows:
        raise ValueError("GMT manifest has no model rows")
    seen: set[str] = set()
    resolved_root = gmt_root.resolve()
    for row in rows:
        model_id = row["model_id"].strip()
        if not model_id or model_id in seen:
            raise ValueError(f"model_id must be non-empty and unique: {model_id!r}")
        seen.add(model_id)
        source = Path(row["source_gmt_path"]).expanduser().resolve()
        try:
            relative = source.relative_to(resolved_root)
        except ValueError as exc:
            raise ValueError(f"GMT for {model_id} is outside --gmt-root: {source}") from exc
        if not source.is_file():
            raise ValueError(f"GMT for {model_id} does not exist: {source}")
        digest = _sha256(source)
        declared = row["sha256"].removeprefix("sha256:").strip()
        if declared and declared != digest:
            raise ValueError(f"GMT checksum mismatch for {model_id}: declared {declared}, observed {digest}")
        row["sha256"] = "sha256:" + digest
        row["source_relative_path"] = relative.as_posix()
    return rows


def scaffold_external_library(*, library_id: str, display_name: str, source_manifest: Path, gmt_manifest: Path, gmt_root: Path, output: Path) -> Path:
    source = _source(source_manifest)
    rows = _models(gmt_manifest, gmt_root)
    scaffold(output, library_id, display_name, "generic")
    config = output / "config"
    (config / "external_source.json").write_text(json.dumps(source, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    fields = ["model_id", "display_name", "source_relative_path", "sha256", "description", "partition_id"]
    with (config / "external_model_manifest.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader(); writer.writerows({field: row[field] for field in fields} for row in rows)
    (config / "model_list.tsv").write_text("model_id\tenabled\n" + "".join(f"{row['model_id']}\ttrue\n" for row in rows), encoding="utf-8")
    (config / "partition_list.tsv").write_text("partition_id\n" + "".join(f"{row['partition_id']}\n" for row in rows), encoding="utf-8")
    (config / "model_description_templates.tsv").write_text("model_id\tdescription_template\n" + "".join(f"{row['model_id']}\t{row['description']}\n" for row in rows), encoding="utf-8")
    input_lines = ["input_id\tsource_uri_or_access_instructions\tversion_release\tchecksum\taccess_method\tsmoke_full\tworkflow_stage\tredistribution_status\tcommitted_fixture\tfixture_path"]
    output_lines = ["output_id\trelative_path\trole\trequired\tmodel_id\tpartition_id"]
    task_lines = ["task_id\tmodel_id\tpartition_id\tenabled\tdig_identifier\toutput_relative_path"]
    for row in rows:
        model = row["model_id"]
        input_lines.append(f"external_{model}\t{row['source_relative_path']}\t{source['release']}\t{row['sha256']}\tmanual\tfull\texternal_precomputed_import\t{source['access_restrictions']}\tfalse\t")
        base = f"genesets/{row['partition_id']}/models/{model}/external_import"
        task_lines.append(f"import_{model}\t{model}\t{row['partition_id']}\ttrue\texternal_precomputed_import\t{base}")
        for output_id, filename, role in (("gmt", "genesets.gmt", "gmt"), ("metadata", "geneset.meta.json", "metadata"), ("legacy_provenance", "geneset.provenance.legacy.json", "provenance"), ("dapper_provenance", "geneset.provenance.dapper.yaml", "provenance")):
            output_lines.append(f"{model}_{output_id}\t{base}/{filename}\t{role}\ttrue\t{model}\t{row['partition_id']}")
    (output / "reproduction/input_manifest.tsv").write_text("\n".join(input_lines) + "\n", encoding="utf-8")
    (output / "expected/output_manifest.tsv").write_text("\n".join(output_lines) + "\n", encoding="utf-8")
    (config / "task_manifest.tsv").write_text("\n".join(task_lines) + "\n", encoding="utf-8")
    payload = load(output / "submission.yaml")
    payload["sources"] = [
        {
            "name": f"external_{row['model_id']}",
            **{key: source[key] for key in ("uri_or_identifier", "release", "access_restrictions", "license")},
        }
        for row in rows
    ]
    payload["library"].update({"organism": source["organism"], "genome_build": source["genome_build"], "assay_types": [source["assay"]]})
    payload["dig"].update({"entrypoints": ["geneset-extractors external-import"], "identifiers": ["external_precomputed_import"]})
    payload["submission_origin"] = {"type": "external_precomputed_import", "scientific_generation_code_available": False}
    payload["external_import"] = {"source_config": "config/external_source.json", "model_manifest": "config/external_model_manifest.tsv", "regeneration_status": "incomplete_code", "attestation": "Imported GMTs are verified unchanged; external scientific generation is not reproduced by repository code."}
    payload["provenance"] = {"contracts": [{"scope": "full", "output_manifest": "expected/output_manifest.tsv", "provenance_filename": "geneset.provenance.legacy.json", "required_input_ids": [f"external_{row['model_id']}" for row in rows]}]}
    (output / "submission.yaml").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in library_id).strip("_")
    (output / "reproduction/download_inputs.sh").write_text("#!/usr/bin/env bash\nset -euo pipefail\necho 'Provide external GMTs through EXTERNAL_GMT_INPUT_ROOT; this library never downloads or regenerates them.'\n", encoding="utf-8")
    (output / "reproduction/download_inputs.sh").chmod(0o755)
    (output / "reproduction/reproduce.sh").write_text(f"#!/usr/bin/env bash\nset -euo pipefail\nROOT=\"$(cd -- \"$(dirname -- \"${{BASH_SOURCE[0]}}\")/..\" && pwd -P)\"\nmode=${{1:---smoke}}\ncase \"$mode\" in --smoke|full) ;; *) exit 2;; esac\nexec bash \"$ROOT/run/import_{slug}_models.sh\" \"$mode\"\n", encoding="utf-8")
    (output / "reproduction/reproduce.sh").chmod(0o755)
    (output / f"run/import_{slug}_models.sh").write_text(f"#!/usr/bin/env bash\nset -euo pipefail\nexec \"${{PYTHON_BIN:-python3}}\" \"$(cd -- \"$(dirname -- \"${{BASH_SOURCE[0]}}\")\" && pwd)/../src/import_external_models.py\" \"$@\"\n", encoding="utf-8")
    (output / f"run/import_{slug}_models.sh").chmod(0o755)
    (output / "src/import_external_models.py").write_text(_DISPATCHER, encoding="utf-8")
    (output / "README.md").write_text(f"# {display_name}\n\nThis is an external precomputed GMT import. Repository code validates and imports the supplied GMTs unchanged; it does not reproduce the external scientific generation.\n", encoding="utf-8")
    return output


_DISPATCHER = '''from __future__ import annotations
import csv, os, subprocess, sys
from pathlib import Path

def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"--smoke", "full"}:
        raise SystemExit("usage: import_external_models.py [--smoke|full]")
    mode = sys.argv[1]
    root = Path(__file__).resolve().parents[1]
    input_root = os.environ.get("EXTERNAL_GMT_INPUT_ROOT")
    if not input_root:
        raise SystemExit("EXTERNAL_GMT_INPUT_ROOT must identify the read-only source GMT root")
    out_root = Path(os.environ.get("SUBMISSION_WORK_DIR", root))
    with (root / "config/external_model_manifest.tsv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\\t"))
    if mode == "--smoke": rows = rows[:1]
    for row in rows:
        out = out_root / "genesets" / row["partition_id"] / "models" / row["model_id"] / "external_import"
        command = [sys.executable, "-m", "geneset_extractors.cli", "external-import", "--gmt", str(Path(input_root) / row["source_relative_path"]), "--out-dir", str(out), "--source-record", str(root / "config/external_source.json"), "--library-id", root.name, "--model-id", row["model_id"], "--display-name", row["display_name"], "--description", row["description"], "--expected-sha256", row["sha256"]]
        subprocess.run(command, check=True)
    return 0
if __name__ == "__main__": raise SystemExit(main())
'''
