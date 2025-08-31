# extractors/pdf_text_extractor.py
# חילוץ מטקסט PDF חי: pdfplumber + Camelot/Tabula לטבלאות, בלי OCR.

from __future__ import annotations
from typing import Dict, Any, Optional
from pathlib import Path
import pdfplumber
from .base_extractor import BaseExtractor, ExtractionResult
from invoice2claude_utils import table_extract, header_map, compute_hash, parse_intro_final_with_regex

class PdfTextExtractor(BaseExtractor):
    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".pdf"

    def extract(self, file_path: Path) -> ExtractionResult:
        # נבדוק אם יש טקסט אמיתי בדף אחד לפחות
        with pdfplumber.open(str(file_path)) as pdf:
            has_text = any(page.extract_text() for page in pdf.pages)
        if not has_text:
            raise RuntimeError("PDF has no selectable text")  # זה יפיל ל-OCR במסלול הבא

        # 1) קריאת טקסט intro/final עם pdfplumber + regex
        intro_raw, final_raw = parse_intro_final_with_regex(file_path)

        # 2) טבלאות main עם Camelot/Tabula (עטפנו בפונקציית עזר table_extract)
        lines_raw = table_extract(file_path)  # list[dict] עמודות גולמיות

        # 3) מיפוי כותרות קנוני (rapidfuzz) + נרמול ערכים (Decimal/תאריכים/RTL)
        lines_raw = header_map(lines_raw, self.config)

        prov = {"engine": "pdf_text", "libraries": ["pdfplumber","camelot/tabula"], "sha256": compute_hash(file_path)}
        return ExtractionResult(intro_raw=intro_raw, lines_raw=lines_raw, final_raw=final_raw,
                                extracted_text=None, boxes=None, provenance=prov)