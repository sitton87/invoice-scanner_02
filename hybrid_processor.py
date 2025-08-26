"""
hybrid_processor.py - מעבד היברידי על בסיס המתודולוגיה המומלצת
"""

import fitz  # PyMuPDF
import pdfplumber
import pytesseract
from PIL import Image
import cv2
import numpy as np
from pathlib import Path
import anthropic
import json
import io
import imutils
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

class HybridInvoiceProcessor:
    """מעבד היברידי לחשבוניות - OCR + Text Extraction"""
    
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    def process_invoice(self, file_path, progress_callback=None):
        """עיבוד חשבונית עם זיהוי אוטומטי של סוג התוכן"""
        try:
            file_path = Path(file_path)
            
            if progress_callback:
                progress_callback("מזהה סוג קובץ ותוכן...")
            
            # שלב 1: זיהוי סוג הקובץ
            if file_path.suffix.lower() == '.pdf':
                text_content = self._process_pdf_hybrid(file_path, progress_callback)
            else:
                # תמונה - ישר ל-OCR
                if progress_callback:
                    progress_callback("קובץ תמונה - מעבר ל-OCR...")
                text_content = self._process_image_ocr(file_path, progress_callback)
            
            # שלב 2: עיבוד עם Claude
            if progress_callback:
                progress_callback("מעבד נתונים עם Claude...")
            
            structured_data = self._process_with_claude(text_content)
            
            return {
                "success": True,
                "json_data": structured_data,
                "extracted_text": text_content,
                "method_used": self.last_method_used,
                "message": "עיבוד הושלם בהצלחה!"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"שגיאה בעיבוד: {str(e)}"
            }
    
    def _process_pdf_hybrid(self, pdf_path, progress_callback=None):
        """עיבוד PDF היברידי - text extraction או OCR"""
        
        # שלב 1: בדיקה אם יש טקסט בחירה
        try:
            if progress_callback:
                progress_callback("בודק אם PDF מכיל טקסט בחירה...")
            
            with pdfplumber.open(pdf_path) as pdf:
                # נבדוק את העמוד הראשון
                first_page = pdf.pages[0]
                sample_text = first_page.extract_text()
                
                if sample_text and len(sample_text.strip()) > 100:
                    # יש טקסט בחירה - נשתמש ב-pdfplumber
                    if progress_callback:
                        progress_callback("נמצא טקסט בחירה - מחלץ עם pdfplumber...")
                    
                    self.last_method_used = "pdfplumber_text_extraction"
                    return self._extract_text_with_pdfplumber(pdf_path)
                else:
                    # אין טקסט בחירה או מעט מידי - מעבר ל-OCR
                    if progress_callback:
                        progress_callback("לא נמצא טקסט בחירה מספיק - מעבר ל-OCR...")
                    
                    self.last_method_used = "ocr_scanned_pdf"
                    return self._process_pdf_with_ocr(pdf_path, progress_callback)
                    
        except Exception:
            # אם pdfplumber נכשל - מעבר ל-OCR
            if progress_callback:
                progress_callback("pdfplumber נכשל - מעבר ל-OCR...")
            
            self.last_method_used = "ocr_fallback"
            return self._process_pdf_with_ocr(pdf_path, progress_callback)
    
    def _extract_text_with_pdfplumber(self, pdf_path):
        """חילוץ טקסט עם pdfplumber (לPDFs עם טקסט בחירה)"""
        try:
            extracted_text = []
            
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        extracted_text.append(f"=== עמוד {page_num + 1} ===")
                        extracted_text.append(page_text)
                    
                    # ניסיון לחלץ גם טבלאות אם קיימות
                    tables = page.extract_tables()
                    if tables:
                        extracted_text.append(f"\n=== טבלאות מעמוד {page_num + 1} ===")
                        for i, table in enumerate(tables):
                            extracted_text.append(f"טבלה {i + 1}:")
                            for row in table:
                                if row:
                                    extracted_text.append(" | ".join([str(cell) if cell else "" for cell in row]))
            
            return "\n".join(extracted_text)
            
        except Exception as e:
            raise ValueError(f"שגיאה בחילוץ טקסט עם pdfplumber: {str(e)}")
    
    def _process_pdf_with_ocr(self, pdf_path, progress_callback=None):
        """עיבוד PDF עם OCR (לסקנים)"""
        try:
            # המרה לתמונות
            if progress_callback:
                progress_callback("ממיר PDF לתמונות...")
            
            pdf_document = fitz.open(pdf_path)
            images = []
            
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                img_array = np.array(img)
                
                if len(img_array.shape) == 3:
                    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                
                images.append(img_array)
            
            pdf_document.close()
            
            # איחוד תמונות
            combined_image = self._combine_images_vertically(images)
            
            # OCR עם תיקון סיבוב
            return self._ocr_with_rotation_fix(combined_image, progress_callback)
            
        except Exception as e:
            raise ValueError(f"שגיאה בעיבוד PDF עם OCR: {str(e)}")
    
    def _process_image_ocr(self, image_path, progress_callback=None):
        """עיבוד תמונה עם OCR"""
        try:
            # טעינת תמונה
            image = cv2.imread(str(image_path))
            if image is None:
                raise ValueError("לא ניתן לטעון את התמונה")
            
            # המרה לגרייסקייל
            if len(image.shape) == 3:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # עיבוד והשבחה
            processed_image = self._preprocess_image_for_ocr(image)
            
            # OCR עם תיקון סיבוב
            self.last_method_used = "ocr_image"
            return self._ocr_with_rotation_fix(processed_image, progress_callback)
            
        except Exception as e:
            raise ValueError(f"שגיאה בעיבוד תמונה: {str(e)}")
    
    def _ocr_with_rotation_fix(self, image, progress_callback=None):
        """OCR עם תיקון סיבוב - הקוד שפיתחנו קודם"""
        try:
            # תיקון סיבוב
            if progress_callback:
                progress_callback("מתקן סיבוב תמונה...")
            
            corrected_image = self._auto_rotate_image(image, progress_callback)
            
            # OCR
            if progress_callback:
                progress_callback("מבצע OCR...")
            
            # ניסיונות OCR מרובים
            text_results = []
            
            # ניסיון 1: עברית + אנגלית
            try:
                text1 = pytesseract.image_to_string(
                    corrected_image, 
                    lang='heb+eng', 
                    config='--psm 6 -c preserve_interword_spaces=1'
                )
                if text1.strip():
                    text_results.append("=== OCR עברית+אנגלית ===")
                    text_results.append(text1)
            except:
                pass
            
            # ניסיון 2: PSM לטבלאות
            try:
                text2 = pytesseract.image_to_string(
                    corrected_image, 
                    lang='heb+eng', 
                    config='--psm 4'
                )
                if text2.strip():
                    text_results.append("\n=== OCR PSM 4 (טבלאות) ===")
                    text_results.append(text2)
            except:
                pass
            
            return "\n".join(text_results) if text_results else "לא הצלחתי לחלץ טקסט"
            
        except Exception as e:
            raise ValueError(f"שגיאה ב-OCR: {str(e)}")
    
    def _auto_rotate_image(self, image, progress_callback=None):
        """תיקון סיבוב - הקוד שפיתחנו קודם"""
        try:
            from pytesseract import Output
            
            # זיהוי כיוון
            try:
                if len(image.shape) == 2:
                    rgb_image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
                else:
                    rgb_image = image
                
                osd_result = pytesseract.image_to_osd(
                    rgb_image, 
                    config='--psm 0 -c min_characters_to_try=5',
                    output_type=Output.DICT
                )
                
                detected_angle = osd_result.get('rotate', 0)
                confidence = osd_result.get('orientation_conf', 0)
                
                if confidence > 1.5 and detected_angle != 0:
                    if progress_callback:
                        progress_callback(f"מסובב ב-{detected_angle}° (ביטחון: {confidence:.1f})")
                    
                    rotated = imutils.rotate_bound(rgb_image, detected_angle)
                    
                    if len(image.shape) == 2:
                        return cv2.cvtColor(rotated, cv2.COLOR_RGB2GRAY)
                    else:
                        return rotated
                
            except:
                pass
            
            return image
            
        except Exception:
            return image
    
    def _preprocess_image_for_ocr(self, image):
        """עיבוד מקדים של תמונה"""
        # הפחתת רעש
        denoised = cv2.medianBlur(image, 3)
        
        # הגברת ניגודיות
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        
        # הגדלת רזולוציה
        scale_factor = 1.2
        height, width = enhanced.shape
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        resized = cv2.resize(enhanced, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        
        return resized
    
    def _combine_images_vertically(self, images):
        """איחוד תמונות אנכית"""
        if not images:
            raise ValueError("אין תמונות לאיחוד")
        
        max_width = max(img.shape[1] for img in images)
        total_height = sum(img.shape[0] for img in images)
        
        combined = np.full((total_height, max_width), 255, dtype=np.uint8)
        
        y_offset = 0
        for img in images:
            height, width = img.shape
            x_offset = (max_width - width) // 2
            combined[y_offset:y_offset + height, x_offset:x_offset + width] = img
            y_offset += height
        
        return combined
    
    def _process_with_claude(self, text_content):
        """עיבוד עם Claude - הפרומפט המשופר שלנו"""
        prompt = f"""
חלץ את כל שורות הפריטים מהחשבונית הישראלית הזו לפורמט JSON:

{{
  "main_items": [
    {{
      "line": מספר_שורה,
      "barcode": "",
      "item_code": "מק_ט", 
      "description": "תיאור_מוצר",
      "quantity": כמות,
      "unit_price": מחיר_ליחידה,
      "discount_percent": הנחה,
      "price_after_discount": מחיר_אחרי_הנחה,
      "total_amount": סכום_שורה
    }}
  ],
  "summary": {{
    "total_lines": מספר_שורות,
    "subtotal": סכום_ביניים
  }}
}}

הטקסט:
{text_content[:4000]}

חלץ את כל השורות בטבלה!
"""
        
        response = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = response.content[0].text
        
        # חילוץ JSON
        start_pos = response_text.find('{')
        if start_pos == -1:
            raise ValueError("לא נמצא JSON בתשובה")
        
        brace_count = 0
        end_pos = start_pos
        
        for i, char in enumerate(response_text[start_pos:], start_pos):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_pos = i + 1
                    break
        
        json_text = response_text[start_pos:end_pos]
        return json.loads(json_text)


# פונקציה נוחה
def process_invoice_hybrid(file_path, progress_callback=None):
    """עיבוד היברידי של חשבונית"""
    processor = HybridInvoiceProcessor()
    return processor.process_invoice(file_path, progress_callback)

# פונקציה לתאימות עם הקוד הקיים
def process_invoice_with_ocr(file_path, progress_callback=None):
    """פונקציה לתאימות עם הקוד הקיים - מפנה למעבד היברידי"""
    return process_invoice_hybrid(file_path, progress_callback)