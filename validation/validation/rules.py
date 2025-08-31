# validation/rules.py
# מגדיר חוקים דטרמיניסטיים לבדיקה עסקית: סכומים, מע״מ, הנחות, טווחים.

from __future__ import annotations
from decimal import Decimal
from typing import Dict, List
from .schemas import Invoice

TOLERANCE = Decimal("0.05")
DEFAULT_VAT = Decimal("17")

Issue = Dict[str, str]

def _approx_equal(a: Decimal, b: Decimal, tol: Decimal = TOLERANCE) -> bool:
    return (a - b).copy_abs() <= tol

def check_line_totals(inv: Invoice) -> List[Issue]:
    issues: List[Issue] = []
    for i, line in enumerate(inv.lines):
        expected = (line.qty * line.unit_price * (Decimal("1") - line.discount_pct/Decimal("100")))
        if not _approx_equal(line.line_total, expected):
            issues.append({
                "code": "E-LINE-TOTAL-MISMATCH",
                "severity": "ERROR",
                "path": f"lines[{i}].line_total",
                "found": str(line.line_total),
                "expected": str(expected.quantize(Decimal('0.01'))),
                "message": "Line total does not match qty×price×(1-discount)."
            })
    return issues

def check_subtotals(inv: Invoice) -> List[Issue]:
    if not inv.final:
        return []
    issues: List[Issue] = []
    sum_lines = sum([l.line_total for l in inv.lines], Decimal("0"))
    if not _approx_equal(inv.final.subtotal, sum_lines):
        issues.append({
            "code": "E-SUBTOTAL-MISMATCH",
            "severity": "ERROR",
            "path": "final.subtotal",
            "found": str(inv.final.subtotal),
            "expected": str(sum_lines.quantize(Decimal('0.01'))),
            "message": "Subtotal differs from sum of line totals."
        })
    total_expected = inv.final.subtotal + inv.final.vat_amount
    if not _approx_equal(inv.final.total, total_expected):
        issues.append({
            "code": "E-TOTAL-MISMATCH",
            "severity": "ERROR",
            "path": "final.total",
            "found": str(inv.final.total),
            "expected": str(total_expected.quantize(Decimal('0.01'))),
            "message": "Total differs from subtotal + VAT amount."
        })
    return issues

def check_vat_reasonableness(inv: Invoice) -> List[Issue]:
    issues: List[Issue] = []
    for i, line in enumerate(inv.lines):
        if line.vat_pct < 0 or line.vat_pct > 100:
            issues.append({
                "code": "E-VAT-RATE",
                "severity": "ERROR",
                "path": f"lines[{i}].vat_pct",
                "found": str(line.vat_pct),
                "expected": "0–100",
                "message": "VAT percent out of range."
            })
        elif line.vat_pct != DEFAULT_VAT:
            issues.append({
                "code": "W-VAT-UNUSUAL",
                "severity": "WARN",
                "path": f"lines[{i}].vat_pct",
                "found": str(line.vat_pct),
                "expected": str(DEFAULT_VAT),
                "message": "VAT percent differs from default."
            })
    return issues

def check_discounts(inv: Invoice) -> List[Issue]:
    issues: List[Issue] = []
    for i, line in enumerate(inv.lines):
        if line.discount_pct < 0 or line.discount_pct > 100:
            issues.append({
                "code": "E-DISCOUNT-RANGE",
                "severity": "ERROR",
                "path": f"lines[{i}].discount_pct",
                "found": str(line.discount_pct),
                "expected": "0–100",
                "message": "Discount percent out of range."
            })
        elif line.discount_pct > 90:
            issues.append({
                "code": "W-DISCOUNT-HIGH",
                "severity": "WARN",
                "path": f"lines[{i}].discount_pct",
                "found": str(line.discount_pct),
                "expected": "≤ 90",
                "message": "Unusually high discount."
            })
    return issues

def run_all_rules(inv: Invoice) -> List[Issue]:
    issues: List[Issue] = []
    issues += check_line_totals(inv)
    issues += check_subtotals(inv)
    issues += check_vat_reasonableness(inv)
    issues += check_discounts(inv)
    return issues
