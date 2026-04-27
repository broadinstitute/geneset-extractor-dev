#!/usr/bin/env Rscript
#
# Prepare clean metadata file from GTEx annotations
# Combines sample attributes and subject phenotypes
# Output: metadata.tsv with columns: sample_id, subject_id, tissue, age
#

# Set library path
options(repos = c(CRAN = "https://cloud.r-project.org/"))
user_lib <- path.expand("~/R/library")
.libPaths(c(user_lib, .libPaths()))

library(tidyverse)

cat("Preparing GTEx metadata file...\n\n")

# Define file paths
sample_attr_file <- "inputs/GTEx_Analysis_v8_Annotations_SampleAttributesDS.txt"
subject_pheno_file <- "inputs/GTEx_Analysis_v8_Annotations_SubjectPhenotypesDS.txt"
output_file <- "inputs/metadata.tsv"

# Load files
cat("Step 1: Loading input files...\n")
sample_attr <- read.table(sample_attr_file, sep = "\t", header = TRUE, 
                           row.names = 1, stringsAsFactors = FALSE)
cat(sprintf("  - Sample attributes: %d samples\n", nrow(sample_attr)))

subject_pheno <- read.table(subject_pheno_file, sep = "\t", header = TRUE, 
                             row.names = 1, stringsAsFactors = FALSE)
cat(sprintf("  - Subject phenotypes: %d subjects\n", nrow(subject_pheno)))

# Extract subject ID from sample ID (format: GTEX-XXXXXX-XXXX-SM-XXXXX)
# Subject ID format: GTEX-XXXX or GTEX-XXXXXX (up to 10 characters total)
cat("\nStep 2: Parsing sample IDs...\n")
sample_attr$subject_id <- substr(rownames(sample_attr), 1, 10)
# Remove trailing dash if present (in case of GTEX-XXXX format)
sample_attr$subject_id <- gsub("-$", "", sample_attr$subject_id)

cat(sprintf("  - Unique subjects in samples: %d\n", length(unique(sample_attr$subject_id))))

# Merge with subject phenotypes
cat("\nStep 3: Merging metadata...\n")
metadata <- sample_attr %>%
  rownames_to_column("sample_id") %>%
  select(sample_id, subject_id, SMTS, starts_with("SMTS")) %>%
  left_join(rownames_to_column(subject_pheno, "subject_id"), by = "subject_id")

# Select final columns
metadata <- metadata %>%
  select(sample_id, subject_id, tissue = SMTS, age = AGE) %>%
  filter(!is.na(tissue))

cat(sprintf("  - Samples with tissue and age data: %d\n", nrow(metadata)))
cat(sprintf("  - Samples with AGE data: %d\n", sum(!is.na(metadata$age))))

# Show tissue and age distribution
cat("\nTissue distribution:\n")
print(table(metadata$tissue))

cat("\nAge distribution:\n")
print(table(metadata$age))

# Write output file
cat(sprintf("\nStep 4: Writing output to %s...\n", output_file))
write.table(metadata, file = output_file, sep = "\t", quote = FALSE, 
            row.names = FALSE, col.names = TRUE)

cat(sprintf("✓ Metadata file created: %s\n", output_file))
cat(sprintf("  Dimensions: %d samples × %d columns\n", nrow(metadata), ncol(metadata)))
cat(sprintf("  Columns: %s\n", paste(colnames(metadata), collapse = ", ")))

# Show sample
cat("\nFirst 5 rows:\n")
print(head(metadata, 5))
