import json
import sqlite3
from pathlib import Path
import pandas as pd

DB = Path("data/frontieratlas.db")
OUT = Path("data/export")
OUT.mkdir(parents=True, exist_ok=True)


def export_all():
    con = sqlite3.connect(DB)
    rows = pd.read_sql_query("SELECT record_type,payload FROM records", con)
    maps = pd.read_sql_query("SELECT raw_name,canonical_name,entity_type,method,score FROM mappings", con)
    con.close()
    for typ in ["STARTUP","PRODUCT","RESEARCH_PAPER","JOB","NEWS"]:
        subset = rows[rows.record_type == typ].copy()
        if subset.empty:
            continue
        records = []
        for p in subset.payload:
            try: records.append(json.loads(p))
            except Exception: pass
        pd.json_normalize(records).to_csv(OUT / f"{typ.lower()}s.csv", index=False)
    maps.to_csv(OUT / "entity_mapping_log.csv", index=False)
    # One workbook with the six requested tabs.
    xlsx = OUT / "frontieratlas_output.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
        for typ, sheet in [("STARTUP","Startups"),("PRODUCT","Products"),("RESEARCH_PAPER","Research Papers"),("JOB","Jobs"),("NEWS","News")]:
            subset = rows[rows.record_type == typ]
            records = [json.loads(p) for p in subset.payload]
            pd.json_normalize(records).to_excel(writer, sheet_name=sheet, index=False)
        maps.to_excel(writer, sheet_name="Entity Mapping Log", index=False)
    return xlsx
