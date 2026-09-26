from pathlib import Path
import csv
import re

# ============================================================
# CHANGE THIS TO YOUR FOLDER
# ============================================================
folder = Path(r"C:\Users\agfla\Massachusetts Institute of Technology\MIT Rocket Team - Project Iris\AeroD\Balius\AVL\runs_trial")

output_file = folder / "aero_results.csv"


# ============================================================
# Variables we want in the CSV
# ============================================================
columns = [
    "filename",
    "Alpha",
    "Beta",
    "Mach",
    "pb/2V",
    "p'b/2V",
    "qc/2V",
    "rb/2V",
    "r'b/2V",
    "CXtot",
    "CYtot",
    "CZtot",
    "Cltot",
    "Cltot",
    "Cmtot",
    "Cntot",
    "Cntot",
    "Cl'tot",
    "CDtot",
    "CDvis",
    "CDind",
    "CLff",
    "CDff",
    "CYff",
    "e",
    "delta_a",
    "delta_e",
    "delta_r"
]


def get_value(text, variable):
    """
    Find a variable followed by = and return its numerical value.
    Example:
        Alpha = 15.00000
    returns:
        15.00000
    """

    # Escape special characters such as / and '
    pattern = rf"{re.escape(variable)}\s*=\s*([-+]?(?:\d*\.\d+|\d+\.?)(?:[Ee][-+]?\d+)?)"

    match = re.search(pattern, text)

    if match:
        return float(match.group(1))

    return ""


# ============================================================
# Read every TXT file
# ============================================================
rows = []

for txt_file in sorted(folder.glob("*.txt")):

    print(f"Reading {txt_file.name}")

    with open(txt_file, "r", encoding="utf-8") as f:
        text = f.read()

    row = {
        "filename": txt_file.name
    }

    for variable in columns[1:]:
        row[variable] = get_value(text, variable)

    rows.append(row)


# ============================================================
# Write CSV
# ============================================================
with open(output_file, "w", newline="", encoding="utf-8") as f:

    writer = csv.DictWriter(
        f,
        fieldnames=columns
    )

    writer.writeheader()
    writer.writerows(rows)


print()
print("===================================")
print("CSV created successfully!")
print(output_file)
print("===================================")
