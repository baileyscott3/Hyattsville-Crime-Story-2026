"""Consistency checks on data/hyattsville_crime.sqlite. Prints every mismatch, grouped by check,
and writes the same output to data/validation_report.txt.

Each mismatch is either a transcription error (fix the CSV) or a discrepancy in the source
document (log it in data/notes.md).
"""
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "hyattsville_crime.sqlite"
REPORT_PATH = ROOT / "data" / "validation_report.txt"

db = sqlite3.connect(DB_PATH)
results = defaultdict(list)


def q(sql, *args):
    return db.execute(sql, args).fetchall()


# 1. Subtypes sum to their parent offense
for ry, dy, tbl, geo, off, parent, subsum in q("""
    SELECT p.report_year, p.data_year, p.source_table, p.geography, p.offense, p.count, SUM(s.count)
    FROM offenses p JOIN offenses s
      ON s.report_year = p.report_year AND s.data_year = p.data_year AND s.source_table = p.source_table
     AND s.geography = p.geography AND s.offense = p.offense AND s.subtype IS NOT NULL
    WHERE p.subtype IS NULL
    GROUP BY 1, 2, 3, 4, 5, 6 HAVING p.count != SUM(s.count)"""):
    results["Subtypes don't sum to parent"].append(
        f"report {ry}, {dy} {tbl}/{geo} {off}: parent={parent}, subtypes sum={subsum}")

# 2. Wards 1-5 sum to the ward table's TOTAL column
for ry, dy, off, sub, tot, wsum in q("""
    SELECT t.report_year, t.data_year, t.offense, t.subtype, t.count, SUM(w.count)
    FROM offenses t JOIN offenses w
      ON w.report_year = t.report_year AND w.data_year = t.data_year AND w.source_table = 'ward'
     AND w.offense = t.offense AND w.subtype IS t.subtype AND w.geography LIKE 'ward_%'
    WHERE t.source_table = 'ward' AND t.geography = 'citywide'
    GROUP BY 1, 2, 3, 4, 5 HAVING t.count != SUM(w.count)"""):
    results["Wards don't sum to ward-table total"].append(
        f"report {ry}, {dy} {off}{'/' + sub if sub else ''}: total col={tot}, wards sum={wsum}")
for ry, dy, tot, wsum in q("""
    SELECT t.report_year, t.data_year, t.count, SUM(w.count) FROM totals t JOIN totals w
      ON w.report_year = t.report_year AND w.data_year = t.data_year AND w.source_table = 'ward'
     AND w.geography LIKE 'ward_%' AND w.measure = 'total'
    WHERE t.source_table = 'ward' AND t.geography = 'citywide' AND t.measure = 'total'
    GROUP BY 1, 2, 3 HAVING t.count != SUM(w.count)"""):
    results["Wards don't sum to ward-table total"].append(
        f"report {ry}, {dy} TOTAL row: total col={tot}, wards sum={wsum}")

# 3. Ward table totals match the citywide table in the same report
for ry, off, sub, wt, cw in q("""
    SELECT w.report_year, w.offense, w.subtype, w.count, c.count FROM offenses w JOIN offenses c
      ON c.report_year = w.report_year AND c.data_year = w.data_year AND c.source_table = 'citywide'
     AND c.offense = w.offense AND c.subtype IS w.subtype
    WHERE w.source_table = 'ward' AND w.geography = 'citywide' AND w.count != c.count"""):
    results["Ward table total != citywide table"].append(
        f"report {ry} {off}{'/' + sub if sub else ''}: ward table={wt}, citywide table={cw}")

# 4. Parent offenses sum to printed subtotals and grand total
for ry, dy, tbl, geo, measure, printed, computed in q("""
    WITH sums AS (
        SELECT report_year, data_year, source_table, geography, category, SUM(count) AS n
        FROM offenses WHERE subtype IS NULL GROUP BY 1, 2, 3, 4, 5
        UNION ALL
        SELECT report_year, data_year, source_table, geography, 'total', SUM(count)
        FROM offenses WHERE subtype IS NULL GROUP BY 1, 2, 3, 4)
    SELECT t.report_year, t.data_year, t.source_table, t.geography, t.measure, t.count, s.n
    FROM totals t JOIN sums s USING (report_year, data_year, source_table, geography)
    WHERE s.category = t.measure AND t.count != s.n"""):
    results["Offenses don't sum to printed subtotal/total"].append(
        f"report {ry}, {dy} {tbl}/{geo} {measure}: printed={printed}, sum of offenses={computed}")

# 5. The same year's figure differs between reports (prior-year column vs. that year's own report)
cross = [
    ("offenses", "source_table, geography, offense, subtype",
     "source_table || '/' || geography || ' ' || offense || COALESCE('/' || subtype, '')"),
    ("totals", "source_table, geography, measure", "source_table || '/' || geography || ' ' || measure"),
    ("enforcement", "measure", "measure"),
    ("calls_for_service", "1", "'calls for service'"),
]
for table, keys, label in cross:
    val = "total" if table == "calls_for_service" else "count"
    for dy, lbl, reports in q(f"""
        SELECT data_year, {label}, GROUP_CONCAT(report_year || ' report: ' || {val}, '; ')
        FROM {table} GROUP BY data_year, {keys}
        HAVING COUNT(DISTINCT {val}) > 1 ORDER BY data_year"""):
        results["Revised between reports"].append(f"{dy} {lbl}: {reports}")

# 6. Printed % change vs. recomputed
for table, label in (("offenses", "cur.offense || COALESCE('/' || cur.subtype, '')"),
                     ("totals", "cur.measure"), ("enforcement", "cur.measure"),
                     ("calls_for_service", "'calls for service'")):
    val = "total" if table == "calls_for_service" else "count"
    keys = {"offenses": ["source_table", "geography", "offense", "subtype"],
            "totals": ["source_table", "geography", "measure"],
            "enforcement": ["measure"], "calls_for_service": []}[table]
    join = "".join(f" AND pri.{k} IS cur.{k}" for k in keys)
    for ry, lbl, prior, cur, printed in q(f"""
        SELECT cur.report_year, {label}, pri.{val}, cur.{val}, cur.reported_pct_change
        FROM {table} cur JOIN {table} pri
          ON pri.report_year = cur.report_year AND pri.data_year = cur.data_year - 1 {join}
        WHERE cur.data_year = cur.report_year AND cur.reported_pct_change IS NOT NULL"""):
        if prior == 0 or cur == 0:
            true_pct = -100.0 if prior else (0.0 if cur == 0 else None)  # None: undefined (from 0)
            # Some years' spreadsheets print (current - prior) * 100% when either year is zero
            quirk_pct = (cur - prior) * 100.0
            if true_pct is not None and abs(printed - true_pct) < 0.01:
                pass
            elif abs(printed - quirk_pct) < 0.01:
                results["% change: zero-year formula quirk (not a data error)"].append(
                    f"report {ry} {lbl}: {prior}->{cur}, printed {printed}%"
                    f" (true change {'undefined' if true_pct is None else f'{true_pct:.0f}%'})")
            else:
                results["% change printed wrong"].append(
                    f"report {ry} {lbl}: {prior}->{cur}, printed {printed}%")
            continue
        true_pct = (cur - prior) / prior * 100
        # 2023+ reports round offense percentages to whole numbers
        tol = 0.51 if printed == round(printed) and ry >= 2022 else 0.011
        if abs(true_pct - printed) > tol:
            results["% change printed wrong"].append(
                f"report {ry} {lbl}: {prior}->{cur}, printed {printed}%, actual {true_pct:.2f}%")

# 7. Five-year chart tables match the table values
chart_map = {
    "ARSON": "offense = 'ARSON'", "THEFT": "offense = 'THEFT'", "STOLEN_VEH": "offense = 'STOLEN VEHICLE'",
    "BE_RES": "offense = 'B & E RESIDENTIAL'", "BE_COM": "offense = 'B & E COMMERCIAL'",
    "ASSAULT": "offense = 'ASSAULT'", "RAPE": "offense = 'RAPE'", "HOMICIDE": "offense = 'HOMICIDE'",
    "ROBBERY": "offense IN ('COMMERCIAL ROBBERY', 'CITIZEN ROBBERY', 'CARJACKING')",
}
for ry, dy, cat, chart in q("SELECT report_year, data_year, category, count FROM chart_values"):
    if cat == "TOTAL":
        row = q("SELECT count FROM totals_final WHERE year = ? AND geography = 'citywide' AND measure = 'total'", dy)
    else:
        row = q(f"SELECT SUM(count) FROM offenses_final WHERE year = ? AND geography = 'citywide' "
                f"AND subtype IS NULL AND {chart_map[cat]}", dy)
    table_val = row[0][0] if row else None
    if table_val != chart:
        results["Chart value != table value"].append(
            f"report {ry} chart, {dy} {cat}: chart={chart}, table (own-year report)={table_val}")

# 8. Enforcement totals equal their parts
for group, parts in (("ARRESTS", ("JUVENILE", "ADULT")), ("CITATIONS", ("PARKING", "STATE"))):
    for ry, dy, printed, computed in q(f"""
        SELECT t.report_year, t.data_year, t.count, SUM(p.count) FROM enforcement t JOIN enforcement p
          ON p.report_year = t.report_year AND p.data_year = t.data_year
         AND p.measure IN ('{group}_{parts[0]}', '{group}_{parts[1]}')
        WHERE t.measure = '{group}_TOTAL' GROUP BY 1, 2, 3 HAVING t.count != SUM(p.count)"""):
        results["Enforcement total != sum of parts"].append(
            f"report {ry}, {dy} {group}_TOTAL: printed={printed}, sum={computed}")

lines = []
for check, items in results.items():
    lines.append(f"\n== {check} ({len(items)})")
    lines += [f"  {i}" for i in items]
if not results:
    lines.append("All checks passed.")
out = "\n".join(lines).lstrip("\n")
print(out)
REPORT_PATH.write_text(out + "\n")
