"""Extract tables from the native-text annual reports (2022-2025) with pdfplumber.

Writes CSVs to extracted/ in the same layouts as the hand transcriptions in transcribed/:
  <year>_citywide.csv     offense,subtype,prior,current,reported_pct
  <year>_ward.csv         data_year,offense,subtype,ward_1..ward_5,total
  <year>_enforcement.csv  measure,prior,current,reported_pct
  <year>_chart.csv        data_year + one column per chart category (five-year comparison table)

Pages are identified by content, not page number, because the page order varies by year.
"""
import csv
import re
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "Crime data"
OUT_DIR = ROOT / "extracted"

FILES = {
    2022: "2022 ANNUAL STATISTICS.pdf",
    2023: "2023.Annual.pdf",
    2024: "2024.Annual.pdf",
    2025: "2025.Annual.pdf",
}

SUBTYPES = {"GUN", "KNIFE", "OTHER WEAPON", "STRONG ARM", "NO WEAPON", "HOMES", "OUTBUILDINGS"}
PARENTS = {
    "HOMICIDE", "RAPE", "COMMERCIAL ROBBERY", "CITIZEN ROBBERY", "CARJACKING", "ASSAULT",
    "B & E RESIDENTIAL", "B & E COMMERCIAL", "STOLEN VEHICLE", "THEFT", "ARSON",
}
ENFORCEMENT_SINGLE = {
    "CANINE ACTIVITY REPORTS": "CANINE_ACTIVITY_REPORTS",
    "RED LIGHT CITATIONS": "RED_LIGHT_CITATIONS",
    "DUI ARRESTS": "DUI_ARRESTS",
    "SPEED CAMERA CITATIONS": "SPEED_CAMERA_CITATIONS",
}

# A row is a label followed by numeric tokens (integers, decimals, percentages).
ROW_RE = re.compile(r"^([A-Z&][A-Z& ]*?)\s+(-?[\d.]+%?(?:\s+-?[\d.]+%?)*)$")


def parse_row(line):
    m = ROW_RE.match(line.strip())
    if not m:
        return None, []
    return m.group(1).strip(), m.group(2).split()


def split_values(tokens):
    """Return (ints, pct) where pct is the '%' token as a float (without the % sign)."""
    ints = [int(t) for t in tokens if not t.endswith("%")]
    pcts = [float(t[:-1]) for t in tokens if t.endswith("%")]
    return ints, (pcts[0] if pcts else None)


def year_order(text, report_year):
    """True if the table lists the current year before the prior year."""
    m = re.search(r"CLASSIFICATION\s+(\d{4})\s+(\d{4})", text)
    return bool(m) and int(m.group(1)) == report_year


def parse_citywide(text, report_year):
    current_first = year_order(text, report_year)
    rows, parent, section = [], None, "persons"
    for line in text.splitlines():
        if "CRIMES AGAINST PROPERTY" in line:
            section = "property"
            continue
        label, tokens = parse_row(line)
        if not label:
            continue
        ints, pct = split_values(tokens)
        a, b = ints[0], ints[1]
        prior, current = (b, a) if current_first else (a, b)
        if label in PARENTS:
            parent = label
            rows.append([label, "", prior, current, pct])
        elif label in SUBTYPES:
            rows.append([parent, label, prior, current, pct])
        elif label == "SUBTOTAL":
            rows.append(["SUBTOTAL_PERSONS" if section == "persons" else "SUBTOTAL_PROPERTY", "", prior, current, pct])
        elif label == "TOTAL CRIMES":
            rows.append(["TOTAL", "", prior, current, pct])
        elif label == "CALLS FOR SERVICE":
            rows.append(["CALLS_FOR_SERVICE", "", prior, current, pct])
    return rows


def parse_ward(text, report_year):
    rows, parent = [], None
    for line in text.splitlines():
        label, tokens = parse_row(line)
        if not label or len(tokens) != 6:
            continue
        vals = [int(t) for t in tokens]
        if label in PARENTS:
            parent = label
            rows.append([report_year, label, ""] + vals)
        elif label in SUBTYPES:
            rows.append([report_year, parent, label] + vals)
        elif label == "TOTAL":
            rows.append([report_year, "TOTAL", ""] + vals)
    return rows


def parse_enforcement(text, report_year):
    current_first = year_order(text, report_year)
    rows, section = [], None
    for line in text.splitlines():
        s = line.strip()
        if s in ("ARRESTS", "CRIMINAL ARRESTS"):
            section = "ARRESTS"
            continue
        if s == "CITATIONS":
            section = "CITATIONS"
            continue
        label, tokens = parse_row(line)
        if not label:
            continue
        ints, pct = split_values(tokens)
        a, b = ints[0], ints[1]
        prior, current = (b, a) if current_first else (a, b)
        if label in ENFORCEMENT_SINGLE:
            rows.append([ENFORCEMENT_SINGLE[label], prior, current, pct])
        elif section and label in ("JUVENILE", "ADULT", "PARKING", "STATE", "TOTAL"):
            rows.append([f"{section}_{label}", prior, current, pct])
    return rows


def parse_chart(text):
    """Five-year comparison chart's data table: header row of categories, then one row per year."""
    header, rows = None, []
    for line in text.splitlines():
        if line.startswith("ARSON THEFT"):
            header = (line.replace("STOLEN VEH", "STOLEN_VEH")
                          .replace("B & E RES", "BE_RES")
                          .replace("B & E COM", "BE_COM").split())
            continue
        parts = line.split()
        if header and parts and re.fullmatch(r"20\d\d", parts[0]) and len(parts) == len(header) + 1:
            rows.append([int(p) for p in parts])
    return (["data_year"] + header if header else None), rows


def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"wrote {path.relative_to(ROOT)} ({len(rows)} rows)")


def main():
    OUT_DIR.mkdir(exist_ok=True)
    for year, fname in FILES.items():
        with pdfplumber.open(PDF_DIR / fname) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if "WARD 1" in text:
                    write_csv(OUT_DIR / f"{year}_ward.csv",
                              ["data_year", "offense", "subtype", "ward_1", "ward_2", "ward_3", "ward_4", "ward_5", "total"],
                              parse_ward(text, year))
                elif "CRIMES AGAINST PERSONS" in text:
                    write_csv(OUT_DIR / f"{year}_citywide.csv",
                              ["offense", "subtype", "prior", "current", "reported_pct"],
                              parse_citywide(text, year))
                elif "CITATIONS" in text:
                    write_csv(OUT_DIR / f"{year}_enforcement.csv",
                              ["measure", "prior", "current", "reported_pct"],
                              parse_enforcement(text, year))
                elif "COMPARISON" in text:
                    header, rows = parse_chart(text)
                    if header:
                        write_csv(OUT_DIR / f"{year}_chart.csv", header, rows)


if __name__ == "__main__":
    main()
