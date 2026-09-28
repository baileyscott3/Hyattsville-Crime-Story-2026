# Data notes: Hyattsville City PD annual statistics, 2015–2025

Source: 11 annual statistics reports from Hyattsville PD website (https://www.hyattsville.org/Archive.aspx?AMID=38). The 2015–2021 files are scans and were hand-transcribed into `transcribed/`. The 2022–2025 files have a text layer and were extracted by `scripts/extract_text_pdfs.py` into `extracted/`. `scripts/validate.py` checks every number. Its full output is in `validation_report.txt`.

## How the transcriptions were verified
- For the scanned years, every printed % change matches the % change recomputed from the transcribed counts (see the exceptions below). Every parent row matches its subtypes, every ward row matches its total, and every subtotal matches its parts, except where the source document itself disagrees (listed below).
- The prior-year column in each report was compared against that year's own report.

## Things to know before using the numbers
- **Which figure to use:** the `*_final` views and the `data/*.csv` exports use each year's figure **from its own report**. Figures printed later as the "prior year" are kept in `offenses_all_reports.csv` and in the `report_year`/`data_year` columns of the database.
- **No ward tables for 2023 or 2024.** Those reports have no ward page.
- **No 2016 calls for service in the 2016 report.** The 2017 report gives 24,945 for 2016 (`calls_for_service` table, report_year 2017).
- **Citizen- vs. officer-initiated call shares** appear only in the 2015 report.
- **"Robbery" in the city's charts** = commercial robbery + citizen robbery + carjacking.

## Errors in the source documents (confirmed against the PDFs)
| Report | Issue |
|---|---|
| 2015 | Citizen robbery = 43, but the weapon subtypes add up to 42 (citywide and ward tables; Ward 3 = 15 vs. subtypes 14). The 2016 report's prior-year column revises the subtypes to 16/5/3/19, which does add up to 43. |
| 2022 | The ward table's weapon breakdowns don't match the citywide table: citizen robbery/knife 5 vs. 3, assault/other weapon 11 vs. 12, assault/no weapon 100 vs. 99. Ward 5 citizen robbery = 9, but its subtypes add up to 11. The parent totals agree. |
| 2022 | State citations: printed +183.85% and an "actual change" of 3,859. The real change is 2,099 → 3,690 = +75.8% (+1,591). |
| 2023 | "Actual change" signs are flipped for arrest totals (−31, should be +31) and citation totals (1,341, should be −1,341). |
| 2022 | The five-year chart plots 2019 far too low (theft bar at about 200; the real figure is 996). |
| Many | When either year is 0, the % change column prints (difference × 100)%, for example 2 → 0 printed as −200% and 0 → 4 as +400%. **Don't quote the printed % change for these rows.** The list is in `validation_report.txt`. |

## Figures revised in a later report
Some figures differ between a year's own report and the next year's prior-year column. Ask the department which is correct before publishing any of these:

| Year | Measure | Own report | Next report |
|---|---|---|---|
| 2015 | Citizen robbery knife / other weapon / strong arm | 4 / 4 / 18 | 5 / 3 / 19 |
| 2015 | Canine activity reports | 53 | 47 |
| 2015 | Red light citations | 4,918 | 4,915 |
| 2017 | Calls for service | 25,277 | 24,442 |
| 2018 | Calls for service | 23,546 | 23,859 |
| 2019 | Adult arrests (total) | 688 (781) | 684 (777) |
| 2020 | Juvenile / adult arrests (total) | 40 / 358 (398) | 41 / 382 (423) |
| 2024 | Theft (property subtotal, total crimes) | 464 (685, 910) | 465 (686, 911) |
| 2024 | Adult arrests (total) | 351 (393) | 359 (401) |

## Questions for HCPD
- The revisions above: are later figures updated counts, and should they replace the originals?
- The 2022 ward-table discrepancies.
- Whether ward boundaries changed during 2015–2025 (this matters for any ward-level comparison over time).
- Whether offense definitions or the records system changed (for example, the jump in stolen vehicles to 314 in 2023).
