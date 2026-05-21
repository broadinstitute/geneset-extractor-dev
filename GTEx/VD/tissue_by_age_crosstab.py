#!/usr/bin/env python3
"""
Create a crosstab of tissue types (rows) by age groups (columns).
"""
import pandas as pd
from pathlib import Path

# File paths
input_dir = Path("inputs")
samples_file = input_dir / "GTEx_Analysis_v8_Annotations_SampleAttributesDS.txt"
subjects_file = input_dir / "GTEx_Analysis_v8_Annotations_SubjectPhenotypesDS.txt"
output_file = Path("outputs") / "subtissue_by_age_counts.tsv"

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

# Reorder age columns chronologically
age_order = ["20-29", "30-39", "40-49", "50-59", "60-69", "70-79"]

# Create crosstab by SMTSD (detailed tissue)
print("Creating crosstab by SMTSD (detailed tissue)...")
crosstab_smtsd = pd.crosstab(joined_df["SMTSD"], joined_df["AGE"])
existing_ages = [age for age in age_order if age in crosstab_smtsd.columns]
crosstab_smtsd = crosstab_smtsd[existing_ages]
crosstab_smtsd = crosstab_smtsd.sort_index()

# Create crosstab by SMTS (general tissue)
print("Creating crosstab by SMTS (general tissue)...")
crosstab_smts = pd.crosstab(joined_df["SMTS"], joined_df["AGE"])
crosstab_smts = crosstab_smts[existing_ages]
crosstab_smts = crosstab_smts.sort_index()

# Write to TSV
output_file.parent.mkdir(parents=True, exist_ok=True)
output_file_smts = Path("outputs") / "tissue_by_age_counts.tsv"

crosstab_smtsd.to_csv(output_file, sep="\t")
crosstab_smts.to_csv(output_file_smts, sep="\t")

print(f"\nSMTSD crosstab saved to {output_file}")
print("\nPreview (SMTSD):")
print(crosstab_smtsd)

print(f"\n\nSMTS crosstab saved to {output_file_smts}")
print("\nPreview (SMTS):")
print(crosstab_smts)
