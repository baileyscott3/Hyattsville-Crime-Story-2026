# Hyattsville-Crime-Story-2026
Crime data story for Hyattsville Life and Times

## Data

Hyattsville City Police Department annual statistics, 2015–2025, from the PDFs in `Crime data/`.

- `data/hyattsville_crime.sqlite`: the full database (tables `offenses`, `totals`, `enforcement`, `calls_for_service`, `chart_values`; views `*_final` hold each year's figures from its own report)
- `data/*.csv`: the same data as CSV. `offenses.csv` is long format (year × geography × offense × subtype); `citywide_by_year.csv` is wide and ready to chart.
- `data/notes.md`: **read this first.** It covers source-document errors, revised figures, and gaps.

### Rebuilding

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/extract_text_pdfs.py   # 2022–2025 (text PDFs) -> extracted/
.venv/bin/python scripts/build_db.py            # transcribed/ + extracted/ -> data/
.venv/bin/python scripts/validate.py            # consistency checks -> data/validation_report.txt
```

The 2015–2021 PDFs are scans; their tables were hand-transcribed into `transcribed/`.
