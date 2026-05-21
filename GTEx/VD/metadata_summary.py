#!/usr/bin/env python3
"""
Join GTEx sample and subject files and create count summaries.
"""
import pandas as pd
from pathlib import Path

# File paths
input_dir = Path("inputs")
samples_file = input_dir / "GTEx_Analysis_v8_Annotations_SampleAttributesDS.txt"
subjects_file = input_dir / "GTEx_Analysis_v8_Annotations_SubjectPhenotypesDS.txt"
output_file = Path("outputs") / "joined_summary_counts.txt"

# Read the files
print("Reading sample attributes...")
samples_df = pd.read_csv(samples_file, sep="\t")

print("Reading subject phenotypes...")
subjects_df = pd.read_csv(subjects_file, sep="\t")

# Extract SUBJID from SAMPID (format: GTEX-XXXXX-...)
samples_df["SUBJID"] = samples_df["SAMPID"].str.split("-").str[:2].str.join("-")

# Join on SUBJID
print("Joining on SUBJID...")
joined_df = samples_df.merge(subjects_df, on="SUBJID", how="left")

print(f"Joined {len(joined_df)} records")

# Create summary counts
output_lines = []

# Counts by tissue (SMTSD)
output_lines.append("=" * 60)
output_lines.append("COUNTS BY TISSUE (SMTSD)")
output_lines.append("=" * 60)
tissue_counts = joined_df["SMTSD"].value_counts().sort_values(ascending=False)
for tissue, count in tissue_counts.items():
    output_lines.append(f"{tissue}\t{count}")

output_lines.append("")

# Counts by age
output_lines.append("=" * 60)
output_lines.append("COUNTS BY AGE")
output_lines.append("=" * 60)
age_counts = joined_df["AGE"].value_counts().sort_index()
# Sort by age range numerically
age_order = ["20-29", "30-39", "40-49", "50-59", "60-69", "70-79"]
age_counts = age_counts.reindex([age for age in age_order if age in age_counts.index])
for age, count in age_counts.items():
    output_lines.append(f"{age}\t{count}")

# Write output
output_file.parent.mkdir(parents=True, exist_ok=True)
with open(output_file, "w") as f:
    f.write("\n".join(output_lines))

print(f"\nSummary written to {output_file}")
print("\n".join(output_lines))
