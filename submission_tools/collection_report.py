#!/usr/bin/env python3
"""Create a portfolio report from multiple completed library run roots."""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from .postrun_report import _markdown_table, _write_tsv_gz, create_report


LOG = logging.getLogger(__name__)
REQUIRED_COLUMNS = {"library_id", "run_root"}


def _safe_library_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
        raise ValueError(f"unsafe library_id {value!r}; use letters, digits, dot, underscore, or hyphen")
    return value


def _resolve(base: Path, value: str) -> Path | None:
    value = value.strip()
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def read_collection_manifest(path: Path) -> list[dict[str, Path | str | None]]:
    """Read a reproducible TSV manifest with paths relative to itself."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames or not REQUIRED_COLUMNS <= set(reader.fieldnames):
            raise ValueError("collection manifest must contain library_id and run_root columns")
        rows: list[dict[str, Path | str | None]] = []
        seen: set[str] = set()
        for line_number, row in enumerate(reader, 2):
            library_id = _safe_library_id(str(row["library_id"] or "").strip())
            if library_id in seen:
                raise ValueError(f"duplicate library_id {library_id!r} at {path}:{line_number}")
            run_root = _resolve(path.parent, str(row["run_root"] or ""))
            if run_root is None:
                raise ValueError(f"blank run_root at {path}:{line_number}")
            rows.append({"library_id": library_id, "run_root": run_root, "generated_gmt": _resolve(path.parent, str(row.get("generated_gmt", "") or "")), "legacy_gmt": _resolve(path.parent, str(row.get("legacy_gmt", "") or "")), "name_mapping": _resolve(path.parent, str(row.get("name_mapping", "") or ""))})
            seen.add(library_id)
    if not rows:
        raise ValueError("collection manifest contains no libraries")
    return rows


def _read_first_tsv_gz(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return next(csv.DictReader(handle, delimiter="\t"), {})


def _write_overview_plot(output_dir: Path, rows: list[dict[str, object]]) -> str | None:
    try:
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except ImportError:
        return "Collection plot skipped: optional dependency matplotlib is unavailable."
    labels = [str(row["library_id"]) for row in rows]
    values = [int(row["gene_set_count"]) for row in rows]
    fig, axis = plt.subplots(figsize=(max(7, len(rows) * 1.1), 4.5))
    axis.bar(labels, values)
    axis.set(xlabel="Library", ylabel="Gene-set count", title="Generated gene sets by library")
    axis.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    for extension in ("png", "pdf"):
        fig.savefig(output_dir / f"cross_library_overview.{extension}", dpi=160)
    plt.close(fig)
    return None


def _write_collection_pdf(output_dir: Path, summary: dict[str, object], rows: list[dict[str, object]], warnings: list[str]) -> str | None:
    try:
        from reportlab.lib import colors  # type: ignore[import-not-found]
        from reportlab.lib.pagesizes import letter  # type: ignore[import-not-found]
        from reportlab.lib.styles import getSampleStyleSheet  # type: ignore[import-not-found]
        from reportlab.lib.units import inch  # type: ignore[import-not-found]
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # type: ignore[import-not-found]
    except ImportError:
        return "Collection PDF skipped: optional dependency reportlab is unavailable."
    styles = getSampleStyleSheet()
    fields = ["library_id", "gene_set_count", "generated_gmt_count", "qc_flag_count", "legacy_comparison", "membership_jaccard", "median_set_jaccard"]
    data = [[Paragraph(escape(field.replace("_", " ")), styles["BodyText"]) for field in fields]]
    for row in rows:
        data.append([Paragraph(escape((f"{row.get(field, ''):.4f}" if isinstance(row.get(field), float) else str(row.get(field, "")))[:80]), styles["BodyText"]) for field in fields])
    table = Table(data, repeatRows=1, colWidths=[7.0 * inch / len(fields)] * len(fields))
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("GRID", (0, 0), (-1, -1), .25, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTSIZE", (0, 0), (-1, -1), 7), ("LEADING", (0, 0), (-1, -1), 8)]))
    story: list[object] = [Paragraph("Gene-set library collection report", styles["Title"]), Spacer(1, .12 * inch), Paragraph(f"Libraries: {summary['library_count']}; total gene sets: {summary['gene_set_count']}", styles["BodyText"]), Spacer(1, .15 * inch), Paragraph("Library overview", styles["Heading2"]), table]
    image_path = output_dir / "cross_library_overview.png"
    if image_path.is_file():
        story.extend([Spacer(1, .18 * inch), Image(str(image_path), width=6.5 * inch, height=6.5 * inch * 4.5 / 7)])
    if warnings:
        story.extend([Spacer(1, .18 * inch), Paragraph("Warnings", styles["Heading2"])])
        story.extend(Paragraph(escape(f"• {warning}"), styles["BodyText"]) for warning in warnings)
    SimpleDocTemplate(str(output_dir / "report.pdf"), pagesize=letter, title="Gene-set library collection report", leftMargin=.75 * inch, rightMargin=.75 * inch, topMargin=.65 * inch, bottomMargin=.65 * inch).build(story)
    return None


def create_collection_report(manifest_path: Path, output_dir: Path, *, command: str = "") -> dict[str, object]:
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"output directory must be empty: {output_dir}")
    entries = read_collection_manifest(manifest_path.resolve())
    output_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=output_dir / "run.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", force=True)
    rows: list[dict[str, object]] = []
    warnings: list[str] = []
    for entry in entries:
        library_id, run_root = str(entry["library_id"]), Path(entry["run_root"])
        if not run_root.is_dir():
            raise ValueError(f"run_root for {library_id} is not a directory: {run_root}")
        library_output = output_dir / "libraries" / library_id
        generated, legacy = entry["generated_gmt"], entry["legacy_gmt"]
        mapping = entry["name_mapping"]
        result = create_report(run_root, library_output, gmts=[Path(generated)] if generated else None, legacy_gmts=[Path(legacy)] if legacy else [], mapping_path=Path(mapping) if mapping else None, command=command)
        comparison = _read_first_tsv_gz(library_output / "legacy_comparison_summary.tsv.gz")
        rows.append({"library_id": library_id, "run_root": str(run_root), "report_path": str(library_output / "report.md"), "generated_gmt_count": int(result["generated_gmt_count"]), "gene_set_count": int(result["gene_set_count"]), "qc_flag_count": int(result["qc_flag_count"]), "warning_count": int(result["warning_count"]), "legacy_comparison": "run" if comparison else "not_run", "membership_jaccard": float(comparison["membership_jaccard"]) if comparison else "", "median_set_jaccard": float(comparison["median_set_jaccard"]) if comparison else ""})
        LOG.info("reported %s", library_id)
    plot_message = _write_overview_plot(output_dir, rows)
    summary: dict[str, object] = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "library_count": len(rows), "generated_gmt_count": sum(int(row["generated_gmt_count"]) for row in rows), "gene_set_count": sum(int(row["gene_set_count"]) for row in rows), "qc_flag_count": sum(int(row["qc_flag_count"]) for row in rows), "legacy_comparison_count": sum(row["legacy_comparison"] == "run" for row in rows), "plots": "available" if plot_message is None else "skipped", "pdf": "available", "command": command}
    pdf_message = _write_collection_pdf(output_dir, summary, rows, ([plot_message] if plot_message else []))
    summary["pdf"] = "available" if pdf_message is None else "skipped"
    _write_tsv_gz(output_dir / "library_summary.tsv.gz", rows)
    _write_tsv_gz(output_dir / "summary.tsv.gz", [summary])
    markdown = ["# Gene-set library collection report", "", "## Overall summary", "", _markdown_table([summary], ["library_count", "generated_gmt_count", "gene_set_count", "qc_flag_count", "legacy_comparison_count", "plots", "pdf"]), "## Library summary", "", _markdown_table(rows, ["library_id", "generated_gmt_count", "gene_set_count", "qc_flag_count", "legacy_comparison", "membership_jaccard", "median_set_jaccard", "report_path"])]
    if plot_message or pdf_message:
        markdown.extend(["", "## Warnings", ""] + [f"- {message}" for message in (message for message in (plot_message, pdf_message) if message)])
    (output_dir / "report.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    (output_dir / "commands.md").write_text("# Command\n\n```bash\n" + (command or "command unavailable") + "\n```\n", encoding="utf-8")
    (output_dir / "MANIFEST.md").write_text("# Collection report manifest\n\n- `report.md`: aggregate human-readable report.\n- `report.pdf`: optional combined PDF when ReportLab is available.\n- `library_summary.tsv.gz`: aggregate library table.\n- `libraries/<library_id>/`: individual library report artifacts.\n- `cross_library_overview.{png,pdf}`: optional overview plot when matplotlib is available.\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create reports for a collection of completed gene-set libraries.")
    parser.add_argument("--manifest", type=Path, required=True, help="TSV with library_id and run_root; optional generated_gmt, legacy_gmt, and name_mapping columns.")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        summary = create_collection_report(args.manifest, args.output_dir, command=" ".join(sys.argv))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
