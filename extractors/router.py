# extractors/router.py
# בוחר Extractor לפי סוג/תכולת PDF (טקסט חי קודם, OCR רק אם נדרש).

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Type
from .base_extractor import BaseExtractor, ExtractionResult
from .pdf_text_extractor import PdfTextExtractor
from .image_ocr_extractor import ImageOCRExtractor

class ExtractionRouter:
    def __init__(self, config: Dict[str, Any]):
        self.extractors: List[BaseExtractor] = [
            PdfTextExtractor(config),     # קודם ניסיון טקסט
            ImageOCRExtractor(config),    # נפילה ל-OCR
        ]

    def run(self, file_path: Path) -> ExtractionResult:
        for ex in self.extractors:
            if ex.can_handle(file_path):
                try:
                    return ex.extract(file_path)
                except Exception:
                    # נמשיך ל-fallback אם הכישלון צפוי (למשל אין טקסט)
                    continue
        # אם הכל נכשל – נעלה חריגה מפורטת
        raise RuntimeError(f"No extractor succeeded for: {file_path}")
