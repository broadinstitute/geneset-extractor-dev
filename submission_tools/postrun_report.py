#!/usr/bin/env python3
"""Create an auditable, wrapper-side summary of completed GMT outputs.

This module deliberately only reads final GMTs and their nearby sidecars.  It
does not participate in gene-set construction and can therefore be run after
any completed wrapper/DIG workflow.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import itertools
import json
import logging
import math
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape


LOG = logging.getLogger(__name__)


def _open_text(path: Path):
    return gzip.open(path, "rt", encoding="utf-8", newline="") if path.suffix == ".gz" else path.open("r", encoding="utf-8", newline="")


def read_gmt(path: Path) -> tuple[dict[str, set[str]], list[str]]:
    """Read a GMT without silently merging duplicate names."""
    sets: dict[str, set[str]] = {}
    warnings: list[str] = []
    with _open_text(path) as handle:
        for line_number, line in enumerate(handle, 1):
            fields = line.rstrip("\r\n").split("\t")
            if not line.strip():
                continue
            if len(fields) < 3 or not fields[0].strip():
                warnings.append(f"{path}:{line_number}: malformed GMT record skipped")
                continue
            name = fields[0].strip()
            if name in sets:
                warnings.append(f"{path}:{line_number}: duplicate gene-set name {name!r}; later record skipped")
                continue
            sets[name] = {gene.strip() for gene in fields[2:] if gene.strip()}
    return sets, warnings


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def discover_gmts(run_root: Path) -> list[Path]:
    return sorted({path.resolve() for pattern in ("*.gmt", "*.gmt.gz") for path in run_root.rglob(pattern) if path.is_file()})


def _location(path: Path, run_root: Path | None) -> dict[str, str]:
    try:
        parts = path.relative_to(run_root).parts if run_root else path.parts
    except ValueError:
        parts = path.parts
    result = {"relative_path": str(path.relative_to(run_root)) if run_root and path.is_relative_to(run_root) else str(path), "partition": "", "model_id": "", "group": ""}
    if "genesets" in parts:
        index = parts.index("genesets")
        if len(parts) > index + 1:
            result["partition"] = parts[index + 1]
        if "models" in parts[index + 1:]:
            model_index = parts.index("models", index + 1)
            if len(parts) > model_index + 1:
                result["model_id"] = parts[model_index + 1]
        if "extractor" in parts[index + 1:]:
            extractor_index = parts.index("extractor", index + 1)
            if len(parts) > extractor_index + 1:
                result["group"] = parts[extractor_index + 1]
    return result


def _safe_div(left: int | float, right: int | float) -> float:
    return left / right if right else 0.0


def read_set_mapping(path: Path) -> dict[str, str]:
    """Read a one-to-one legacy-to-generated name mapping TSV."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {"legacy_set_name", "generated_set_name"}
        if not reader.fieldnames or not required <= set(reader.fieldnames):
            raise ValueError("set mapping must contain legacy_set_name and generated_set_name columns")
        mapping = {str(row["legacy_set_name"]).strip(): str(row["generated_set_name"]).strip() for row in reader}
    if not mapping or any(not left or not right for left, right in mapping.items()) or len(mapping) != len(set(mapping.values())):
        raise ValueError("set mapping must be non-empty, one-to-one, and contain no blank names")
    return mapping


def _summary(values: list[int]) -> dict[str, float | int]:
    if not values:
        return {"min": 0, "q1": 0.0, "median": 0.0, "mean": 0.0, "q3": 0.0, "max": 0}
    sorted_values = sorted(values)
    def quantile(p: float) -> float:
        position = (len(sorted_values) - 1) * p
        lower, upper = math.floor(position), math.ceil(position)
        return float(sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (position - lower))
    return {"min": min(values), "q1": quantile(.25), "median": quantile(.5), "mean": statistics.mean(values), "q3": quantile(.75), "max": max(values)}


def _inventory(path: Path, run_root: Path | None, gene_sets: dict[str, set[str]], warnings: list[str], min_size: int, max_size: int | None) -> tuple[dict[str, object], list[dict[str, object]]]:
    location = _location(path, run_root)
    sizes = [len(genes) for genes in gene_sets.values()]
    memberships = sum(sizes)
    record: dict[str, object] = {
        **location, "gmt_path": str(path), "sha256": _sha256(path), "gene_set_count": len(gene_sets),
        "membership_count": memberships, "unique_gene_count": len(set().union(*gene_sets.values())) if gene_sets else 0,
        "empty_gene_set_count": sum(not genes for genes in gene_sets.values()), "warning_count": len(warnings), **_summary(sizes),
    }
    flags: list[dict[str, object]] = []
    for name, genes in sorted(gene_sets.items()):
        reasons = []
        if not genes:
            reasons.append("empty")
        if len(genes) < min_size:
            reasons.append(f"below_min_size_{min_size}")
        if max_size is not None and len(genes) > max_size:
            reasons.append(f"above_max_size_{max_size}")
        if reasons:
            flags.append({"gmt_path": str(path), "gene_set_name": name, "gene_set_size": len(genes), "flag": ";".join(reasons)})
    return record, flags


def _comparison(reference: dict[str, set[str]], candidate: dict[str, set[str]], label: str, mapping: dict[str, str] | None = None) -> tuple[dict[str, object], list[dict[str, object]]]:
    pairs = mapping or {name: name for name in set(reference) & set(candidate)}
    unknown_legacy = sorted(set(pairs) - set(reference))
    unknown_generated = sorted(set(pairs.values()) - set(candidate))
    if unknown_legacy or unknown_generated:
        raise ValueError(f"mapping does not match comparison inputs: legacy={unknown_legacy[:3]}, generated={unknown_generated[:3]}")
    shared_names = sorted(pairs)
    details: list[dict[str, object]] = []
    for name in shared_names:
        generated_name = pairs[name]
        left, right = reference[name], candidate[generated_name]
        shared = left & right
        details.append({"comparison": label, "legacy_set_name": name, "generated_set_name": generated_name, "status": "matched", "legacy_size": len(left), "generated_size": len(right), "intersection": len(shared), "legacy_only": len(left - right), "generated_only": len(right - left), "precision": _safe_div(len(shared), len(right)), "recall": _safe_div(len(shared), len(left)), "jaccard": _safe_div(len(shared), len(left | right)), "exact_match": left == right})
    for name in sorted(set(reference) - set(pairs)):
        details.append({"comparison": label, "legacy_set_name": name, "generated_set_name": "", "status": "legacy_only", "legacy_size": len(reference[name]), "generated_size": 0, "intersection": 0, "legacy_only": len(reference[name]), "generated_only": 0, "precision": 0.0, "recall": 0.0, "jaccard": 0.0, "exact_match": False})
    for name in sorted(set(candidate) - set(pairs.values())):
        details.append({"comparison": label, "legacy_set_name": "", "generated_set_name": name, "status": "generated_only", "legacy_size": 0, "generated_size": len(candidate[name]), "intersection": 0, "legacy_only": 0, "generated_only": len(candidate[name]), "precision": 0.0, "recall": 0.0, "jaccard": 0.0, "exact_match": False})
    ref_pairs = {(name, gene) for name, genes in reference.items() for gene in genes}
    candidate_pairs = (
        {(legacy_name, gene) for legacy_name, generated_name in pairs.items() for gene in candidate[generated_name]}
        | {(name, gene) for name, genes in candidate.items() if name not in set(pairs.values()) for gene in genes}
    )
    overlap = ref_pairs & candidate_pairs
    jaccards = [float(row["jaccard"]) for row in details if row["status"] == "matched"]
    summary = {"comparison": label, "legacy_set_count": len(reference), "generated_set_count": len(candidate), "matched_set_count": len(shared_names), "legacy_only_set_count": len(set(reference) - set(candidate)), "generated_only_set_count": len(set(candidate) - set(reference)), "set_name_recall": _safe_div(len(shared_names), len(reference)), "set_name_precision": _safe_div(len(shared_names), len(candidate)), "legacy_membership_count": len(ref_pairs), "generated_membership_count": len(candidate_pairs), "membership_intersection": len(overlap), "membership_recall": _safe_div(len(overlap), len(ref_pairs)), "membership_precision": _safe_div(len(overlap), len(candidate_pairs)), "membership_jaccard": _safe_div(len(overlap), len(ref_pairs | candidate_pairs)), "median_set_jaccard": statistics.median(jaccards) if jaccards else 0.0, "mean_set_jaccard": statistics.mean(jaccards) if jaccards else 0.0, "exact_match_count": sum(bool(row["exact_match"]) for row in details), "exact_match_rate": _safe_div(sum(bool(row["exact_match"]) for row in details), len(shared_names))}
    return summary, details


def _write_tsv_gz(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _markdown_table(rows: list[dict[str, object]], fields: list[str], limit: int = 20) -> str:
    if not rows:
        return "No rows.\n"
    shown = rows[:limit]
    def display(value: object) -> str:
        return f"{value:.4f}" if isinstance(value, float) else str(value).replace("|", "\\|")
    return "| " + " | ".join(fields) + " |\n| " + " | ".join("---" for _ in fields) + " |\n" + "\n".join("| " + " | ".join(display(row.get(field, "")) for field in fields) + " |" for row in shown) + (f"\n\nShowing {len(shown)} of {len(rows)} rows.\n" if len(rows) > len(shown) else "\n")


def _plots(output_dir: Path, gene_set_sizes: list[int], comparisons: list[dict[str, object]]) -> list[str]:
    try:
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except ImportError:
        return ["Plots skipped: optional dependency matplotlib is unavailable."]
    messages: list[str] = []
    if gene_set_sizes:
        fig, axis = plt.subplots(figsize=(7, 4))
        axis.hist(gene_set_sizes, bins=min(40, max(1, len(gene_set_sizes))))
        axis.set(xlabel="Gene-set size", ylabel="Gene-set count", title="Generated gene-set size distribution")
        fig.tight_layout()
        for extension in ("png", "pdf"):
            fig.savefig(output_dir / f"set_size_distribution.{extension}", dpi=160)
        plt.close(fig)
    values = [float(row["median_set_jaccard"]) for row in comparisons]
    if values:
        fig, axis = plt.subplots(figsize=(7, 4))
        axis.bar(range(len(values)), values)
        axis.set(ylim=(0, 1), xlabel="Legacy comparison", ylabel="Median per-set Jaccard", title="Legacy GMT agreement")
        fig.tight_layout()
        for extension in ("png", "pdf"):
            fig.savefig(output_dir / f"legacy_jaccard_distribution.{extension}", dpi=160)
        plt.close(fig)
    return messages


def _write_pdf_report(output_dir: Path, summary: dict[str, object], inventories: list[dict[str, object]], flags: list[dict[str, object]], comparisons: list[dict[str, object]], warnings: list[str]) -> str | None:
    """Build the optional combined PDF without making it a runtime requirement."""
    try:
        from reportlab.lib import colors  # type: ignore[import-not-found]
        from reportlab.lib.pagesizes import letter  # type: ignore[import-not-found]
        from reportlab.lib.styles import getSampleStyleSheet  # type: ignore[import-not-found]
        from reportlab.lib.units import inch  # type: ignore[import-not-found]
        from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # type: ignore[import-not-found]
    except ImportError:
        return "Combined PDF skipped: optional dependency reportlab is unavailable."

    styles = getSampleStyleSheet()
    story: list[object] = [Paragraph("Post-run gene-set report", styles["Title"])]

    def add_table(title: str, rows: list[dict[str, object]], fields: list[str], limit: int = 20) -> None:
        story.extend([Spacer(1, 0.15 * inch), Paragraph(title, styles["Heading2"])])
        if not rows:
            story.append(Paragraph("No rows.", styles["BodyText"]))
            return
        data = [[Paragraph(escape(field.replace("_", " ")), styles["BodyText"]) for field in fields]]
        for row in rows[:limit]:
            data.append([Paragraph(escape((f"{row.get(field, ''):.4f}" if isinstance(row.get(field), float) else str(row.get(field, "")))[:100]), styles["BodyText"]) for field in fields])
        table = Table(data, repeatRows=1, colWidths=[7.0 * inch / len(fields)] * len(fields))
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTSIZE", (0, 0), (-1, -1), 7), ("LEADING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
        story.append(table)
        if len(rows) > limit:
            story.append(Paragraph(f"Showing {limit} of {len(rows)} rows; full data are in the TSV.GZ artifact.", styles["BodyText"]))

    add_table("Run summary", [summary], ["run_root", "generated_gmt_count", "legacy_gmt_count", "gene_set_count", "qc_flag_count", "warning_count"])
    add_table("Generated GMT inventory", inventories, ["relative_path", "partition", "model_id", "group", "gene_set_count", "membership_count", "unique_gene_count", "median"])
    add_table("Quality-control flags", flags, ["gene_set_name", "gene_set_size", "flag"])
    if comparisons:
        add_table("Legacy comparison", comparisons, ["comparison", "matched_set_count", "legacy_only_set_count", "generated_only_set_count", "membership_jaccard", "median_set_jaccard", "exact_match_rate"])
    for image_name in ("set_size_distribution.png", "legacy_jaccard_distribution.png"):
        image_path = output_dir / image_name
        if image_path.is_file():
            story.extend([PageBreak(), Paragraph(image_name.removesuffix(".png").replace("_", " ").title(), styles["Heading2"]), Spacer(1, 0.12 * inch), Image(str(image_path), width=6.5 * inch, height=6.5 * inch * 4 / 7)])
    if warnings:
        story.extend([PageBreak(), Paragraph("Warnings", styles["Heading2"])])
        story.extend(Paragraph(escape(f"• {warning}"), styles["BodyText"]) for warning in warnings)
    SimpleDocTemplate(str(output_dir / "report.pdf"), pagesize=letter, title="Post-run gene-set report", leftMargin=.75 * inch, rightMargin=.75 * inch, topMargin=.65 * inch, bottomMargin=.65 * inch).build(story)
    return None


def create_report(run_root: Path | None, output_dir: Path, *, gmts: Iterable[Path] | None = None, legacy_gmts: Iterable[Path] = (), mapping_path: Path | None = None, min_gene_set_size: int = 1, max_gene_set_size: int | None = None, command: str = "") -> dict[str, object]:
    """Write a complete report and return its machine-readable summary."""
    run_root, output_dir = run_root.resolve() if run_root else None, output_dir.resolve()
    if gmts is None and run_root is None:
        raise ValueError("pass --run-root for discovery, or at least one --gmt")
    gmt_paths = [path.resolve() for path in gmts] if gmts else discover_gmts(run_root)
    if not gmt_paths:
        raise ValueError(f"no GMT files found beneath {run_root}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"output directory must be empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=output_dir / "run.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", force=True)
    inventories: list[dict[str, object]] = []
    flags: list[dict[str, object]] = []
    gene_set_size_rows: list[dict[str, object]] = []
    all_warnings: list[str] = []
    parsed: dict[Path, dict[str, set[str]]] = {}
    for path in gmt_paths:
        gene_sets, warnings = read_gmt(path)
        parsed[path] = gene_sets
        inventory, new_flags = _inventory(path, run_root, gene_sets, warnings, min_gene_set_size, max_gene_set_size)
        inventories.append(inventory); flags.extend(new_flags); all_warnings.extend(warnings)
        gene_set_size_rows.extend({"gmt_path": str(path), "gene_set_name": name, "gene_set_size": len(genes)} for name, genes in sorted(gene_sets.items()))
        LOG.info("read %s: %d gene sets", path, len(gene_sets))
    _write_tsv_gz(output_dir / "gene_set_inventory.tsv.gz", inventories)
    _write_tsv_gz(output_dir / "qc_flags.tsv.gz", flags)
    _write_tsv_gz(output_dir / "gene_set_sizes.tsv.gz", gene_set_size_rows)
    legacy_paths = [path.resolve() for path in legacy_gmts]
    if legacy_paths and len(legacy_paths) != len(gmt_paths):
        raise ValueError("pass exactly one --legacy-gmt for every selected/generated GMT; use --gmt to select a matching subset")
    comparison_summaries: list[dict[str, object]] = []
    comparison_details: list[dict[str, object]] = []
    mapping = read_set_mapping(mapping_path) if mapping_path else None
    for legacy_path, generated_path in zip(legacy_paths, gmt_paths):
        legacy_sets, warnings = read_gmt(legacy_path)
        all_warnings.extend(warnings)
        label = f"{legacy_path.name} vs {generated_path.name}"
        summary, details = _comparison(legacy_sets, parsed[generated_path], label, mapping)
        summary.update({"legacy_gmt": str(legacy_path), "generated_gmt": str(generated_path)})
        comparison_summaries.append(summary); comparison_details.extend(details)
    if comparison_summaries:
        _write_tsv_gz(output_dir / "legacy_comparison_summary.tsv.gz", comparison_summaries)
        _write_tsv_gz(output_dir / "legacy_per_set_comparison.tsv.gz", comparison_details)
    if mapping:
        _write_tsv_gz(output_dir / "legacy_set_mapping_audit.tsv.gz", [{"legacy_set_name": legacy, "generated_set_name": generated, "status": "declared"} for legacy, generated in sorted(mapping.items())])
    plot_messages = _plots(output_dir, [int(row["gene_set_size"]) for row in gene_set_size_rows], comparison_summaries)
    summary = {"run_root": str(run_root) if run_root else "", "created_at_utc": datetime.now(timezone.utc).isoformat(), "generated_gmt_count": len(gmt_paths), "legacy_gmt_count": len(legacy_paths), "gene_set_count": sum(int(row["gene_set_count"]) for row in inventories), "qc_flag_count": len(flags), "warning_count": len(all_warnings), "plots": "available" if not plot_messages else "skipped", "pdf": "available", "command": command}
    pdf_message = _write_pdf_report(output_dir, summary, inventories, flags, comparison_summaries, all_warnings + plot_messages)
    summary["pdf"] = "available" if pdf_message is None else "skipped"
    _write_tsv_gz(output_dir / "summary.tsv.gz", [summary])
    (output_dir / "run_manifest.tsv.gz").write_bytes((output_dir / "gene_set_inventory.tsv.gz").read_bytes())
    (output_dir / "commands.md").write_text("# Command\n\n```bash\n" + (command or "command unavailable") + "\n```\n", encoding="utf-8")
    report = ["# Post-run gene-set report", "", "## Run summary", "", _markdown_table([summary], ["run_root", "generated_gmt_count", "legacy_gmt_count", "gene_set_count", "qc_flag_count", "warning_count", "plots", "pdf"]), "## Generated GMT inventory", "", _markdown_table(inventories, ["relative_path", "partition", "model_id", "group", "gene_set_count", "membership_count", "unique_gene_count", "median", "empty_gene_set_count", "warning_count"]), "## Quality-control flags", "", _markdown_table(flags, ["gmt_path", "gene_set_name", "gene_set_size", "flag"]), "## Legacy comparison"]
    if comparison_summaries:
        report.extend(["", _markdown_table(comparison_summaries, ["comparison", "matched_set_count", "legacy_only_set_count", "generated_only_set_count", "membership_jaccard", "median_set_jaccard", "exact_match_rate"]), "", "Per-set results are in `legacy_per_set_comparison.tsv.gz`."])
    else:
        report.extend(["", "No legacy GMTs were supplied; legacy comparison was not run."])
    if all_warnings or plot_messages or pdf_message:
        report.extend(["", "## Warnings", ""] + [f"- {message}" for message in all_warnings + plot_messages + ([pdf_message] if pdf_message else [])])
    (output_dir / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    (output_dir / "MANIFEST.md").write_text("# Report manifest\n\n- `report.md`: human-readable summary.\n- `report.pdf`: optional combined PDF when ReportLab is available.\n- `*.tsv.gz`: machine-readable tables.\n- `run.log`: execution log.\n- `commands.md`: invocation.\n- PNG/PDF files: optional plots when matplotlib is available.\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize completed GMT outputs without modifying them.")
    parser.add_argument("--run-root", type=Path, help="Run root for automatic GMT discovery; optional with --gmt.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--gmt", type=Path, action="append", help="Explicit generated GMT; repeatable. Defaults to discovery below --run-root.")
    parser.add_argument("--legacy-gmt", type=Path, action="append", default=[], help="Legacy GMT paired positionally with each generated GMT.")
    parser.add_argument("--name-mapping", type=Path, help="Optional TSV mapping legacy_set_name to generated_set_name.")
    parser.add_argument("--min-gene-set-size", type=int, default=1)
    parser.add_argument("--max-gene-set-size", type=int)
    args = parser.parse_args(argv)
    if args.min_gene_set_size < 0 or args.max_gene_set_size is not None and args.max_gene_set_size < args.min_gene_set_size:
        parser.error("invalid gene-set size limits")
    if args.run_root is None and not args.gmt:
        parser.error("pass --run-root for discovery, or at least one --gmt")
    try:
        summary = create_report(args.run_root, args.output_dir, gmts=args.gmt, legacy_gmts=args.legacy_gmt, mapping_path=args.name_mapping, min_gene_set_size=args.min_gene_set_size, max_gene_set_size=args.max_gene_set_size, command=" ".join(sys.argv))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
