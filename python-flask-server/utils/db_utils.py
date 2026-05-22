from __future__ import annotations

import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parents[1] / "data" / "genseco_v0.sqlite"


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}


def get_gene_set_data(gene_set_id: int) -> dict | None:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    try:
        gene_set_row = connection.execute(
            """
            SELECT
                gs.gene_set_id,
                gs.standard_name,
                gs.collection_name,
                gs.tags,
                gs.license_code,
                p.provenance_graph,
                p.geneset_metadata
            FROM gene_set AS gs
            LEFT JOIN provenance AS p
                ON p.gene_set_id = gs.gene_set_id
            WHERE gs.gene_set_id = ?
            """,
            (gene_set_id,),
        ).fetchone()

        if gene_set_row is None:
            return None

        gene_symbol_rows = connection.execute(
            """
            SELECT
                gsgs.gene_symbol_id,
                gsym.symbol,
                gsym.NCBI_id,
                gsym.namespace_id
            FROM gene_set_gene_symbol AS gsgs
            JOIN gene_symbol AS gsym
                ON gsym.gene_symbol_id = gsgs.gene_symbol_id
            WHERE gsgs.gene_set_id = ?
            ORDER BY gsgs.gene_symbol_id
            """,
            (gene_set_id,),
        ).fetchall()

        gene_set_data = _row_to_dict(gene_set_row)
        gene_set_data["gene_symbols"] = [_row_to_dict(row) for row in gene_symbol_rows]
        return gene_set_data
    finally:
        connection.close()
