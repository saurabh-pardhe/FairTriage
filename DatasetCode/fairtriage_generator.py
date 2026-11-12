#!/usr/bin/env python3
"""
FairTriage vignette demographic-variant generator

What it does
------------
1. Reads ED vignettes from an Excel workbook.
2. Selects a user-controlled number of source vignettes (default: 20).
3. Creates one unbiased control plus every Ethnicity x Socioeconomic Status
   combination for each selected vignette.
4. Replaces the {patient} placeholder in the vignette text.
5. Saves the expanded records as a CSV file.

Install requirements
--------------------
    pip install pandas openpyxl

Example
-------
    python fairtriage_generator.py

To select 50 source vignettes:
    python fairtriage_generator.py --n-cases 50

To randomly select 20 source vignettes:
    python fairtriage_generator.py --n-cases 20 --sample random --seed 42

To use the other sheet:
    python fairtriage_generator.py --sheet "Additional 245 "

You can also edit the DEMOGRAPHIC CATEGORIES section below.
"""

import argparse
import itertools
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------
# EDIT THESE SETTINGS
# ---------------------------------------------------------------------

INPUT_FILE = "Data_Pub.xlsx"
SHEET_NAME = "First 255"

# Number of original vignettes to select.
# Set to 20 for 20 source cases. The output will contain 20 x 13 = 260 rows
# with the default demographic categories and unbiased control.
N_CASES = 20

# "first" selects the first N_CASES rows.
# "random" selects N_CASES rows at random (use --seed for reproducibility).
SAMPLE_MODE = "first"
RANDOM_SEED = 42

ETHNICITIES = ["White", "Black", "Asian", "Hispanic"]
SOCIOECONOMIC_STATUSES = ["Low income", "High income", "Unhoused"]

INCLUDE_UNBIASED_CONTROL = True
OUTPUT_FILE = "fairtriage_demographic_variants.csv"


# ---------------------------------------------------------------------
# SCRIPT
# ---------------------------------------------------------------------

def find_column(columns, possible_names):
    """Return the first matching column name, or None."""
    for name in possible_names:
        if name in columns:
            return name
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Create FairTriage demographic variants from ED vignettes."
    )
    parser.add_argument(
        "--input", default=INPUT_FILE,
        help="Excel input file (default: Data_Pub.xlsx)"
    )
    parser.add_argument(
        "--sheet", default=SHEET_NAME,
        help='Excel sheet name (default: "First 255")'
    )
    parser.add_argument(
        "--n-cases", type=int, default=N_CASES,
        help="Number of original vignettes to select (default: 20)"
    )
    parser.add_argument(
        "--sample", choices=["first", "random"], default=SAMPLE_MODE,
        help="Select first rows or a random sample (default: first)"
    )
    parser.add_argument(
        "--seed", type=int, default=RANDOM_SEED,
        help="Random seed for reproducible random sampling"
    )
    parser.add_argument(
        "--output", default=OUTPUT_FILE,
        help="Output CSV filename"
    )
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

    # Load the selected worksheet.
    source = pd.read_excel(input_path, sheet_name=args.sheet)

    if "Case" not in source.columns:
        raise ValueError(
            f"No 'Case' column found in sheet '{args.sheet}'. "
            f"Columns found: {list(source.columns)}"
        )

    # Select the requested number of original vignettes.
    source = source[source["Case"].notna()].copy()

    if args.n_cases > len(source):
        raise ValueError(
            f"You requested {args.n_cases} vignettes, but the selected "
            f"sheet contains only {len(source)} non-empty cases."
        )

    if args.sample == "random":
        selected = source.sample(
            n=args.n_cases, random_state=args.seed
        ).copy()
    else:
        selected = source.head(args.n_cases).copy()

    # Standardize vital-sign column names where present.
    column_aliases = {
        "BP_Systolic": ["BP Systolic", "BP (Systolic)"],
        "BP_Diastolic": ["BP Diastolic", "BP (Diastolic)"],
        "HR": ["HR"],
        "RR": ["RR"],
        "O2_Sat": ["O2 Sat"],
        "Temperature": ["Temperature", "Temp"],
    }

    rows = []
    combinations = list(itertools.product(
        ETHNICITIES, SOCIOECONOMIC_STATUSES
    ))

    for selected_number, (source_index, record) in enumerate(
        selected.iterrows(), start=1
    ):
        case_id = f"CASE{selected_number:03d}"
        original_text = str(record["Case"])

        variants = []

        if INCLUDE_UNBIASED_CONTROL:
            variants.append({
                "suffix": "CTRL",
                "variant_type": "Unbiased control",
                "ethnicity": "Unbiased",
                "ses": "Unbiased",
                "patient_text": "patient",
            })

        for combination_number, (ethnicity, ses) in enumerate(
            combinations, start=1
        ):
            variants.append({
                "suffix": f"DEM{combination_number:02d}",
                "variant_type": "Demographic combination",
                "ethnicity": ethnicity,
                "ses": ses,
                "patient_text": (
                    f"{ethnicity} patient from a {ses.lower()} background"
                ),
            })

        for variant in variants:
            # Replace the dataset's demographic placeholder.
            generated_text = original_text.replace(
                "{patient}", variant["patient_text"]
            )

            output_row = {
                "Case_ID": case_id,
                "Source_Excel_Row": int(source_index) + 2,
                "Variant_ID": f"{case_id}_{variant['suffix']}",
                "Variant_Type": variant["variant_type"],
                "Ethnicity": variant["ethnicity"],
                "Socioeconomic_Status": variant["ses"],
                "Vignette_Original": original_text,
                "Vignette_Text": generated_text,
            }

            # Carry over available vital signs from the source workbook.
            for standard_name, aliases in column_aliases.items():
                source_column = find_column(record.index, aliases)
                if source_column is not None:
                    output_row[standard_name] = record[source_column]

            rows.append(output_row)

    output = pd.DataFrame(rows)
    output.to_csv(args.output, index=False, encoding="utf-8-sig")

    variants_per_case = len(combinations) + int(INCLUDE_UNBIASED_CONTROL)

    print("FairTriage dataset generation complete")
    print("---------------------------------------")
    print(f"Source workbook: {input_path}")
    print(f"Worksheet: {args.sheet}")
    print(f"Source vignettes selected: {len(selected)}")
    print(f"Ethnicity categories: {len(ETHNICITIES)}")
    print(f"SES categories: {len(SOCIOECONOMIC_STATUSES)}")
    print(f"Demographic combinations per vignette: {len(combinations)}")
    print(f"Unbiased control included: {INCLUDE_UNBIASED_CONTROL}")
    print(f"Variants per vignette: {variants_per_case}")
    print(f"Total generated rows: {len(output)}")
    print(f"Output file: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
