# --- ADD/ENSURE imports at top of invoice2claude_utils.py ---
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import hashlib
import re
import io
import cv2
import numpy as np
import pytesseract
from PIL import Image

# ---------- HASH ----------
def compute_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

# ---------- TABLE EXTRACT (Camelot/Tabula) ----------
def table_extract(file_path: Path) -> List[Dict[str, Any]]:
    """
    ניסיון לחילוץ טבלאות מ-PDF:
    1) Camelot flavor=lattice → stream
    2) Fallback: tabula-py
    מחזיר רשימת שורות (dict) עם כותרות מקוריות. במקרה כישלון – [].
    """
    rows: List[Dict[str, Any]] = []

    # Camelot
    try:
        import camelot  # type: ignore
        # lattice (יש קווי טבלה)
        tables = camelot.read_pdf(str(file_path), flavor="lattice", pages="all")
        for t in (tables or []):
            rows.extend(_camelot_table_to_rows(t.df))
        if rows:
            return rows
        # stream (אין קווי טבלה)
        tables = camelot.read_pdf(str(file_path), flavor="stream", pages="all")
        for t in (tables or []):
            rows.extend(_camelot_table_to_rows(t.df))
        if rows:
            return rows
    except Exception:
        pass

    # Tabula fallback
    try:
        import tabula  # type: ignore
        dfs = tabula.read_pdf(str(file_path), pages="all", multiple_tables=True)
        for df in (dfs or []):
            rows.extend(_pandas_df_to_rows(df))
    except Exception:
        pass

    return rows

def _camelot_table_to_rows(df) -> List[Dict[str, Any]]:
    try:
        import pandas as pd  # type: ignore
    except Exception:
        return []
    # Camelot מחזיר DataFrame; השורה הראשונה ככותרות
    if not hasattr(df, "iloc"):
        # במקרה של אובייקט Camelot Table עם df אחר
        try:
            df = df.to_pandas()
        except Exception:
            return []
    df = df.fillna("").astype(str)
    if df.empty:
        return []
    headers = [str(h).strip() for h in list(df.iloc[0, :])]
    body = df.iloc[1:, :].reset_index(drop=True)
    body.columns = headers
    return _pandas_df_to_rows(body)

def _pandas_df_to_rows(df) -> List[Dict[str, Any]]:
    try:
        import pandas as pd  # type: ignore
    except Exception:
        return []
    if not isinstance(df, pd.DataFrame):
        return []
    df = df.fillna("").astype(str)
    rows: List[Dict[str, Any]] = []
    for _, r in df.iterrows():
        row = {str(k).strip(): str(v).strip() for k, v in r.items()}
        if any(v for v in row.values()):
            rows.append(row)
    return rows

# ---------- HEADER MAP + NORMALIZE ----------
try:
    from rapidfuzz import process as _fuzz  # type: ignore
except Exception:
    _fuzz = None

_CANON_HEADERS = {
    "line_no": ["#", "מס", "שורה", "מספר"],
    "sku": ["מק\"ט", "ברקוד", "מק\"ט/ברקוד", "קוד"],
    "description": ["תיאור", "פריט", "שם מוצר", "מוצר"],
    "qty": ["כמות", "מספר יח'", "יחידות"],
    "unit_price": ["מחיר", "מחיר יח'", "מחיר ליחידה"],
    "discount_pct": ["הנחה", "% הנחה", "הנחה %"],
    "line_total": ["סה\"כ", "סהכ", "סכום שורה", "סכום"],
}

def header_map(rows: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    def _canon_name(src: str, thresh: int = 75) -> str:
        if not _fuzz:
            return src
        best = (None, 0)
        for canon, aliases in _CANON_HEADERS.items():
            m = _fuzz.extractOne(src, aliases)
            if m and m[1] > best[1]:
                best = (canon, m[1])
        return best[0] if best[1] >= thresh else src

    mapped: List[Dict[str, Any]] = []
    for row in rows:
        new_row: Dict[str, Any] = {}
        for k, v in row.items():
            canon = _canon_name(str(k))
            new_row[canon] = _normalize_value(canon, v)
        mapped.append(new_row)
    return mapped

def _normalize_value(field: str, v: Any):
    if v is None:
        return None
    s = str(v).strip()
    if field in ("qty", "unit_price", "discount_pct", "line_total", "price_after_discount"):
        s = s.replace(",", ".")
        s = re.sub(r"[^\d.\-]", "", s)  # הסר ₪/רווחים/טקסט
        return s
    return s

def _strip_num(s: str) -> str:
    s = s.strip().replace(",", ".")
    s = re.sub(r"[^\d.\-]", "", s)
    return s

# ---------- OCR FUNCTIONS ----------
def run_ocr_with_preproc(file_path, config):
    """
    Run OCR with preprocessing on image/PDF file.
    Returns (extracted_text, boxes_dict)
    """
    try:
        # Convert path to string
        file_path_str = str(file_path)
        
        # Handle PDF by converting first page to image
        if file_path_str.lower().endswith('.pdf'):
            import fitz  # PyMuPDF
            doc = fitz.open(file_path_str)
            page = doc[0]  # First page
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            doc.close()
        else:
            # Load image
            img = Image.open(file_path_str)
        
        # Convert PIL to OpenCV format
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        
        # Basic preprocessing
        img_processed = _preprocess_image_for_ocr(img_cv)
        
        # OCR engine selection
        ocr_engine = config.get("ocr_engine", "tesseract")
        
        if ocr_engine.lower() == "tesseract":
            # Use Tesseract
            text = pytesseract.image_to_string(img_processed, lang='heb+eng')
            # Get bounding boxes (optional)
            boxes = {}
            try:
                data = pytesseract.image_to_data(img_processed, output_type=pytesseract.Output.DICT)
                boxes = {"words": data}
            except:
                pass
        else:
            # Fallback to basic OCR
            text = pytesseract.image_to_string(img_processed, lang='heb+eng')
            boxes = {}
        
        return text, boxes
        
    except Exception as e:
        # Fallback - try without preprocessing
        try:
            img = Image.open(str(file_path))
            text = pytesseract.image_to_string(img, lang='heb+eng')
            return text, {}
        except:
            raise RuntimeError(f"OCR failed: {str(e)}")

def _preprocess_image_for_ocr(img_cv):
    """Basic image preprocessing for better OCR results"""
    try:
        # Convert to grayscale
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (1, 1), 0)
        
        # Apply threshold to get binary image
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Morphological operations to clean up
        kernel = np.ones((1, 1), np.uint8)
        processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return processed
        
    except Exception:
        # If preprocessing fails, return original
        return img_cv

# ---------- TEXT PARSING FUNCTIONS ----------
def parse_intro_from_text(text, config):
    """
    Parse invoice intro/header information from extracted text.
    Returns dict with invoice details.
    """
    intro = {}
    
    if not text:
        return intro
    
    # Invoice number
    patterns = [
        r"(?:חשבונית|Invoice|מס['\"]?\s*חשבונית)[^\d]{0,10}(\d{4,})",
        r"(?:Invoice\s*#|חשבונית\s*מס['\"]?)[^\d]{0,5}(\d{4,})",
        r"(?:מספר|מס['\"]?)\s*(\d{4,})"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            intro["invoice_number"] = match.group(1)
            break
    
    # Date patterns
    date_patterns = [
        r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
        r"(\d{4}[./-]\d{1,2}[./-]\d{1,2})"
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            intro["invoice_date"] = match.group(1)
            break
    
    # Customer info (basic)
    customer_patterns = [
        r"לכבוד[:\s]*([^\n\r]{5,50})",
        r"ללקוח[:\s]*([^\n\r]{5,50})",
        r"(?:Customer|Client)[:\s]*([^\n\r]{5,50})"
    ]
    
    for pattern in customer_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            intro["customer_name"] = match.group(1).strip()
            break
    
    return intro

def parse_main_from_text(text, config):
    """
    Parse main invoice items from extracted text.
    Returns (lines_list, final_totals_dict)
    """
    lines = []
    final = {}
    
    if not text:
        return lines, final
    
    # Try to find table-like structures
    text_lines = text.split('\n')
    
    # Look for lines that might contain item data
    item_lines = []
    for line in text_lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if line contains numbers and text (potential item line)
        if re.search(r'\d+', line) and len(line) > 10:
            # Check for price-like patterns
            if re.search(r'\d+[\.,]\d{2}', line):
                item_lines.append(line)
    
    # Parse each potential item line
    line_number = 1
    for line in item_lines:
        item = _parse_single_item_line(line, line_number)
        if item:
            lines.append(item)
            line_number += 1
    
    # Parse totals
    final = _parse_totals_from_text(text)
    
    return lines, final

def _parse_single_item_line(line, line_num):
    """Parse a single item line"""
    item = {"line": line_num}
    
    # Find all numbers in the line
    numbers = re.findall(r'\d+[\.,]?\d*', line)
    
    if not numbers:
        return None
    
    # Try to extract description (text before first large number)
    desc_match = re.search(r'^(.*?)(?=\d{3,}|\d+[\.,]\d{2})', line)
    if desc_match:
        description = desc_match.group(1).strip()
        # Clean up description
        description = re.sub(r'^\d+\s*', '', description)  # Remove leading numbers
        if description:
            item["description"] = description
    
    # Extract price-like numbers (with decimal)
    prices = re.findall(r'\d+[\.,]\d{2}', line)
    if prices:
        # Last price is usually total
        item["total_amount"] = prices[-1].replace(',', '.')
        if len(prices) > 1:
            item["unit_price"] = prices[0].replace(',', '.')
    
    # Extract quantity (usually first small number)
    qty_candidates = [n for n in numbers if '.' not in n and ',' not in n and len(n) <= 3]
    if qty_candidates:
        try:
            qty = int(qty_candidates[0])
            if 1 <= qty <= 999:  # Reasonable quantity range
                item["quantity"] = qty
        except:
            pass
    
    return item if len(item) > 1 else None

def _parse_totals_from_text(text):
    """Parse total amounts from text"""
    final = {}
    
    # Subtotal patterns
    subtotal_patterns = [
        r"(?:סכום ביניים|Subtotal|סכום חלקי)[^\d]{0,10}([\d,.\s]+)",
        r"(?:סה\"כ לפני מע\"מ)[^\d]{0,10}([\d,.\s]+)"
    ]
    
    for pattern in subtotal_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            final["subtotal"] = _clean_amount(match.group(1))
            break
    
    # VAT patterns
    vat_patterns = [
        r"(?:מע\"מ|VAT|מעמ)[^\d]{0,10}([\d,.\s]+)",
        r"(?:מס ערך מוסף)[^\d]{0,10}([\d,.\s]+)"
    ]
    
    for pattern in vat_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            final["vat_amount"] = _clean_amount(match.group(1))
            break
    
    # Total patterns
    total_patterns = [
        r"(?:סה\"כ לתשלום|Total|סכום לתשלום)[^\d]{0,10}([\d,.\s]+)",
        r"(?:סה\"כ|סהכ)[^\d]{0,10}([\d,.\s]+)"
    ]
    
    for pattern in total_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            final["total"] = _clean_amount(match.group(1))
            break
    
    return final

def _clean_amount(amount_str):
    """Clean and normalize amount string"""
    if not amount_str:
        return ""
    
    # Remove currency symbols and extra spaces
    cleaned = re.sub(r'[₪$€£\s]', '', amount_str.strip())
    # Replace comma with dot for decimal
    cleaned = cleaned.replace(',', '.')
    # Keep only digits, dots, and minus
    cleaned = re.sub(r'[^\d.\-]', '', cleaned)
    
    return cleaned

# ---------- INTRO/FINAL from PDF text ----------
def parse_intro_final_with_regex(file_path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    קורא טקסט מ-PDF (pdfplumber) ומחלץ שדות בסיסיים ב-regex.
    מחזיר (intro_raw, final_raw). מימוש מינימלי – אפשר להרחיב בקלות.
    """
    intro = {}
    final = {}

    try:
        import pdfplumber  # type: ignore
    except Exception:
        return intro, final

    # קריאת טקסט מכל העמודים
    texts = []
    with pdfplumber.open(str(file_path)) as pdf:
        for p in pdf.pages:
            t = p.extract_text() or ""
            if t:
                texts.append(t)
    full = "\n".join(texts)

    # מס' חשבונית (דוגמאות: חשבונית 12345, Invoice #12345)
    m = re.search(r"(?:חשבונית|Invoice)[^\d]{0,5}(\d{4,})", full, re.I)
    if m:
        intro["invoice_number"] = m.group(1)

    # תאריך (פשוט; נשתמש ב-dateparser בהמשך אם נרצה)
    m = re.search(r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})", full)
    if m:
        try:
            from dateparser import parse as date_parse  # type: ignore
            dt = date_parse(m.group(1), languages=["he", "en"])
            if dt:
                intro["invoice_date"] = dt.date().isoformat()
        except Exception:
            intro["invoice_date"] = m.group(1)

    # סכומי סיכום (מינימלי; אפשר לדייק מאוחר יותר)
    # Subtotal
    m = re.search(r"(?:Subtotal|סכום ביניים)[^\d]{0,10}([\d,.\s]+)", full, re.I)
    if m:
        final["subtotal"] = _strip_num(m.group(1))
    # VAT amount
    m = re.search(r"(?:VAT|מע[\"']?מ)[^\d]{0,10}([\d,.\s]+)", full, re.I)
    if m:
        final["vat_amount"] = _strip_num(m.group(1))
    # Total
    m = re.search(r"(?:Total|סה\"כ|סך הכל)[^\d]{0,10}([\d,.\s]+)", full, re.I)
    if m:
        final["total"] = _strip_num(m.group(1))

    return intro, final