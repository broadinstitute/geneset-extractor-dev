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
All scripts support CLI options to override defaults. Common options across most scripts:
- `-b/--base-folder`: Base folder for genesets (default: `runs/gtex_all_models/genesets`)
- `-o/--output-folder`: Output folder for results (default: `data/gtex/output.tissue`)
- `-m/--method`: Enrichment method: `eaggl` or `pigean` (default: `eaggl`)

Examples:
```
cd .../geneset-extractor-dev/validation/src

# Run validation for specific tissues with pigean
python run_validation.py -m pigean -t adipose_tissue -t whole_blood
python run_validation.py -b $BASE_FOLDER/runs/hubmap_all_models/genesets -o ../../data/hubmap/
python run_validation.py -b $BASE_FOLDER/runs/lincs_l1000_all_models/genesets -o ../../data/lincs

python validation_summary.py -b $BASE_FOLDER/runs/motrpac_all_models/genesets -o ../../data/motrpac



# Run consensus analysis for AC models only
python consensus_validation.py --prefix AC -m pigean

# Validate harmonizome source
python harmonizome_validation.py -s harmonizome -m pigean

# Count gene sets
python result_counts.py -b /path/to/genesets -o custom_counts.txt

# Compare gene sets
python gene_set_comparison.py --dm-comparison

# Summarize results
python validation_summary.py
```

## Scripts

### `run_validation.py`
Entry point for batch validation. Iterates over tissues and models, parses each model's `genesets.gmt` file, submits gene sets to PIGEAN API, and appends enrichment results to per-tissue output files.

**CLI options:**
- `-b/--base-folder`: Base folder for genesets (default: `runs/gtex_all_models/genesets`)
- `-o/--output-folder`: Output folder for results (default: `data/gtex/output.tissue`)
- `-t/--tissue`: Tissue to process (repeatable; if omitted, processes all)
- `-m/--method`: Enrichment method: `eaggl` (hypergeometric) or `pigean` (naive_priors)
- `--force-rewrite`: Overwrite existing output files

**Key functions:**
- `parse_gmt_file(gmt_file)` — Parses a GMT file and returns a list of `{gene_set, genes}` dicts.
- `get_gmt_file(folder_path)` — Resolves the GMT file path for a model folder (checks `extractor/` then `tissue_extractor/`).
- `run_validation(folder_path, out_file, model=None, method="eaggl")` — Runs validation for all gene sets in a model folder and appends results.
- `validate_tissue(tissue, base_folder, out_file_template, method="eaggl", force_rewrite=False)` — Validates all models for a single tissue.

---

### `run_eaggl.py`
Low-level interface to the EAGGL/PIGEAN enrichment API. Also contains the random-gene simulation baseline.

**Key functions:**
- `run_client(genes, enrichment_analysis="hypergeometric")` — Core API client. Posts a gene list to the PIGEAN API with the specified enrichment analysis method and returns enriched gene sets.
- `run_eaggl(genes)` — Calls `run_client` with `enrichment_analysis="hypergeometric"`.
- `run_pigean(genes)` — Calls `run_client` with `enrichment_analysis="naive_priors"`.
- `save_results(out_f, gene_set_name, gene_set_size, genesets)` — Writes enrichment results as tab-delimited rows.
- `read_all_loc_genes()` — Reads all gene symbols from the LDSC gene location file.

---

### `validation_summary.py`
Loads and summarizes validation results across tissues and models. Produces ranked enrichment tables and plots.

**CLI options:**
- `-b/--base-folder`: Base folder for genesets (default: `runs/gtex_all_models/genesets`)
- `-o/--output-folder`: Output folder for results (default: `data/gtex/output.tissue`)
- `-m/--method`: Enrichment method: `eaggl` or `pigean` (affects output file names)

**Key functions:**
- `parse_gtex_gene_set_name_suffix(tissue, gene_set_name)` — Parses tissue and condition metadata from a GTEx gene set name (handles aging and tissue-level formats).
- `parse_drc_gene_set_name_suffix(gene_set_name)` — Parses metadata from a DRC gene set name.
- `key(...)` — Builds a canonical dict key for a gene set.
- `create_top_enriched_df(df)` — Builds a per-model top-enriched-gene-set summary DataFrame.
- `plot_gene_set_by_model(df, gene_set_name_suffix)` — Plots enrichment rank across models for a given gene set.

---

### `gene_set_comparison.py`
Compares gene sets across models for a given tissue, computing pairwise overlap and producing a comparison matrix.

**CLI options:**
- `-b/--base-folder`: Base folder for genesets (default: `runs/gtex_all_models/genesets`)
- `-o/--output-folder`: Output folder for results (default: `data/gtex/output.tissue`)
- `--dm-comparison`: Enable data matrix comparison mode
- `--dm-vs-dm`: Enable data matrix vs data matrix comparison

**Key functions:**
- `load_genesets_for_tissue(tissue_folder)` — Loads all model gene sets for a tissue into a nested dict `{gene_set_name: {model: [genes]}}`.
- `load_genesets(base_folder=None)` — Loads gene sets for all tissues with optional base_folder override.
- `gene_set_overlap(geneset1, geneset2)` — Returns counts of left-only, overlapping, and right-only genes between two sets.
- `compare_gene_sets_matrix(gene_set_name, genesets, base_gene_sets)` — Writes a pairwise overlap matrix TSV for a gene set.

---

### `harmonizome_validation.py`
Validates external gene set sources (Harmonizome, data matrix) against the PIGEAN API.

**CLI options:**
- `-i/--input-folder`: Input folder for source files (default: `data/gtex/input`)
- `-o/--output-folder`: Output folder for results (default: `data/gtex/output.tissue`)
- `-s/--source`: Data source: `harmonizome` or `data_matrix` (default: `harmonizome`)
- `-m/--method`: Enrichment method: `eaggl` or `pigean` (default: `eaggl`)

**Key functions:**
- `validate_gene_sets(gene_set_name, genes, out_f, method="eaggl")` — Runs enrichment on a single gene set and writes results.

---

### `result_counts.py`
Counts the number of gene sets produced by each model across all tissues and writes a summary table.

**CLI options:**
- `-b/--base-folder`: Base folder for genesets (default: `runs/gtex_all_models/genesets`)
- `-o/--output-file`: Output file for counts (default: `data/gtex/output.tissue/model_counts.txt`)

**Key functions:**
- `validate_tissue(tissue, out_f)` — Counts gene sets per model for a tissue and writes a row to the output file.

---

### `consensus_validation.py`
Builds consensus gene sets from multiple models by aggregating gene frequencies across sources.

**CLI options:**
- `-b/--base-folder`: Base folder for genesets (default: `runs/gtex_all_models/genesets`)
- `-o/--output-folder`: Output folder for results (default: `data/gtex/output.tissue`)
- `-m/--method`: Enrichment method: `eaggl` or `pigean` (default: `eaggl`)
- `--min-genes`: Minimum number of genes to validate (default: 5)
- `--prefix`: Model prefix filter (e.g., `AB` or `AC` to validate only those models)

**Key functions:**
- `load_genesets_for_tissue(tissue_folder)` — Loads all model gene sets for a tissue.
- `load_genesets(base_folder=None)` — Loads gene sets for all tissues.
- `consensus_counts(gene_sets)` — Takes a collection of gene sets (`{source: [genes]}` or iterable of gene lists) and returns a list of `(gene, count)` tuples ordered from most to least frequent.
- `consensus_thresholds(gene_sets, thresholds=(0.90, 0.75, 0.50, 0.25))` — Returns a dict mapping threshold keys (e.g. `"AA90"`) to genes appearing in at least that fraction of the input gene sets, ordered by frequency. Requires at least 10 source sets.
- `analyze_consensus(gene_set_name, gene_set, out_f, method="eaggl")` — Analyzes consensus with specified enrichment method.

## Output format

Validation result files (written by `run_validation.py` and enrichment scripts) are tab-delimited with the following columns:

```
model  gene_set_name_suffix  gene_set_name  gene_set_size  rank  enriched_gene_sets_name  enriched_gene_set_size  enriched_gene_set_p_value
```

Output files are written based on method and source:
- **EAGGL validation**: `data/gtex/output.tissue/{tissue}_validation_results.txt`
- **PIGEAN validation**: `data/gtex/output.tissue.pigean/{tissue}_validation_results_pigean.txt`
- **Harmonizome**: `{output-folder}/harmonizome_validation.txt` or `harmonizome_pigean_validation.txt`
- **Data Matrix**: `{output-folder}/data_matrix_validation.txt` or `data_matrix_pigean_validation.txt`

## GMT file format

GMT (Gene Matrix Transposed) files are tab-delimited with the format:
```
name  [empty_description]  gene1  gene2  gene3  ...
```

Gene sets from the new file structure (`runs/gtex_all_models/genesets`) use standard GTEx naming conventions:
- **Aging model**: `GTEx_aging_Adipose_Tissue_20-29_50-59_up` → tissue, age1, age2, direction
- **Tissue-level model**: `GTEx_Adrenal_Gland_up` → tissue, direction

When validated, gene set names are prefixed with the model name: `{model}__{original_name}`
