# extractors/image_ocr_extractor.py
# חילוץ עם OCR (Tesseract/EasyOCR או Textract) כשאין טקסט ב-PDF או כשקלט תמונה.

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any

from .base_extractor import BaseExtractor, ExtractionResult
from invoice2claude_utils import (
    run_ocr_with_preproc,
    parse_intro_from_text,
    parse_main_from_text,
    compute_hash,
)

IMG_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".pdf"}  # כולל PDF סרוק

class ImageOCRExtractor(BaseExtractor):
    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in IMG_EXTS

    def extract(self, file_path: Path) -> ExtractionResult:
        # OCR עם קדם-עיבוד בסיסי
        text, boxes = run_ocr_with_preproc(file_path, self.config)

        # פרסרי טקסט (מינימליים; הסטאבים נמצאים ב-invoice2claude_utils.py)
        intro_raw: Dict[str, Any] = parse_intro_from_text(text, self.config) or {}
        lines_raw, final_raw = parse_main_from_text(text, self.config)
        lines_raw = lines_raw or []
        final_raw = final_raw or {}

        prov = {
            "engine": "ocr",
            "ocr": self.config.get("ocr_engine", "tesseract"),
            "sha256": compute_hash(file_path),
        }

        return ExtractionResult(
            intro_raw=intro_raw,
            lines_raw=lines_raw,
            final_raw=final_raw,
            extracted_text=text,
            boxes=boxes or {},
            provenance=prov,
        )
