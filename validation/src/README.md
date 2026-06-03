# validation/src

Scripts for validating and comparing GTEx gene sets extracted by different models. Validation is performed via the EAGGL/PIGEAN enrichment API, and results are written to TSV/text files under `data/gtex/output.tissue/`.

## Commands


### Start local EAGGL
```
cd /chembio/datasets/csdev/VD/code/molecular-data-provider/dcc_pigean_flask/python-flask-server
source venv/bin/activate.csh
nohup python app.py
```

### Run validation
```
cd /chembio/datasets/csdev/VD/code/CFDE/geneset-extractor-dev/validation/src
python run_validation.py
python harmonizome_validation.py
python concensus_validation.py
python validation_summary.py
python gene_set_comparison.py
```

## Scripts

### `run_validation.py`
Entry point for batch validation. Iterates over all tissues and models in `BASE_FOLDER`, parses each model's `genesets.gmt` file, submits gene sets to EAGGL, and appends enrichment results to per-tissue output files.

**Key functions:**
- `parse_gmt_file(gmt_file)` — Parses a GMT file and returns a list of `{gene_set, genes}` dicts.
- `get_gmt_file(folder_path)` — Resolves the GMT file path for a model folder (checks `extractor/` then `tissue_extractor/`).
- `run_validation(folder_path, out_file)` — Runs EAGGL validation for all gene sets in a model folder and appends results.
- `validate_tissue(tissue)` — Validates all models for a single tissue.

---

### `run_eaggl.py`
Low-level interface to the EAGGL/PIGEAN enrichment API. Also contains the random-gene simulation baseline.

**Key functions:**
- `run_eaggl(genes)` — Posts a gene list to the PIGEAN API and returns enriched gene sets.
- `save_results(out_f, gene_set_name, gene_set_size, genesets)` — Writes enrichment results as tab-delimited rows.
- `read_all_loc_genes()` — Reads all gene symbols from the LDSC gene location file.

---

### `validation_summary.py`
Loads and summarizes validation results across tissues and models. Produces ranked enrichment tables and plots.

**Key functions:**
- `parse_gtex_gene_set_name_suffix(tissue, gene_set_name)` — Parses tissue and condition metadata from a GTEx gene set name.
- `parse_drc_gene_set_name_suffix(gene_set_name)` — Parses metadata from a DRC gene set name.
- `key(...)` — Builds a canonical dict key for a gene set.
- `create_top_enriched_df(df)` — Builds a per-model top-enriched-gene-set summary DataFrame.
- `plot_gene_set_by_model(df, gene_set_name_suffix)` — Plots enrichment rank across models for a given gene set.

---

### `gene_set_comparison.py`
Compares gene sets across models for a given tissue, computing pairwise overlap and producing a comparison matrix.

**Key functions:**
- `load_genesets_for_tissue(tissue_folder)` — Loads all model gene sets for a tissue into a nested dict `{gene_set_name: {model: [genes]}}`.
- `load_genesets()` — Loads gene sets for all tissues.
- `gene_set_overlap(geneset1, geneset2)` — Returns counts of left-only, overlapping, and right-only genes between two sets.
- `compare_gene_sets_matrix(gene_set_name, genesets, base_gene_sets)` — Writes a pairwise overlap matrix TSV for a gene set.

---

### `harmonizome_validation.py`
Validates Harmonizome GTEx aging gene sets against the EAGGL API.

**Key functions:**
- `validate_gene_sets(gene_set_name, genes, out_f)` — Runs EAGGL on a single gene set and writes results.

---

### `result_counts.py`
Counts the number of gene sets produced by each model across all tissues and writes a summary table.

**Key functions:**
- `validate_tissue(tissue, out_f)` — Counts gene sets per model for a tissue and writes a row to the output file.

---

### `concensus_validation.py`
Builds consensus gene sets from multiple models by aggregating gene frequencies across sources.

**Key functions:**
- `load_genesets_for_tissue(tissue_folder)` — Loads all model gene sets for a tissue.
- `load_genesets()` — Loads gene sets for all tissues.
- `consensus_counts(gene_sets)` — Takes a collection of gene sets (`{source: [genes]}` or iterable of gene lists) and returns a list of `(gene, count)` tuples ordered from most to least frequent.
- `consensus_thresholds(gene_sets, thresholds=(0.90, 0.75, 0.50, 0.25))` — Returns a dict mapping threshold keys (e.g. `"AA90"`) to genes appearing in at least that fraction of the input gene sets, ordered by frequency. Requires at least 10 source sets.

## Output format

Validation result files (written by `run_validation.py` and `run_eaggl.py`) are tab-delimited with the following columns:

```
model  gene_set_name_suffix  gene_set_name  gene_set_size  rank  enriched_gene_sets_name  enriched_gene_set_size  enriched_gene_set_p_value
```

Output files are written to `data/gtex/output.tissue/`.
