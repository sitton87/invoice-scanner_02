# validation/validator.py
# מריץ את כללי הוולידציה העסקית על חשבונית, מחזיר issues, ציון וסטטוס.

from __future__ import annotations
from typing import Any, Dict, List
from .schemas import Invoice
from .rules import run_all_rules

SEVERITY_WEIGHTS = {"ERROR": 10, "WARN": 3, "INFO": 0}

class BusinessValidator:
    @staticmethod
    def _score(issues: List[Dict[str, str]]) -> int:
        penalty = sum(SEVERITY_WEIGHTS.get(i["severity"], 0) for i in issues)
        score = max(0, 100 - penalty)
        return score

    @staticmethod
    def validate(invoice_json: Dict[str, Any]) -> Dict[str, Any]:
        inv = Invoice.model_validate(invoice_json)
        issues = run_all_rules(inv)
        score = BusinessValidator._score(issues)
        status = "PASS" if score >= 90 and not any(i["severity"] == "ERROR" for i in issues) else \
                 "REVIEW" if score >= 70 else "FAIL"
        return {"issues": issues, "score": score, "status": status}
