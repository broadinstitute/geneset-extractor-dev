#!/usr/bin/env Rscript
#
# Batch Differential Expression Analysis
# Runs limma-voom DE analysis for multiple tissue/age comparisons
#
# This script reads comparison specifications from comparisons.txt
# and runs de_analysis_limma_voom.R for each comparison in sequence
#

# Set CRAN mirror and library path
options(repos = c(CRAN = "https://cloud.r-project.org/"))
user_lib <- path.expand("~/R/library")
if (!dir.exists(user_lib)) {
  dir.create(user_lib, recursive = TRUE)
}
.libPaths(c(user_lib, .libPaths()))

# Load required libraries
library(tidyverse)

cat("============================================================================\n")
cat("BATCH DIFFERENTIAL EXPRESSION ANALYSIS\n")
cat("============================================================================\n\n")

# ============================================================================
# LOAD COMPARISONS FROM FILE
# ============================================================================

comparisons_file <- "comparisons.txt"

if (!file.exists(comparisons_file)) {
  cat("ERROR: comparisons.txt not found!\n")
  quit(status = 1)
}

# Read comparisons, removing empty lines and trimming whitespace
comparisons <- read.delim(comparisons_file, header = FALSE, stringsAsFactors = FALSE)
comparisons$V1 <- trimws(comparisons$V1)
comparisons <- comparisons[comparisons$V1 != "", , drop = FALSE]
comparisons_list <- comparisons$V1

cat(sprintf("Loaded %d comparisons from %s\n\n", length(comparisons_list), comparisons_file))

# Show first few comparisons
cat("First 5 comparisons:\n")
for (i in 1:min(5, length(comparisons_list))) {
  cat(sprintf("  %d. %s\n", i, comparisons_list[i]))
}
cat("\n")

# ============================================================================
# RUN BATCH ANALYSIS
# ============================================================================

cat("Starting batch analysis...\n")
cat("============================================================================\n\n")

# Track progress
successful <- 0
failed <- 0
skipped <- 0
failed_comparisons <- c()
skipped_comparisons <- c()
start_time <- Sys.time()

for (i in seq_along(comparisons_list)) {
  comparison <- comparisons_list[i]
  
  cat(sprintf("\n[%d/%d] Running: %s\n", i, length(comparisons_list), comparison))
  cat(sprintf("Time elapsed: %.1f minutes\n", as.numeric(difftime(Sys.time(), start_time, units = "mins"))))
  
  # Try to run the analysis
  tryCatch({
    # Create an environment with the comparison parameter
    analysis_env <- new.env()
    analysis_env$comparison_param <- comparison
    analysis_env$comparison_type <- "TISSUE_AGE"
    
    # Source the main analysis script with the comparison parameter in scope
    source("de_analysis_limma_voom.R", local = analysis_env, verbose = FALSE)
    
    successful <- successful + 1
    cat(sprintf("✓ Completed: %s\n", comparison))
    
  }, error = function(e) {
    error_msg <- conditionMessage(e)
    
    # Check if it's a skip (insufficient samples) or a real error
    if (grepl("SKIP_COMPARISON", error_msg, fixed = TRUE)) {
      skipped <<- skipped + 1
      skipped_comparisons <<- c(skipped_comparisons, comparison)
      cat(sprintf("⊘ Skipped: %s\n", comparison))
    } else {
      failed <<- failed + 1
      failed_comparisons <<- c(failed_comparisons, comparison)
      cat(sprintf("✗ FAILED: %s\n", comparison))
      cat(sprintf("  Error: %s\n", error_msg))
    }
  })
}

# ============================================================================
# SUMMARY
# ============================================================================

cat("\n\n")
cat("============================================================================\n")
cat("BATCH ANALYSIS COMPLETE\n")
cat("============================================================================\n")

total_time <- as.numeric(difftime(Sys.time(), start_time, units = "mins"))

cat(sprintf("\nSummary:\n"))
cat(sprintf("  Total comparisons: %d\n", length(comparisons_list)))
cat(sprintf("  Successful: %d\n", successful))
cat(sprintf("  Skipped (insufficient samples): %d\n", skipped))
cat(sprintf("  Failed: %d\n", failed))
cat(sprintf("  Success rate: %.1f%%\n", 100 * successful / length(comparisons_list)))
cat(sprintf("  Total time: %.1f minutes (%.2f hours)\n", total_time, total_time / 60))

if (skipped > 0) {
  cat(sprintf("\nSkipped comparisons (insufficient samples):\n"))
  for (comp in skipped_comparisons) {
    cat(sprintf("  - %s\n", comp))
  }
}

if (failed > 0) {
  cat(sprintf("\nFailed comparisons:\n"))
  for (comp in failed_comparisons) {
    cat(sprintf("  - %s\n", comp))
  }
}

cat("\nResults saved in tissue-specific folders:\n")
cat("  e.g., Thyroid_20-29_vs_40-49/, Heart_20-29_vs_30-39/, etc.\n")
cat("\n")

if (failed > 0) {
  quit(status = 1)
} else {
  quit(status = 0)
}
