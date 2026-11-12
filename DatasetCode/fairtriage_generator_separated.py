#!/usr/bin/env python3
"""
FairTriage demographic-variant generator.

For each source vignette, generates:
  1 unbiased control
  4 ethnicity-only conditions (SES omitted)
  3 SES-only conditions (ethnicity omitted)
  12 ethnicity x SES intersectional conditions

With the default categories this is 20 variants per vignette.
"""
import argparse
import itertools
from pathlib import Path
import pandas as pd

INPUT_FILE = "Data_Pub.xlsx"
SHEET_NAME = "First 255"
N_CASES = 20
SAMPLE_MODE = "first"
RANDOM_SEED = 42

ETHNICITIES = ["White", "Black", "Asian", "Hispanic"]
SOCIOECONOMIC_STATUSES = ["Low income", "High income", "Unhoused"]
INCLUDE_UNBIASED_CONTROL = True
INCLUDE_ETHNICITY_ONLY = True
INCLUDE_SES_ONLY = True
INCLUDE_INTERSECTIONAL = True
OUTPUT_FILE = "fairtriage_demographic_variants_separated.csv"


def find_column(columns, possible_names):
    for name in possible_names:
        if name in columns:
            return name
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Generate isolated and intersectional FairTriage demographic variants."
    )
    parser.add_argument("--input", default=INPUT_FILE)
    parser.add_argument("--sheet", default=SHEET_NAME)
    parser.add_argument("--n-cases", type=int, default=N_CASES)
    parser.add_argument("--sample", choices=["first", "random"], default=SAMPLE_MODE)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    parser.add_argument("--output", default=OUTPUT_FILE)
    args = parser.parse_args()

    if args.n_cases < 1:
        raise ValueError("--n-cases must be at least 1.")
    if not ETHNICITIES or not SOCIOECONOMIC_STATUSES:
        raise ValueError("Add at least one ethnicity and one SES category.")

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(
            f"Cannot find {input_path}. Put Data_Pub.xlsx in this folder "
            "or pass its path with --input."
        )

    source = pd.read_excel(input_path, sheet_name=args.sheet)
    if "Case" not in source.columns:
        raise ValueError(f"No 'Case' column found. Columns: {list(source.columns)}")
    source = source[source["Case"].notna()].copy()

    if args.n_cases > len(source):
        raise ValueError(
            f"Requested {args.n_cases} vignettes, but sheet contains "
            f"{len(source)} non-empty cases."
        )
    selected = (
        source.sample(n=args.n_cases, random_state=args.seed).copy()
        if args.sample == "random" else source.head(args.n_cases).copy()
    )

    column_aliases = {
        "BP_Systolic": ["BP Systolic", "BP (Systolic)"],
        "BP_Diastolic": ["BP Diastolic", "BP (Diastolic)"],
        "HR": ["HR"], "RR": ["RR"], "O2_Sat": ["O2 Sat"],
        "Temperature": ["Temperature", "Temp"],
    }

    rows = []
    intersectional = list(itertools.product(ETHNICITIES, SOCIOECONOMIC_STATUSES))

    for case_number, (source_index, record) in enumerate(selected.iterrows(), start=1):
        case_id = f"CASE{case_number:03d}"
        original_text = str(record["Case"])
        variants = []

        if INCLUDE_UNBIASED_CONTROL:
            variants.append({
                "suffix": "CTRL", "type": "Unbiased control",
                "ethnicity": "Unspecified", "ses": "Unspecified",
                "patient_text": "patient",
            })

        if INCLUDE_ETHNICITY_ONLY:
            for i, ethnicity in enumerate(ETHNICITIES, start=1):
                variants.append({
                    "suffix": f"ETH{i:02d}", "type": "Ethnicity only",
                    "ethnicity": ethnicity, "ses": "Unspecified",
                    "patient_text": f"{ethnicity} patient",
                })

        if INCLUDE_SES_ONLY:
            for i, ses in enumerate(SOCIOECONOMIC_STATUSES, start=1):
                # SES-only conditions deliberately omit ethnicity.
                variants.append({
                    "suffix": f"SES{i:02d}", "type": "SES only",
                    "ethnicity": "Unspecified", "ses": ses,
                    "patient_text": f"patient from a {ses.lower()} background",
                })

        if INCLUDE_INTERSECTIONAL:
            for i, (ethnicity, ses) in enumerate(intersectional, start=1):
                variants.append({
                    "suffix": f"INT{i:02d}", "type": "Intersectional",
                    "ethnicity": ethnicity, "ses": ses,
                    "patient_text": f"{ethnicity} patient from a {ses.lower()} background",
                })

        for variant in variants:
            generated_text = original_text.replace("{patient}", variant["patient_text"])
            output_row = {
                "Case_ID": case_id,
                "Source_Excel_Row": int(source_index) + 2,
                "Variant_ID": f"{case_id}_{variant['suffix']}",
                "Variant_Type": variant["type"],
                "Ethnicity": variant["ethnicity"],
                "Socioeconomic_Status": variant["ses"],
                "Vignette_Original": original_text,
                "Vignette_Text": generated_text,
            }
            for standard_name, aliases in column_aliases.items():
                source_column = find_column(record.index, aliases)
                if source_column is not None:
                    output_row[standard_name] = record[source_column]
            rows.append(output_row)

    output = pd.DataFrame(rows)
    output.to_csv(args.output, index=False, encoding="utf-8-sig")

    per_case = len(output) // len(selected)
    print("FairTriage separated-demographics dataset generated")
    print("---------------------------------------------------")
    print(f"Source workbook: {input_path}")
    print(f"Worksheet: {args.sheet}")
    print(f"Source vignettes: {len(selected)}")
    print(f"Variants per vignette: {per_case}")
    print(f"  Control: {int(INCLUDE_UNBIASED_CONTROL)}")
    print(f"  Ethnicity only: {len(ETHNICITIES) if INCLUDE_ETHNICITY_ONLY else 0}")
    print(f"  SES only: {len(SOCIOECONOMIC_STATUSES) if INCLUDE_SES_ONLY else 0}")
    print(f"  Intersectional: {len(intersectional) if INCLUDE_INTERSECTIONAL else 0}")
    print(f"Total rows: {len(output)}")
    print(f"Output: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
