from __future__ import annotations

import json
import os
import re
from pathlib import Path


PATTERNS = {
    "gtex": ("tissue-partitioned bulk RNA-seq models", "tissue_id"),
    "motrpac": ("tissue-partitioned transcriptomics models", "tissue_id"),
    "hubmap": ("released ASCT+B library workflow", "partition_id"),
    "lincs_l1000": ("shared signature-source models", "partition_id"),
    "generic": ("library-specific DIG workflow", "partition_id"),
}

INPUT_HEADERS = ["input_id", "source_uri_or_access_instructions", "version_release", "checksum", "access_method", "smoke_full", "workflow_stage", "redistribution_status", "committed_fixture", "fixture_path"]
OUTPUT_HEADERS = ["output_id", "relative_path", "role", "required", "model_id", "partition_id"]
TASK_HEADERS = ["task_id", "model_id", "partition_id", "enabled", "dig_identifier", "output_relative_path"]


def _write(path: Path, text: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    if executable:
        path.chmod(path.stat().st_mode | 0o111)


def scaffold(root: Path, library_id: str, display_name: str, pattern: str) -> None:
    if pattern not in PATTERNS:
        raise ValueError(f"unknown pattern: {pattern}")
    if root.exists():
        raise ValueError(f"output already exists: {root}")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", library_id):
        raise ValueError("library ID must start with a letter and contain only letters, digits, _ or -")
    description, partition_field = PATTERNS[pattern]
    slug = re.sub(r"[^a-z0-9]+", "_", library_id.lower()).strip("_")
    root.mkdir(parents=True)
    payload = {
        "schema_version": "1.0.0",
        "submission_status": "draft",
        "library": {"id": library_id, "display_name": display_name, "organism": "human", "genome_build": "hg38", "assay_types": ["rna_seq"], "closest_reference_pattern": pattern, "wrapper_directory": "."},
        "sources": [{"name": "TODO source", "uri_or_identifier": "TODO", "release": "TODO", "access_restrictions": "TODO", "license": "TODO"}],
        "dig": {"repository_url": "https://github.com/flannick/dig-gene-set-extractors", "commit": "TODO", "entrypoints": ["geneset-extractors workflows TODO"], "identifiers": ["TODO"]},
        "configs": {"model_config": "config/model_list.tsv", "partition_config": "config/partition_list.tsv", "description_config": "config/model_description_templates.tsv", "task_manifest": "config/task_manifest.tsv"},
        "reproduction": {"entry_point": "reproduction/reproduce.sh", "input_manifest": "reproduction/input_manifest.tsv", "smoke_test_command": "bash reproduction/reproduce.sh --smoke"},
        "expected_outputs": {"manifest": "expected/output_manifest.tsv"},
        "provenance": {"contracts": [{"scope": "full", "output_manifest": "expected/output_manifest.tsv", "provenance_filename": "geneset.provenance.json", "required_input_ids": []}]},
        "environment": {"declaration": "TODO: document the Python/container environment"},
        "runtime": {"mode": "local", "task_manifest": "config/task_manifest.tsv", "local_builder": f"run/build_{slug}_genesets.sh"},
        "deviations": {"from_standard_architecture": [], "allow_wrapper_findings": [], "allow_provenance_findings": []},
        "paired_pull_requests": {"geneset_extractor_dev": "TBD", "dig_gene_set_extractors": "TBD"},
    }
    _write(root / "submission.yaml", json.dumps(payload, indent=2) + "\n")
    _write(root / "README.md", f"# {display_name}\n\nSubmission scaffold based on the **{pattern}** pattern: {description}.\n\nFill every `TODO` before marking the submission ready.\n")
    _write(root / "config/model_list.tsv", "model_id\tenabled\nM1\tfalse\n")
    _write(root / "config/partition_list.tsv", f"{partition_field}\nexample\n")
    _write(root / "config/model_description_templates.tsv", "model_id\tdescription_template\nM1\tTODO\n")
    _write(root / "config/task_manifest.tsv", "\t".join(TASK_HEADERS) + "\nexample_task\tM1\texample\tfalse\tTODO\tgenesets/example/models/M1\n")
    _write(root / "config/runtime.yaml", "mode: local\n# Set mode: apptainer_cluster only when a reviewed cluster adapter is needed.\n")
    _write(
        root / "config/provenance_overlay.json",
        json.dumps(
            {
                "inputs": {
                    "role:example_input": {
                        "canonical_uri": "TODO: stable source URI or identifier from input_manifest.tsv",
                        "download_url": "TODO: public download URL when applicable",
                        "provider": "TODO",
                        "version": "TODO",
                    }
                }
            },
            indent=2,
        )
        + "\n",
    )
    _write(root / "reproduction/input_manifest.tsv", "\t".join(INPUT_HEADERS) + "\nexample_input\tTODO\tTODO\t\tmanual\tsmoke,full\tworkflow_input\tnot_redistributable\tfalse\t\n")
    _write(root / "expected/output_manifest.tsv", "\t".join(OUTPUT_HEADERS) + "\nexample_output\tgenesets/example/models/M1/extractor/geneset.meta.json\tmetadata\ttrue\tM1\texample\n")
    _write(root / "reproduction/download_inputs.sh", "#!/usr/bin/env bash\nset -euo pipefail\necho 'TODO: obtain inputs described in input_manifest.tsv'\n", executable=True)
    _write(root / "reproduction/reproduce.sh", f"#!/usr/bin/env bash\nset -euo pipefail\nmode=${{1:---smoke}}\ncase \"${{mode}}\" in --smoke|full) ;; *) echo 'usage: reproduce.sh [--smoke|full]' >&2; exit 2;; esac\n# Isolated workspaces provide this external location for generated artifacts.\noutput_root=${{SUBMISSION_WORK_DIR:-\"$PWD\"}}\nmkdir -p \"${{output_root}}\"\nif [[ \"${{mode}}\" == \"full\" ]]; then bash reproduction/download_inputs.sh; fi\n# The builder is the single local execution path; select smoke tasks from the manifest.\nbash run/build_{slug}_genesets.sh \"${{mode}}\" --out-root \"${{output_root}}\"\n", executable=True)
    _write(root / f"run/build_{slug}_genesets.sh", f"#!/usr/bin/env bash\nset -euo pipefail\nSCRIPT_DIR=\"$(cd -- \"$(dirname -- \"${{BASH_SOURCE[0]}}\")\" && pwd -P)\"\nLIBRARY_ROOT=\"$(cd -- \"${{SCRIPT_DIR}}/..\" && pwd -P)\"\nmode=\"${{1:?usage: build_{slug}_genesets.sh --smoke|full --out-root PATH}}\"\nshift\n# -- keeps --smoke a positional mode for thin Python dispatchers.\nexec \"${{PYTHON_BIN:-python3}}\" \"${{LIBRARY_ROOT}}/src/run_{slug}_task.py\" \"$@\" -- \"${{mode}}\"\n", executable=True)
    _write(root / f"src/run_{slug}_task.py", """\"\"\"Thin task dispatcher scaffold; DIG owns all scientific processing.\"\"\"\nfrom __future__ import annotations\n\nimport argparse\nfrom pathlib import Path\n\n\ndef main() -> int:\n    parser = argparse.ArgumentParser()\n    parser.add_argument(\"mode\", choices=(\"--smoke\", \"full\"))\n    parser.add_argument(\"--task-id\")\n    parser.add_argument(\"--out-root\", required=True)\n    args = parser.parse_args()\n    manifest = Path(__file__).resolve().parents[1] / \"config\" / \"task_manifest.tsv\"\n    print(f\"TODO: select declared task(s) from {manifest} and invoke the pinned DIG entry point; output root is {args.out_root}\")\n    return 0\n\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n""")
    _write(root / "src/README.md", "Thin wrapper-only code belongs here. Do not add analysis, mapping, statistics, or GMT writing.\n")
    _write(root / "tests/fixtures/README.md", "Small, committed smoke fixtures only; list each in input_manifest.tsv.\n")
