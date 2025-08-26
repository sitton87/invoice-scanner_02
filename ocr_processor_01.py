"""
ocr_processor.py - מעבד OCR עם ולידציה מתקדמת לחשבוניות ישראליות
"""

import cv2
import numpy as np
from PIL import Image
import pytesseract
from pathlib import Path
import json
import anthropic
import fitz  # PyMuPDF
import io
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, validate_api_key

class OCRProcessor:
    """מעבד OCR עם ולידציה מתקדמת לחשבוניות ישראליות"""
    
    def __init__(self):
        """אתחול מעבד OCR"""
        if not validate_api_key():
            raise ValueError("מפתח API לא תקין")
        
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        print("✅ מעבד OCR הוכן בהצלחה (Tesseract + Validation)")
    
    def process_invoice_with_ocr(self, image_path, progress_callback=None):
        """עיבוד חשבונית עם OCR וולידציה"""
        try:
            if progress_callback:
                progress_callback("מכין תמונה לOCR...")
            
            # טיפול שונה ל-PDF ותמונות
            image_path = Path(image_path)
            
            if image_path.suffix.lower() == '.pdf':
                # עיבוד PDF
                processed_image = self._process_pdf_for_ocr(image_path)
            else:
                # עיבוד תמונה רגילה
                processed_image = self._preprocess_image(image_path)
            
            if progress_callback:
                progress_callback("מבצע OCR לחילוץ טקסט...")
            
            # חילוץ טקסט עם OCR
            extracted_text = self._extract_text_tesseract(processed_image)
            
            if progress_callback:
                progress_callback("שולח טקסט לClaude לניתוח...")
            
            # ניתוח הטקסט עם Claude (עם פרומפט משופר)
            result_json = self._analyze_text_with_claude(extracted_text)
            
            if progress_callback:
                progress_callback("מבצע ולידציה ותיקון נתונים...")
            
            # *** כאן מתבצעת הוולידציה החדשה ***
            validated_json = self._validate_and_fix_data(result_json, extracted_text)
            
            return {
                "success": True,
                "json_data": validated_json,
                "extracted_text": extracted_text,
                "message": "עיבוד הושלם בהצלחה עם ולידציה!"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"שגיאה בעיבוד OCR: {str(e)}"
            }
    
    def _validate_and_fix_data(self, json_data, extracted_text):
        """ולידציה ותיקון של נתונים שחולצו - זו הפונקציה החדשה!"""
        try:
            if "main_items" not in json_data:
                return json_data
            
            validation_log = []
            fixed_items = []
            
            for i, item in enumerate(json_data["main_items"]):
                fixed_item = item.copy()
                fixes_applied = []
                
                # תיקון 1: מק"ט vs ברקוד
                if self._looks_like_item_code(item.get("barcode", "")):
                    if not item.get("item_code"):
                        fixed_item["item_code"] = item.get("barcode", "")
                        fixes_applied.append("הועבר ברקוד למק\"ט")
                    fixed_item["barcode"] = ""
                    fixes_applied.append("נוקה ברקוד (לא ברקוד אמיתי)")
                
                # תיקון 2: מחיר ליחידה אם = 0
                unit_price = float(item.get("unit_price", 0))
                total_amount = float(item.get("total_amount", 0))
                quantity = float(item.get("quantity", 1))
                
                if unit_price == 0 and total_amount > 0 and quantity > 0:
                    calculated_unit_price = round(total_amount / quantity, 3)
                    fixed_item["unit_price"] = calculated_unit_price
                    fixes_applied.append(f"חושב מחיר ליחידה: {calculated_unit_price}")
                
                # תיקון 3: סכום כולל אם = 0
                elif unit_price > 0 and total_amount == 0 and quantity > 0:
                    calculated_total = round(unit_price * quantity, 2)
                    fixed_item["total_amount"] = calculated_total
                    fixes_applied.append(f"חושב סכום כולל: {calculated_total}")
                
                # תיקון 4: זיהוי כמויות מורכבות ("5 לשק" וכו')
                quantity_text = self._find_quantity_in_text(item.get("description", ""), extracted_text)
                if quantity_text:
                    parsed_quantity = self._parse_complex_quantity(quantity_text)
                    if parsed_quantity and parsed_quantity != quantity:
                        fixed_item["quantity"] = parsed_quantity
                        fixes_applied.append(f"תוקנה כמות מ-{quantity} ל-{parsed_quantity}")
                
                # תיקון 5: ולידציה בסיסית
                fixed_item = self._validate_basic_fields(fixed_item)
                
                if fixes_applied:
                    validation_log.append({
                        "line": i + 1,
                        "fixes": fixes_applied
                    })
                
                fixed_items.append(fixed_item)
            
            # עדכון הנתונים
            json_data["main_items"] = fixed_items
            
            # הוספת לוג ולידציה
            json_data["validation_log"] = validation_log
            json_data["validation_summary"] = {
                "total_items": len(fixed_items),
                "items_fixed": len(validation_log),
                "validation_completed": True
            }
            
            return json_data
            
        except Exception as e:
            # אם יש שגיאה בולידציה - נחזיר את הנתונים המקוריים
            json_data["validation_error"] = f"שגיאה בולידציה: {str(e)}"
            return json_data
    
    def _looks_like_item_code(self, value):
        """בדיקה אם זה נראה כמו מק"ט ולא ברקוד"""
        if not value or len(value) < 3:
            return False
        
        # מק"ט ישראלי טיפוסי: אותיות + מספרים
        return any(c.isalpha() for c in value) and any(c.isdigit() for c in value)
    
    def _find_quantity_in_text(self, description, full_text):
        """חיפוש ביטויי כמות בטקסט"""
        import re
        
        # דוגמאות לביטויי כמות: "5 לשק", "x50", "(x50)"
        quantity_patterns = [
            r'(\d+)\s*לשק',
            r'\(x(\d+)\)',
            r'x(\d+)',
            r'(\d+)\s*יח\'?',
        ]
        
        text_to_search = description + " " + full_text
        
        for pattern in quantity_patterns:
            matches = re.findall(pattern, text_to_search, re.IGNORECASE)
            if matches:
                return matches[0]
        
        return None
    
    def _parse_complex_quantity(self, quantity_text):
        """פרסור כמויות מורכבות"""
        try:
            # אם זה מספר פשוט
            if quantity_text.isdigit():
                return float(quantity_text)
            
            # כאן אפשר להוסיף לוגיקה מורכבת יותר
            # כמו "5 לשק" × כמות שקים
            return float(quantity_text)
            
        except:
            return None
    
    def _validate_basic_fields(self, item):
        """ולידציה בסיסית של שדות"""
        # וידוא שמספרים הם מספרים
        numeric_fields = ["quantity", "unit_price", "discount_percent", "price_after_discount", "total_amount"]
        
        for field in numeric_fields:
            try:
                if field in item:
                    item[field] = float(item[field]) if item[field] else 0.0
            except:
                item[field] = 0.0
        
        # וידוא שמחרוזות הן מחרוזות
        string_fields = ["barcode", "item_code", "description"]
        for field in string_fields:
            if field in item and item[field] is None:
                item[field] = ""
        
        return item
    
    # כל שאר הפונקציות נשארות כמו שהן...
    
    def _preprocess_image(self, image_path):
        """עיבוד מקדים של התמונה לOCR"""
        try:
            # קריאת התמונה עם PIL (יותר בטוח)
            pil_image = Image.open(image_path)
            
            # המרה ל-numpy array
            image_array = np.array(pil_image)
            
            # אם התמונה צבעונית, המר לגרייסקייל
            if len(image_array.shape) == 3:
                image_array = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
            
            # הגברת ניגודיות
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            enhanced = clahe.apply(image_array)
            
            # הגדלת רזולוציה
            scale_factor = 1.5
            height, width = enhanced.shape
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            resized = cv2.resize(enhanced, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            
            return resized
            
        except Exception as e:
            raise ValueError(f"שגיאה בעיבוד התמונה: {str(e)}")
    
    def _process_pdf_for_ocr(self, pdf_path):
        """עיבוד PDF לOCR"""
        try:
            # פתיחת ה-PDF
            pdf_document = fitz.open(pdf_path)
            
            # רשימת תמונות
            images = []
            
            # המרת כל העמודים
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
                
                # המרה ל-PIL Image
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                
                # המרה ל-numpy array
                img_array = np.array(img)
                
                # המרה לגרייסקייל אם צריך
                if len(img_array.shape) == 3:
                    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                
                images.append(img_array)
            
            pdf_document.close()
            
            if not images:
                raise ValueError("לא הצלחתי לחלץ תמונות מה-PDF")
            
            # איחוד התמונות
            combined_image = self._combine_images_vertically(images)
            
            # עיבוד התמונה המאוחדת
            return self._enhance_combined_image(combined_image)
            
        except Exception as e:
            raise ValueError(f"שגיאה בעיבוד PDF: {str(e)}")
    
    def _combine_images_vertically(self, images):
        """איחוד תמונות לתמונה אחת אנכית"""
        if not images:
            raise ValueError("אין תמונות לאיחוד")
        
        # חישוב מידות
        max_width = max(img.shape[1] for img in images)
        total_height = sum(img.shape[0] for img in images)
        
        # יצירת תמונה חדשה
        combined = np.full((total_height, max_width), 255, dtype=np.uint8)
        
        # הדבקת תמונות
        y_offset = 0
        for img in images:
            height, width = img.shape
            x_offset = (max_width - width) // 2
            combined[y_offset:y_offset + height, x_offset:x_offset + width] = img
            y_offset += height
        
        return combined
    
    def _enhance_combined_image(self, image):
        """שיפור התמונה המאוחדת"""
        # הגברת ניגודיות
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(image)
        
        # הפחתת רעש
        denoised = cv2.medianBlur(enhanced, 3)
        
        return denoised
    
    def _extract_text_tesseract(self, image):
        """חילוץ טקסט עם Tesseract בלבד"""
        try:
            extracted_texts = []
            
            # ניסיון 1: עברית + אנגלית
            try:
                text1 = pytesseract.image_to_string(image, lang='heb+eng', config='--psm 6')
                if text1.strip():
                    extracted_texts.append("=== חילוץ עם עברית ואנגלית ===")
                    extracted_texts.append(text1)
            except Exception as e:
                extracted_texts.append(f"שגיאה בחילוץ עברית: {e}")
            
            # ניסיון 2: רק אנגלית (גיבוי)
            try:
                text2 = pytesseract.image_to_string(image, lang='eng', config='--psm 6')
                if text2.strip():
                    extracted_texts.append("\n=== חילוץ עם אנגלית בלבד ===")
                    extracted_texts.append(text2)
            except Exception as e:
                extracted_texts.append(f"שגיאה בחילוץ אנגלית: {e}")
            
            # ניסיון 3: מצב OCR אחר
            try:
                text3 = pytesseract.image_to_string(image, config='--psm 3')
                if text3.strip():
                    extracted_texts.append("\n=== חילוץ עם PSM 3 ===")
                    extracted_texts.append(text3)
            except Exception as e:
                extracted_texts.append(f"שגיאה ב-PSM 3: {e}")
            
            # שילוב כל התוצאות
            final_text = "\n".join(extracted_texts)
            
            # בדיקה שחילצנו משהו שימושי
            if len(final_text.strip()) < 50:
                raise ValueError("לא הצלחתי לחלץ מספיק טקסט מהתמונה")
            
            return final_text
            
        except Exception as e:
            raise ValueError(f"שגיאה בחילוץ טקסט: {str(e)}")
    
    def _analyze_text_with_claude(self, extracted_text):
        """ניתוח הטקסט המחולץ עם Claude - עם פרומפט משופר"""
        
        # פרומפט משופר לחשבוניות ישראליות
        prompt = f"""
אתה מומחה לחילוץ נתונים מחשבוניות ישראליות. חלץ את שורות הפריטים מהטקסט הזה.

⚠️ הוראות קריטיות:
• חשבוניות בעברית נקראות מימין לשמאל
• עמודות נפוצות: ש | מק"ט | תאור מוצר | כמות | מחיר ליחידה | הנחה | מחיר אחרי הנחה | סה"כ
• מק"ט ≠ ברקוד (רוב החשבוניות אין בהן ברקוד)
• שים לב לכיוון העמודות הנכון
• אם מחיר ליחידה = 0.000 זה אומר שצריך לחשב מהסכום הכולל

יצור JSON במבנה:
{{
  "main_items": [
    {{
      "line": מספר_שורה,
      "barcode": "",
      "item_code": "מק_ט_מהעמודה_הנכונה", 
      "description": "תיאור_מלא",
      "quantity": כמות_מספרית,
      "unit_price": מחיר_ליחידה_או_0,
      "discount_percent": הנחה_באחוזים,
      "price_after_discount": מחיר_אחרי_הנחה,
      "total_amount": סכום_כולל_לשורה
    }}
  ],
  "summary": {{
    "total_lines": מספר_שורות,
    "subtotal": סכום_ביניים
  }}
}}

הטקסט המחולץ:
{extracted_text[:4000]}

חשוב: 
1. תחילה זהה את כותרות העמודות
2. ואז חלץ כל שורה לפי הסדר הנכון
3. חלץ את כל השורות - אל תדלג על כלום!
"""

        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=8000,
                messages=[
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ]
            )
            
            response_text = response.content[0].text
            return self._extract_json_from_response(response_text)
            
        except Exception as e:
            raise ValueError(f"שגיאה בניתוח עם Claude: {str(e)}")
    
    def _extract_json_from_response(self, response_text):
        """חילוץ JSON מתשובת Claude"""
        try:
            # חיפוש JSON בתשובה
            start_pos = response_text.find('{')
            if start_pos == -1:
                raise ValueError("לא נמצא JSON בתשובה")
            
            # ספירת סוגריים למציאת סוף ה-JSON
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
            
        except json.JSONDecodeError as e:
            raise ValueError(f"שגיאה בפרסור JSON: {str(e)}")


def process_invoice_with_ocr(image_path, progress_callback=None):
    """פונקציה נוחה לעיבוד עם OCR מתקדם"""
    processor = OCRProcessor()
    return processor.process_invoice_with_ocr(image_path, progress_callback)