# validation/schemas.py
# מגדיר סכמות קשיחות (Pydantic) לחשבונית ולשורותיה עם Decimal ותיקוני ערכים בסיסיים.

from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal, InvalidOperation
from typing import List, Optional
from datetime import date
import re

def _to_decimal(v) -> Decimal:
    if v is None or v == "":
        return Decimal("0")
    s = str(v).strip().replace(",", ".")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        raise ValueError(f"Invalid decimal: {v}")

class LineItem(BaseModel):
    line_no: int = Field(ge=1)
    barcode: Optional[str] = None
    item_code: Optional[str] = None
    description: str
    qty: Decimal
    unit_price: Decimal
    discount_pct: Decimal = Decimal("0")
    price_after_discount: Optional[Decimal] = None
    vat_pct: Decimal = Decimal("17")
    line_total: Decimal

    @field_validator("description", mode="before")
    @classmethod
    def _clean_desc(cls, v: str):
        v = str(v or "").strip()
        v = re.sub(r"\s+", " ", v)
        if not v:
            raise ValueError("Empty description")
        return v

    @field_validator("qty", "unit_price", "discount_pct", "price_after_discount", "vat_pct", "line_total", mode="before")
    @classmethod
    def _decimals(cls, v):
        return _to_decimal(v)

class InvoiceIntro(BaseModel):
    supplier_name: Optional[str] = None
    supplier_vat_id: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    currency: Optional[str] = "ILS"
    customer_name: Optional[str] = None

class InvoiceFinal(BaseModel):
    subtotal: Decimal
    vat_amount: Decimal
    total: Decimal

    @field_validator("subtotal", "vat_amount", "total", mode="before")
    @classmethod
    def _dec(cls, v): 
        return _to_decimal(v)

class Invoice(BaseModel):
    intro: Optional[InvoiceIntro] = None
    lines: List[LineItem]
    final: Optional[InvoiceFinal] = None