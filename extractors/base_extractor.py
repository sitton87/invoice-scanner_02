# extractors/base_extractor.py
# ממשק בסיס לכל Extractor: מקבל path + קונפיג, מחזיר Draftים + מטא-דאטה.

from __future__ import annotations
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

@dataclass
class ExtractionResult:
    intro_raw: Optional[Dict[str, Any]]
    lines_raw: Optional[Any]               # יכול להיות list[dict] או טבלה לפני מיפוי
    final_raw: Optional[Dict[str, Any]]
    extracted_text: Optional[str]          # אם קיים (OCR)
    boxes: Optional[Dict[str, Any]]        # bbox לשדות/טבלאות אם יש
    provenance: Dict[str, Any]             # engine, version, params, file hash

class BaseExtractor:
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def can_handle(self, file_path: Path) -> bool:
        raise NotImplementedError

    def extract(self, file_path: Path) -> ExtractionResult:
        raise NotImplementedError
