#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_outputs_root() -> Path:
    return repo_root() / "geneset-extractor-dev" / "GTEx" / "outputs" / "genesets"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write per-genesets.gmt markdown files describing the commands that produced each GMT."
    )
    parser.add_argument(
        "--outputs_root",
        default=str(default_outputs_root()),
        help="GTEx outputs/genesets root to scan for tissue directories with a unified models directory.",
    )
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def normalize_recorded_commands(text: str, tissue_root: Path) -> str:
    legacy_root = str(tissue_root.parent.parent / tissue_root.name)
    current_root = str(tissue_root)
    return text.replace(legacy_root, current_root)


def extract_logged_commands(run_log_text: str) -> list[str]:
    commands: list[str] = []
    for line in run_log_text.splitlines():
        if line.startswith("$ "):
            commands.append(line[2:].strip())
    return commands


def current_python_bin() -> str:
    candidate = Path("/home/ryank/software/miniconda3/envs/work/bin/python")
    return str(candidate) if candidate.exists() else "python3"


def current_rscript_bin() -> str:
    candidate = Path("/home/ryank/software/miniconda3/envs/work/bin/Rscript")
    return str(candidate) if candidate.exists() else "Rscript"


def current_gtf_path() -> str:
    candidate = repo_root() / "inputs" / "GTEx" / "v10" / "gencode.v26.annotation.gtf.gz"
    return str(candidate)


def wrapper_command_for(gmt_path: Path) -> str:
    root = repo_root()
    model_id = gmt_path.parents[1].name
    if "tissue_extractor" in gmt_path.parts:
        tissue_root = gmt_path.parents[3]
        tissue_id = tissue_root.name
        return " ".join(
            [
                "bash",
                str(root / "geneset-extractor-dev" / "GTEx" / "run" / "build_genesets.sh"),
                "--tissues",
                tissue_id,
                "--models",
                model_id,
            ]
        )
    tissue_root = gmt_path.parents[4] if gmt_path.parent.name.startswith("age") else gmt_path.parents[3]
    model_id = gmt_path.parents[2].name if gmt_path.parent.name.startswith("age") else gmt_path.parents[1].name
    return " ".join(
        [
            "bash",
            str(root / "geneset-extractor-dev" / "GTEx" / "run" / "build_genesets.sh"),
            "--tissues",
            tissue_root.name,
            "--models",
            model_id,
        ]
    )


def discover_gmts(outputs_root: Path) -> list[Path]:
    gmts: list[Path] = []
    for tissue_dir in sorted(path for path in outputs_root.iterdir() if path.is_dir()):
        models_dir = tissue_dir / "models"
        if models_dir.exists():
            gmts.extend(sorted(models_dir.glob("AB*/extractor/genesets.gmt")))
            gmts.extend(sorted(models_dir.glob("AB*/extractor/age*/genesets.gmt")))
            gmts.extend(sorted(models_dir.glob("AC*/tissue_extractor/genesets.gmt")))
            gmts.extend(sorted(models_dir.glob("TV*/tissue_extractor/genesets.gmt")))
    return gmts


def model_context(gmt_path: Path) -> dict[str, str | Path]:
    if "tissue_extractor" in gmt_path.parts:
        tissue_root = gmt_path.parents[3]
        model_dir = gmt_path.parents[1]
        if model_dir.name.startswith("AC"):
            model_group = "continuous_age"
        else:
            model_group = "tissue_versus"
        return {
            "model_group": model_group,
            "tissue_id": tissue_root.name,
            "model_id": model_dir.name,
            "model_dir": model_dir,
            "tissue_root": tissue_root,
            "scope": "tissue",
            "scope_label": tissue_root.name,
            "commands_md": model_dir / "commands.md",
            "run_log": model_dir / "run.log",
            "workflow_script": model_dir / "workflow" / "run_continuous_age_limma_voom.R",
        }
    if gmt_path.parent.name.startswith("age"):
        tissue_root = gmt_path.parents[4]
        model_dir = gmt_path.parents[2]
    else:
        tissue_root = gmt_path.parents[3]
        model_dir = gmt_path.parents[1]
    scope = "combined"
    scope_label = "all comparisons"
    if gmt_path.parent.name.startswith("age"):
        scope = "comparison"
        scope_label = gmt_path.parent.name
    return {
        "model_group": "age_binned",
        "tissue_id": tissue_root.name,
        "model_id": model_dir.name,
        "model_dir": model_dir,
        "tissue_root": tissue_root,
        "scope": scope,
        "scope_label": scope_label,
        "commands_md": model_dir / "commands.md",
        "run_log": model_dir / "run.log",
        "workflow_script": model_dir / "workflow" / "backend_work" / "run_limma_voom.R",
    }


def render_markdown(gmt_path: Path) -> str:
    ctx = model_context(gmt_path)
    tissue_root = Path(ctx["tissue_root"])
    commands_md_path = Path(ctx["commands_md"])
    run_log_path = Path(ctx["run_log"])
    workflow_script = Path(ctx["workflow_script"])
    recorded_commands_text = normalize_recorded_commands(read_text(commands_md_path), tissue_root)
    run_log_text = normalize_recorded_commands(read_text(run_log_path), tissue_root)
    logged_commands = extract_logged_commands(run_log_text)

    lines: list[str] = [
        "# genesets.gmt Command Provenance",
        "",
        f"- generated_at: `{utc_now()}`",
        f"- output_gmt: `{gmt_path}`",
        f"- tissue_id: `{ctx['tissue_id']}`",
        f"- model_group: `{ctx['model_group']}`",
        f"- model_id: `{ctx['model_id']}`",
        f"- scope: `{ctx['scope']}`",
        f"- scope_label: `{ctx['scope_label']}`",
        "",
        "## Top-Level Wrapper Command",
        "",
        "```bash",
        wrapper_command_for(gmt_path),
        "```",
        "",
    ]

    if workflow_script.exists():
        lines.extend(
            [
                "## Workflow Script Path",
                "",
                f"- `{workflow_script}`",
                "",
            ]
        )

    if recorded_commands_text.strip():
        lines.extend(
            [
                "## Recorded Model Commands",
                "",
                "These commands were recorded with the model output and correspond to the workflow and extractor stages.",
                "",
                recorded_commands_text.rstrip(),
                "",
            ]
        )

    lines.extend(["## Logged Executed Commands", ""])
    if logged_commands:
        for command in logged_commands:
            lines.extend(["```bash", command, "```", ""])
    else:
        lines.extend(
            [
                "No explicit `$ ...` command lines were recorded in `run.log` for this model output.",
                "",
            ]
        )

    if ctx["model_group"] == "models":
        lines.extend(
            [
                "## Notes",
                "",
                "- For comparison models, one workflow run produces `workflow/deg_long.tsv` and one extractor run produces both the combined root `genesets.gmt` and the per-comparison `age*/genesets.gmt` files.",
                "- The same wrapper, workflow, and extractor commands apply to each `age*/genesets.gmt` file under the model.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Notes",
                "",
                "- For tissue models, one continuous-age R workflow run produces `tissue_deg.tsv`, then one `rna_deg` extractor run produces the tissue-level `genesets.gmt`.",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    outputs_root = Path(args.outputs_root).resolve()
    gmts = discover_gmts(outputs_root)
    for gmt_path in gmts:
        md_path = gmt_path.with_name("genesets.commands.md")
        log_path = gmt_path.with_name("genesets.commands.log")
        write_text(md_path, render_markdown(gmt_path))
        write_text(log_path, f"[{utc_now()}] wrote {md_path.name} for {gmt_path.name}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
