#!/usr/bin/env Rscript
#
# Differential Expression Analysis using limma-voom
# GTEx Dataset Analysis
# 
# This script performs differential expression analysis on GTEx RNA-seq data
# using the limma-voom pipeline, which is ideal for RNA-seq count data.
#

# Set CRAN mirror and library path
options(repos = c(CRAN = "https://cloud.r-project.org/"))
user_lib <- path.expand("~/R/library")
if (!dir.exists(user_lib)) {
  dir.create(user_lib, recursive = TRUE)
}
.libPaths(c(user_lib, .libPaths()))

# Load required libraries
library(limma)
library(edgeR)
library(tidyverse)

cat("Loading required packages...\n")

# ============================================================================
# USER PARAMETERS
# ============================================================================

# Specify comparison in format: "<tissue> <age_group1> vs <age_group2>"
# Examples:
#   "Thyroid 20-29 vs 40-49"
#   "Heart 30-39 vs 60-69"
#   "Blood 50-59 vs 70-79"
# Leave as NULL to compare all tissues broadly by default
# NOTE: This can be overridden by batch_de_analysis.R when running in batch mode
if (!exists("comparison_param")) {
  comparison_param <- "Thyroid 20-29 vs 40-49"
}

# Alternative: compare by sex instead of age
# Set to one of: "SEX", "AGE", "TISSUE", "TISSUE_AGE" or NULL
if (!exists("comparison_type")) {
  comparison_type <- "TISSUE_AGE"  # Use tissue + age comparison from comparison_param
}

# ============================================================================
# 1. DATA LOADING
# ============================================================================

cat("Step 1: Loading metadata and gene annotations...\n")

# Define file paths
gct_file <- "inputs/GTEx_Analysis_2017-06-05_v8_RNASeQCv1.1.9_gene_reads.gct"
metadata_file <- "inputs/metadata.tsv"
hgnc_file <- "inputs/hgnc.txt"

# Load gene symbol mapping from HGNC
cat("  Loading HGNC gene symbol mapping...\n")
if (!file.exists(hgnc_file)) {
  cat("  WARNING: hgnc.txt not found, gene symbols will be unavailable\n")
  gene_symbol_map <- NULL
} else {
  # Use fill=TRUE to handle rows with different numbers of columns
  hgnc_data <- read.table(hgnc_file, sep = "\t", header = TRUE, stringsAsFactors = FALSE, 
                          fill = TRUE, quote = "", comment.char = "")
  # Create mapping from Ensembl gene ID to symbol
  if ("ensembl_gene_id" %in% colnames(hgnc_data) && "symbol" %in% colnames(hgnc_data)) {
    gene_symbol_map <- setNames(hgnc_data$symbol, hgnc_data$ensembl_gene_id)
    # Remove NA entries
    gene_symbol_map <- gene_symbol_map[!is.na(names(gene_symbol_map)) & names(gene_symbol_map) != ""]
    cat(sprintf("  Loaded %d gene symbol mappings\n", length(gene_symbol_map)))
  } else {
    cat("  WARNING: Could not find ensembl_gene_id or symbol columns in HGNC file\n")
    gene_symbol_map <- NULL
  }
}

# Load clean metadata file
if (!file.exists(metadata_file)) {
  cat("ERROR: metadata.tsv not found!\n")
  cat("Please run 'Rscript prepare_metadata.R' first to generate it.\n")
  quit(status = 1)
}

metadata <- read.table(metadata_file, sep = "\t", header = TRUE, stringsAsFactors = FALSE)
rownames(metadata) <- metadata$sample_id

cat(sprintf("  - Metadata: %d samples\n", nrow(metadata)))
cat(sprintf("  - Columns: %s\n", paste(colnames(metadata), collapse = ", ")))

# ============================================================================
# 2. DATA INTEGRATION AND IDENTIFY TARGET SAMPLES
# ============================================================================

cat("Step 2: Identifying target samples...\n")

# Parse comparison parameter to identify target samples
target_samples <- NULL

if (!is.null(comparison_param) && comparison_param != "") {
  cat(sprintf("  - Parsing comparison: %s\n", comparison_param))
  
  # Parse format: "Tissue Age1 vs Age2"
  parts <- strsplit(comparison_param, " vs ")[[1]]
  if (length(parts) == 2) {
    group1_spec <- trimws(parts[1])
    group2_spec <- trimws(parts[2])
    
    # Split first part into tissue and age group
    group1_parts <- strsplit(group1_spec, " ")[[1]]
    group2_parts <- strsplit(group2_spec, " ")[[1]]
    
    if (length(group1_parts) >= 2 && length(group2_parts) >= 1) {
      tissue_name <- paste(group1_parts[-length(group1_parts)], collapse = " ")
      age_group1 <- group1_parts[length(group1_parts)]
      age_group2 <- group2_parts[length(group2_parts)]
      
      cat(sprintf("  - Tissue: %s\n", tissue_name))
      cat(sprintf("  - Age groups: %s vs %s\n", age_group1, age_group2))
      
      # Show available tissues and ages
      cat("  - Available tissues:\n")
      tissue_counts <- table(metadata$tissue)
      print(tissue_counts)
      
      cat("  - Available age groups:\n")
      age_counts <- table(metadata$age)
      print(age_counts)
      
      # Identify target samples
      idx_tissue <- metadata$tissue == tissue_name
      idx_age1 <- metadata$age == age_group1
      idx_age2 <- metadata$age == age_group2
      
      target_idx <- (idx_tissue & idx_age1) | (idx_tissue & idx_age2)
      target_samples <- metadata$sample_id[target_idx]
      
      cat(sprintf("  - Samples with %s and age %s: %d\n", tissue_name, age_group1, sum(idx_tissue & idx_age1)))
      cat(sprintf("  - Samples with %s and age %s: %d\n", tissue_name, age_group2, sum(idx_tissue & idx_age2)))
      cat(sprintf("  - Total target samples: %d\n", length(target_samples)))
      
      # Check for minimum sample requirements
      n_age1 <- sum(idx_tissue & idx_age1)
      n_age2 <- sum(idx_tissue & idx_age2)
      min_samples_per_group <- 2
      
      if (n_age1 < min_samples_per_group || n_age2 < min_samples_per_group) {
        cat(sprintf("  ⚠ WARNING: Insufficient samples for comparison!\n"))
        cat(sprintf("    %s age %s: %d samples\n", tissue_name, age_group1, n_age1))
        cat(sprintf("    %s age %s: %d samples\n", tissue_name, age_group2, n_age2))
        cat(sprintf("    Minimum required: %d per group. Skipping this comparison.\n", min_samples_per_group))
        cat("\n")
        stop("SKIP_COMPARISON: Insufficient samples for groups")  # This will be caught by batch script
      }
    }
  }
} else {
  # No specific comparison, use all samples
  target_samples <- metadata$sample_id
  cat(sprintf("  - No comparison specified, using all %d samples\n", length(target_samples)))
}

# Filter metadata to target samples
sample_metadata <- metadata[metadata$sample_id %in% target_samples, ]
rownames(sample_metadata) <- sample_metadata$sample_id

cat(sprintf("  - Sample metadata dimensions: %d samples\n", nrow(sample_metadata)))

# ============================================================================
# CREATE OUTPUT DIRECTORY BASED ON COMPARISON
# ============================================================================

# Create folder name from comparison parameter
if (!is.null(comparison_param) && comparison_param != "") {
  # Replace spaces and "vs" with underscores for folder name
  output_dir <- file.path("outputs", comparison_param %>%
    gsub(" vs ", "_vs_", .) %>%
    gsub(" ", "_", .))
} else {
  output_dir <- file.path("outputs", "results_all_samples")
}

# Create the output directory if it doesn't exist
if (!dir.exists(output_dir)) {
  dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)
  cat(sprintf("\nCreated output directory: %s\n", output_dir))
} else {
  cat(sprintf("\nUsing existing output directory: %s\n", output_dir))
}

# ============================================================================
# 3. LOAD EXPRESSION DATA (MEMORY EFFICIENT)
# ============================================================================

cat("Step 3: Loading expression data for target samples only...\n")

# Function to read GCT file with selective column loading
read_gct_selective <- function(file, target_cols) {
  cat("  Reading GCT header to identify columns...\n")
  
  # Read first three lines: version, dimensions, and column headers
  header_lines <- readLines(file, n = 3)
  dims <- as.numeric(strsplit(header_lines[2], "\t")[[1]])
  n_genes <- dims[1]
  n_samples <- dims[2]
  
  # Parse column names from header (skip gene_id and description)
  all_cols <- strsplit(header_lines[3], "\t")[[1]]
  
  cat(sprintf("  GCT file: %d genes x %d total samples\n", n_genes, n_samples))
  cat(sprintf("  Total columns in header: %d\n", length(all_cols)))
  cat(sprintf("  Target samples to find: %d\n", length(target_cols)))
  
  # Show first few GCT column names
  cat("  First 5 GCT column names:\n")
  print(head(all_cols, 5))
  
  cat("  First 5 target column names:\n")
  print(head(target_cols, 5))
  
  # Find which positions match (among sample columns, not including gene_id/description)
  sample_cols <- all_cols[-c(1, 2)]
  matching_positions <- which(sample_cols %in% target_cols)
  
  cat(sprintf("  Matching positions found: %d\n", length(matching_positions)))
  
  if (length(matching_positions) > 0) {
    cat("  First few matching positions:\n")
    print(head(matching_positions, 5))
  }
  
  # Create colClasses: "NULL" to skip, "character"/"numeric" to keep
  colClasses <- rep("NULL", length(all_cols))
  colClasses[1] <- "character"  # gene_id
  colClasses[2] <- "character"  # description
  
  # Set numeric for matching columns
  # matching_positions are relative to sample_cols, so add 2 to get absolute position
  if (length(matching_positions) > 0) {
    colClasses[matching_positions + 2] <- "numeric"
  }
  
  cat(sprintf("  Columns to load as numeric: %d\n", sum(colClasses == "numeric")))
  
  # Read only target columns
  data <- read.table(file, sep = "\t", skip = 2, header = TRUE, 
                     row.names = 1, stringsAsFactors = FALSE,
                     colClasses = colClasses, nrows = n_genes,
                     check.names = FALSE)
  
  # Remove description column if present
  if ("Description" %in% colnames(data)) {
    data <- data[, -1, drop = FALSE]
  }
  
  cat(sprintf("  Loaded: %d genes x %d samples\n", nrow(data), ncol(data)))
  
  return(data)
}

# Load expression data for target samples only
# The GCT file column names use dashes (same as metadata), no conversion needed
expr_data <- read_gct_selective(gct_file, target_samples)

# Ensure columns match target samples exactly
matching_samples <- intersect(target_samples, colnames(expr_data))
cat(sprintf("  - Matched samples: %d\n", length(matching_samples)))

if (length(matching_samples) > 0) {
  expr_data <- expr_data[, matching_samples]
  # Filter metadata to matched samples
  sample_metadata <- sample_metadata[matching_samples, ]
} else {
  cat("  ERROR: No column name matches found!\n")
  quit(status = 1)
}

cat(sprintf("  - Final expression data: %d genes x %d samples\n", 
            nrow(expr_data), ncol(expr_data)))

# Remove genes with very low counts (fewer than 1 count per million in at least X samples)
cpm_threshold <- 1
n_samples_threshold <- 3  # genes must have >= cpm_threshold in at least this many samples

counts <- expr_data
keep <- rowSums(cpm(counts) >= cpm_threshold) >= n_samples_threshold
expr_data_filtered <- expr_data[keep, ]

cat(sprintf("  - Genes retained after filtering: %d (from %d, %.1f%% retained)\n", 
            nrow(expr_data_filtered), nrow(expr_data), 
            100 * nrow(expr_data_filtered) / nrow(expr_data)))

# ============================================================================
# 5. CREATE DESIGN MATRIX
# ============================================================================

cat("Step 5: Creating design matrix...\n")

# Create group factor based on age if comparison was specified
if (!is.null(comparison_param) && comparison_param != "") {
  # Parse format: "Tissue Age1 vs Age2"
  parts <- strsplit(comparison_param, " vs ")[[1]]
  if (length(parts) == 2) {
    group1_spec <- trimws(parts[1])
    group2_spec <- trimws(parts[2])
    
    group1_parts <- strsplit(group1_spec, " ")[[1]]
    group2_parts <- strsplit(group2_spec, " ")[[1]]
    
    if (length(group1_parts) >= 2 && length(group2_parts) >= 1) {
      age_group1 <- group1_parts[length(group1_parts)]
      age_group2 <- group2_parts[length(group2_parts)]
      
      # Create group factor based on age
      sample_metadata$group <- ifelse(sample_metadata$age == age_group1, 
                                      sprintf("Age_%s", gsub("-", "_", age_group1)),
                                      sprintf("Age_%s", gsub("-", "_", age_group2)))
      sample_metadata$group <- as.factor(sample_metadata$group)
    } else {
      sample_metadata$group <- as.factor(sample_metadata$tissue)
    }
  } else {
    sample_metadata$group <- as.factor(sample_metadata$tissue)
  }
} else {
  # Default: use tissue as grouping
  sample_metadata$group <- as.factor(sample_metadata$tissue)
}

cat(sprintf("  - Groups for comparison:\n"))
print(table(sample_metadata$group))

# Create the design matrix
design <- model.matrix(~ 0 + group, data = sample_metadata)
colnames(design) <- gsub("^group", "", colnames(design))

cat(sprintf("  - Design matrix dimensions: %d samples x %d coefficients\n", 
            nrow(design), ncol(design)))

# ============================================================================
# 6. NORMALIZATION WITH VOOM
# ============================================================================

cat("Step 6: Normalizing with voom...\n")

# Create DGEList object
dge <- DGEList(counts = expr_data_filtered)

# Normalize for library size
dge <- calcNormFactors(dge, method = "TMM")

# Apply voom transformation (converts counts to log2-CPM with observation weights)
# This accounts for the mean-variance trend in RNA-seq data
v <- voom(dge, design, plot = FALSE)

cat(sprintf("  - Voom transformation completed\n"))
cat(sprintf("  - Mean-variance weights calculated for %d genes\n", nrow(v)))

# Optional: Generate voom diagnostic plots
pdf(file.path(output_dir, "voom_diagnostic_plots.pdf"), width = 10, height = 8)
plotMDS(v, main = "MDS Plot: Sample Distances")
dev.off()
cat(sprintf("  - Diagnostic plots saved to: %s\n", file.path(output_dir, "voom_diagnostic_plots.pdf")))

# ============================================================================
# 7. FIT LINEAR MODEL AND COMPUTE CONTRASTS
# ============================================================================

cat("Step 7: Fitting linear model...\n")

# Fit the linear model
fit <- lmFit(v, design)

# Define contrast matrix (compare first and second group)
# Modify this based on your biological questions
if (ncol(design) >= 2) {
  contrast_matrix <- makeContrasts(
    contrasts = paste(colnames(design)[2], "-", colnames(design)[1], sep = ""),
    levels = design
  )
} else {
  cat("  - Only one group detected, skipping contrasts\n")
  contrast_matrix <- NULL
}

if (!is.null(contrast_matrix)) {
  # Apply contrasts
  fit2 <- contrasts.fit(fit, contrast_matrix)
  
  # Apply empirical Bayes smoothing
  fit2 <- eBayes(fit2)
  
  cat(sprintf("  - Linear model fitted\n"))
  cat(sprintf("  - Empirical Bayes statistics computed\n"))
  
  # ============================================================================
  # 9. EXTRACT AND VISUALIZE RESULTS
  # ============================================================================
  
  cat("Step 9: Extracting results...\n")
  
  # Get top genes
  results <- topTable(fit2, adjust.method = "BH", number = Inf)
  
  # Add gene information to results
  results$gene_id <- rownames(results)
  
  # Add gene symbols using HGNC mapping
  if (!is.null(gene_symbol_map)) {
    # Strip version numbers from gene IDs (e.g., ENSG00000116106.11 -> ENSG00000116106)
    gene_ids_unversioned <- gsub("\\.\\d+$", "", rownames(results))
    results$gene_symbol <- gene_symbol_map[gene_ids_unversioned]
    # For genes without symbols, use the unversioned gene ID
    results$gene_symbol[is.na(results$gene_symbol)] <- gene_ids_unversioned[is.na(results$gene_symbol)]
  } else {
    # Strip version numbers for cleaner display
    results$gene_symbol <- gsub("\\.\\d+$", "", rownames(results))
  }
  
  # Reorder columns: symbol, id, then statistics
  results <- results %>% 
    select(gene_symbol, gene_id, logFC, AveExpr, t, P.Value, adj.P.Val)
  
  # Count significant genes
  sig_genes <- results[results$adj.P.Val < 0.05, ]
  sig_genes_fc <- results[results$adj.P.Val < 0.05 & abs(results$logFC) > 1, ]
  
  # Sort all results by logFC (descending: upregulated first, downregulated last)
  results <- results[order(results$logFC, decreasing = TRUE), ]
  sig_genes <- sig_genes[order(sig_genes$logFC, decreasing = TRUE), ]
  sig_genes_fc <- sig_genes_fc[order(sig_genes_fc$logFC, decreasing = TRUE), ]
  
  cat(sprintf("  - Significantly DE genes (FDR < 0.05): %d\n", nrow(sig_genes)))
  cat(sprintf("  - Significantly DE genes (FDR < 0.05, |logFC| > 1): %d\n", nrow(sig_genes_fc)))
  
  # Display top genes
  cat("\nTop 10 differentially expressed genes:\n")
  print(head(results[, c("gene_symbol", "gene_id", "logFC", "AveExpr", "P.Value", "adj.P.Val")], 10))
  
  # ============================================================================
  # 10. GENERATE VISUALIZATIONS
  # ============================================================================
  
  cat("Step 10: Generating visualizations...\n")
  
  # Volcano plot
  pdf(file.path(output_dir, "volcano_plot.pdf"), width = 10, height = 8)
  with(results, plot(logFC, -log10(adj.P.Val), 
                     main = "Volcano Plot", 
                     xlab = "log2 Fold Change", 
                     ylab = "-log10(Adjusted P-value)",
                     pch = 16, cex = 0.5))
  # Highlight significant genes
  with(subset(results, adj.P.Val < 0.05),
       points(logFC, -log10(adj.P.Val), 
              col = "red", pch = 16, cex = 0.6))
  # Add threshold lines
  abline(h = -log10(0.05), col = "blue", lty = 2)
  abline(v = c(-1, 1), col = "green", lty = 2)
  dev.off()
  cat(sprintf("  - Volcano plot saved to: %s\n", file.path(output_dir, "volcano_plot.pdf")))
  
  # MA plot (M vs A plot)
  pdf(file.path(output_dir, "ma_plot.pdf"), width = 10, height = 8)
  plotMA(fit2, main = "MA Plot")
  dev.off()
  cat(sprintf("  - MA plot saved to: %s\n", file.path(output_dir, "ma_plot.pdf")))
  
  # ============================================================================
  # 11. SAVE RESULTS
  # ============================================================================
  
  cat("Step 11: Saving results...\n")
  
  # Save all results as TSV
  write.table(results, file.path(output_dir, "de_genes_all.tsv"), sep = "\t", row.names = FALSE, quote = FALSE)
  cat(sprintf("  - All results saved to: %s\n", file.path(output_dir, "de_genes_all.tsv")))
  
  # Save significant genes only as TSV
  write.table(sig_genes, file.path(output_dir, "de_genes_significant.tsv"), sep = "\t", row.names = FALSE, quote = FALSE)
  cat(sprintf("  - Significant genes saved to: %s\n", file.path(output_dir, "de_genes_significant.tsv")))
  
  # Save significant genes with |logFC| > 1 as TSV
  write.table(sig_genes_fc, file.path(output_dir, "de_genes_significant_fc1.tsv"), sep = "\t", row.names = FALSE, quote = FALSE)
  cat(sprintf("  - Significant genes (|logFC|>1) saved to: %s\n", file.path(output_dir, "de_genes_significant_fc1.tsv")))
  
  # Save sample metadata as TSV
  write.table(sample_metadata, file.path(output_dir, "sample_metadata.tsv"), sep = "\t", row.names = TRUE, quote = FALSE)
  cat(sprintf("  - Sample metadata saved to: %s\n", file.path(output_dir, "sample_metadata.tsv")))
}

cat("\nAnalysis complete!\n")
