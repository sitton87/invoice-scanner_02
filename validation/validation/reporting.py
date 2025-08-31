# validation/reporting.py
# מייצא את תוצאות הוולידציה העסקית כ-JSON או CSV לשימוש חיצוני/דוחות.

from __future__ import annotations
from typing import Dict, List
import json, csv
from pathlib import Path

def export_issues_json(issues: List[Dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(issues, f, ensure_ascii=False, indent=2)

def export_issues_csv(issues: List[Dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not issues:
        path.write_text("", encoding="utf-8")
        return
    keys = ["code", "severity", "path", "found", "expected", "message"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for i in issues:
            w.writerow({k: i.get(k, "") for k in keys})
