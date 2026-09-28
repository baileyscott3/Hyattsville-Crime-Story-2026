"""Load transcribed/ and extracted/ CSVs into data/hyattsville_crime.sqlite plus CSV exports.

Every number is stored with the report it came from (report_year) and the year it describes
(data_year). Each annual report prints the prior year too, so most years appear twice; the
*_final views keep each year's figure from its own report.
"""
import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "hyattsville_crime.sqlite"
SOURCES = [ROOT / "transcribed", ROOT / "extracted"]

SOURCE_FILES = {
    2015: "2015 ANNUAL STATISTICS.pdf", 2016: "2016 Annual Statistics.pdf",
    2017: "2017 Annual Statistics.pdf", 2018: "2018 Annual Statistics.pdf",
    2019: "2019 Annual Statistics.pdf", 2020: "2020 Annual Statistics.pdf",
    2021: "2021 Annual Statistics.pdf", 2022: "2022 ANNUAL STATISTICS.pdf",
    2023: "2023.Annual.pdf", 2024: "2024.Annual.pdf", 2025: "2025.Annual.pdf",
}
# PDF page holding each table, per report year (defaults below; exceptions listed).
DEFAULT_PAGES = {"citywide": 1, "ward": 3, "ward_prior": 4, "enforcement": 4, "chart": 5}
PAGE_OVERRIDES = {
    2019: {"enforcement": 5},
    2022: {"ward": 2, "enforcement": 3, "chart": 4},
    2023: {"enforcement": 2, "chart": 3},
    2024: {"enforcement": 2, "chart": 3},
    2025: {"ward": 2, "enforcement": 3, "chart": 4},
}

PERSONS = {"HOMICIDE", "RAPE", "COMMERCIAL ROBBERY", "CITIZEN ROBBERY", "CARJACKING", "ASSAULT"}
TOTAL_ROWS = {"SUBTOTAL_PERSONS": "persons", "SUBTOTAL_PROPERTY": "property", "TOTAL": "total"}
WARDS = ["ward_1", "ward_2", "ward_3", "ward_4", "ward_5"]

SCHEMA = """
CREATE TABLE offenses (
    report_year INTEGER, data_year INTEGER,
    source_table TEXT,          -- 'citywide' (year-over-year table) or 'ward' (ward breakdown table)
    geography TEXT,             -- 'citywide' or 'ward_1'..'ward_5'
    category TEXT,              -- 'persons' or 'property'
    offense TEXT, subtype TEXT, -- subtype NULL for the parent offense row
    count INTEGER,
    reported_pct_change REAL,   -- % change as printed (current-year citywide rows only)
    source_file TEXT, page INTEGER
);
CREATE TABLE totals (
    report_year INTEGER, data_year INTEGER, source_table TEXT, geography TEXT,
    measure TEXT,               -- 'persons', 'property' (subtotals) or 'total'
    count INTEGER, reported_pct_change REAL, source_file TEXT, page INTEGER
);
CREATE TABLE enforcement (
    report_year INTEGER, data_year INTEGER, measure TEXT, count INTEGER,
    reported_pct_change REAL, source_file TEXT, page INTEGER
);
CREATE TABLE calls_for_service (
    report_year INTEGER, data_year INTEGER, total INTEGER,
    pct_citizen_generated REAL, pct_officer_initiated REAL,
    reported_pct_change REAL, source_file TEXT, page INTEGER
);
CREATE TABLE chart_values (       -- five-year comparison chart tables (2023-2025), for cross-checks
    report_year INTEGER, data_year INTEGER, category TEXT, count INTEGER, source_file TEXT, page INTEGER
);

CREATE VIEW offenses_final AS
    SELECT data_year AS year, geography, category, offense, subtype, count, source_file, page
    FROM offenses
    WHERE report_year = data_year AND (source_table = 'citywide' OR geography != 'citywide');
CREATE VIEW totals_final AS
    SELECT data_year AS year, geography, measure, count, source_file, page
    FROM totals
    WHERE report_year = data_year AND (source_table = 'citywide' OR geography != 'citywide');
CREATE VIEW enforcement_final AS
    SELECT data_year AS year, measure, count, source_file, page FROM enforcement WHERE report_year = data_year;
CREATE VIEW calls_for_service_final AS
    SELECT data_year AS year, total, pct_citizen_generated, pct_officer_initiated, source_file, page
    FROM calls_for_service WHERE report_year = data_year;
"""


def page(year, table):
    return PAGE_OVERRIDES.get(year, {}).get(table, DEFAULT_PAGES[table])


def num(s):
    return None if s in ("", None) else (float(s) if "." in s else int(s))


def find_files(suffix):
    """Yield (report_year, path) for every <year>_<suffix>.csv across source dirs."""
    for d in SOURCES:
        for p in sorted(d.glob(f"*_{suffix}.csv")):
            yield int(p.name[:4]), p


def read(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_citywide(db):
    for ry, path in find_files("citywide"):
        src, pg = SOURCE_FILES[ry], page(ry, "citywide")
        cfs = {}
        for r in read(path):
            off, prior, cur, pct = r["offense"], num(r["prior"]), num(r["current"]), num(r["reported_pct"])
            if off in TOTAL_ROWS:
                for dy, val, p in ((ry - 1, prior, None), (ry, cur, pct)):
                    db.execute("INSERT INTO totals VALUES (?,?,?,?,?,?,?,?,?)",
                               (ry, dy, "citywide", "citywide", TOTAL_ROWS[off], val, p, src, pg))
            elif off == "CALLS_FOR_SERVICE":
                cfs["total"] = (prior, cur, pct)
            elif off.startswith("PCT_"):
                cfs[off] = (prior, cur)
            else:
                cat = "persons" if off in PERSONS else "property"
                for dy, val, p in ((ry - 1, prior, None), (ry, cur, pct)):
                    db.execute("INSERT INTO offenses VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                               (ry, dy, "citywide", "citywide", cat, off, r["subtype"] or None, val, p, src, pg))
        if "total" in cfs:
            prior, cur, pct = cfs["total"]
            cit = cfs.get("PCT_CITIZEN_GENERATED", (None, None))
            off_ = cfs.get("PCT_OFFICER_INITIATED", (None, None))
            db.execute("INSERT INTO calls_for_service VALUES (?,?,?,?,?,?,?,?)",
                       (ry, ry - 1, prior, cit[0], off_[0], None, src, pg))
            db.execute("INSERT INTO calls_for_service VALUES (?,?,?,?,?,?,?,?)",
                       (ry, ry, cur, cit[1], off_[1], pct, src, pg))


def load_ward(db, suffix, table):
    for ry, path in find_files(suffix):
        src, pg = SOURCE_FILES[ry], page(ry, table)
        for r in read(path):
            dy, off = int(r["data_year"]), r["offense"]
            geos = WARDS + (["citywide"] if r["total"] != "" else [])
            for geo in geos:
                val = num(r["total"] if geo == "citywide" else r[geo])
                if off == "TOTAL":
                    db.execute("INSERT INTO totals VALUES (?,?,?,?,?,?,?,?,?)",
                               (ry, dy, "ward", geo, "total", val, None, src, pg))
                else:
                    cat = "persons" if off in PERSONS else "property"
                    db.execute("INSERT INTO offenses VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                               (ry, dy, "ward", geo, cat, off, r["subtype"] or None, val, None, src, pg))


def load_enforcement(db):
    for ry, path in find_files("enforcement"):
        src, pg = SOURCE_FILES[ry], page(ry, "enforcement")
        for r in read(path):
            db.execute("INSERT INTO enforcement VALUES (?,?,?,?,?,?,?)",
                       (ry, ry - 1, r["measure"], num(r["prior"]), None, src, pg))
            db.execute("INSERT INTO enforcement VALUES (?,?,?,?,?,?,?)",
                       (ry, ry, r["measure"], num(r["current"]), num(r["reported_pct"]), src, pg))


def load_charts(db):
    for ry, path in find_files("chart"):
        src, pg = SOURCE_FILES[ry], page(ry, "chart")
        for r in read(path):
            dy = int(r.pop("data_year"))
            for cat, val in r.items():
                db.execute("INSERT INTO chart_values VALUES (?,?,?,?,?,?)", (ry, dy, cat, int(val), src, pg))


def export(db, name, sql):
    cur = db.execute(sql)
    with open(DATA_DIR / f"{name}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([c[0] for c in cur.description])
        w.writerows(cur.fetchall())


def main():
    DATA_DIR.mkdir(exist_ok=True)
    DB_PATH.unlink(missing_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    load_citywide(db)
    load_ward(db, "ward", "ward")
    load_ward(db, "ward_prior", "ward_prior")
    load_enforcement(db)
    load_charts(db)
    db.commit()

    order = "ORDER BY 1, 2"
    export(db, "offenses_all_reports", f"SELECT * FROM offenses {order}")
    export(db, "offenses", f"SELECT * FROM offenses_final {order}")
    export(db, "totals", f"SELECT * FROM totals_final {order}")
    export(db, "enforcement", f"SELECT * FROM enforcement_final {order}")
    export(db, "calls_for_service", f"SELECT * FROM calls_for_service_final {order}")
    # Wide table for charting: citywide parent offenses, one row per year
    offenses = [r[0] for r in db.execute(
        "SELECT DISTINCT offense FROM offenses_final ORDER BY category, offense")]
    cols = ", ".join(
        f"SUM(CASE WHEN offense = '{o}' THEN count END) AS \"{o}\"" for o in offenses)
    export(db, "citywide_by_year",
           f"SELECT year, {cols} FROM offenses_final "
           f"WHERE geography = 'citywide' AND subtype IS NULL GROUP BY year ORDER BY year")

    for t in ("offenses", "totals", "enforcement", "calls_for_service", "chart_values"):
        print(f"{t}: {db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]} rows")
    print(f"wrote {DB_PATH.relative_to(ROOT)} and CSVs in data/")


if __name__ == "__main__":
    main()
