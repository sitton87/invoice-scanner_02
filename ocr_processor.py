    
"""
ocr_processor.py - מעבד OCR עם תיקון סיבוב אוטומטי לחשבוניות
"""

import cv2
import numpy as np
from PIL import Image
import pytesseract
from pytesseract import Output
from pathlib import Path
import json
import anthropic
import fitz  # PyMuPDF
import io
import re
import imutils
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, validate_api_key

class OCRProcessor:
    """מעבד OCR עם תיקון סיבוב אוטומטי"""
    
    def __init__(self):
        """אתחול מעבד OCR"""
        if not validate_api_key():
            raise ValueError("מפתח API לא תקין")
        
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        print("✅ מעבד OCR הוכן בהצלחה (עם תיקון סיבוב אוטומטי)")
    
    def process_invoice_with_ocr(self, image_path, progress_callback=None):
        """עיבוד חשבונית עם OCR ותיקון סיבוב"""
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
                progress_callback("בודק כיוון תמונה ומתקן סיבוב...")
            
            # *** תיקון סיבוב אוטומטי - זה החלק החדש! ***
            corrected_image = self._auto_rotate_image(processed_image, progress_callback)
            
            if progress_callback:
                progress_callback("מבצע OCR לחילוץ טקסט...")
            
            # חילוץ טקסט עם OCR על התמונה המתוקנת
            extracted_text = self._extract_text_tesseract(corrected_image)
            
            if progress_callback:
                progress_callback("שולח טקסט לClaude לניתוח...")
            
            # ניתוח הטקסט עם Claude
            result_json = self._analyze_text_with_claude(extracted_text)
            
            return {
                "success": True,
                "json_data": result_json,
                "extracted_text": extracted_text,
                "message": "עיבוד הושלם בהצלחה עם תיקון סיבוב!"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"שגיאה בעיבוד OCR: {str(e)}"
            }
    
    def _auto_rotate_image(self, image, progress_callback=None):
        """תיקון סיבוב אוטומטי של התמונה"""
        try:
            # המרה לצבע אם התמונה בגרייסקייל
            if len(image.shape) == 2:
                rgb_image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            else:
                rgb_image = image
            
            # ניסיון לזהות כיוון עם Tesseract OSD (Orientation and Script Detection)
            try:
                if progress_callback:
                    progress_callback("מזהה כיוון התמונה...")
                
                # זיהוי כיוון עם Tesseract
                osd_result = pytesseract.image_to_osd(
                    rgb_image, 
                    config='--psm 0 -c min_characters_to_try=5',
                    output_type=Output.DICT
                )
                
                detected_angle = osd_result.get('rotate', 0)
                confidence = osd_result.get('orientation_conf', 0)
                
                if progress_callback:
                    progress_callback(f"זוהה סיבוב: {detected_angle}° (ביטחון: {confidence:.1f})")
                
                # רק אם הביטחון גבוה מספיק - בצע סיבוב
                if confidence > 1.5 and detected_angle != 0:
                    if progress_callback:
                        progress_callback(f"מסובב תמונה ב-{detected_angle} מעלות...")
                    
                    # סיבוב עם שמירה על גבולות התמונה
                    rotated_image = imutils.rotate_bound(rgb_image, detected_angle)
                    
                    # המרה חזרה לגרייסקייל
                    if len(image.shape) == 2:
                        return cv2.cvtColor(rotated_image, cv2.COLOR_RGB2GRAY)
                    else:
                        return rotated_image
                else:
                    if progress_callback:
                        progress_callback(f"ביטחון נמוך ({confidence:.1f}) - לא מסובב")
                    return image
                    
            except Exception as osd_error:
                if progress_callback:
                    progress_callback(f"זיהוי OSD נכשל: {str(osd_error)}")
                
                # אם OSD נכשל - ננסה זיהוי חלופי על בסיס קווים
                return self._detect_rotation_by_lines(image, progress_callback)
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"שגיאה בתיקון סיבוב: {str(e)}")
            return image  # נחזיר את התמונה המקורית במקרה של שגיאה
    
    def _detect_rotation_by_lines(self, image, progress_callback=None):
        """זיהוי סיבוב על בסיס זיהוי קווים (גיבוי אם OSD נכשל)"""
        try:
            if progress_callback:
                progress_callback("מנסה זיהוי סיבוב על בסיס קווים...")
            
            # המרה לבינארי
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # בינאריזציה
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # זיהוי קווים עם Hough Transform
            edges = cv2.Canny(binary, 50, 150, apertureSize=3)
            lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
            
            if lines is not None and len(lines) > 0:
                angles = []
                for rho, theta in lines[:10]:  # בדוק רק 10 קווים ראשונים
                    angle = (theta - np.pi/2) * 180 / np.pi
                    angles.append(angle)
                
                # מצא זווית חציונית
                median_angle = np.median(angles)
                
                # עגל לזוויות של 90 מעלות
                if abs(median_angle) > 45:
                    rotation_angle = 90 if median_angle > 0 else -90
                elif abs(median_angle) > 1:
                    rotation_angle = median_angle
                else:
                    rotation_angle = 0
                
                if abs(rotation_angle) > 1:
                    if progress_callback:
                        progress_callback(f"זוהה סיבוב על בסיס קווים: {rotation_angle:.1f}°")
                    
                    return imutils.rotate_bound(image, -rotation_angle)
                
            if progress_callback:
                progress_callback("לא נמצא סיבוב משמעותי")
            
            return image
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"שגיאה בזיהוי קווים: {str(e)}")
            return image
    
    def _preprocess_image(self, image_path):
        """עיבוד מקדים של התמונה לOCR - משופר"""
        try:
            # קריאת התמונה עם PIL (יותר בטוח)
            pil_image = Image.open(image_path)
            
            # המרה ל-numpy array
            image_array = np.array(pil_image)
            
            # אם התמונה צבעונית, המר לגרייסקייל
            if len(image_array.shape) == 3:
                image_array = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
            
            # שיפור איכות התמונה
            # 1. הפחתת רעש
            denoised = cv2.medianBlur(image_array, 3)
            
            # 2. הגברת ניגודיות עם CLAHE
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            enhanced = clahe.apply(denoised)
            
            # 3. הגדלת רזולוציה (יותר מתון)
            scale_factor = 1.2
            height, width = enhanced.shape
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            resized = cv2.resize(enhanced, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            
            # 4. שיפור שולי טקסט
            kernel = np.ones((2,2), np.uint8)
            processed = cv2.morphologyEx(resized, cv2.MORPH_CLOSE, kernel)
            
            return processed
            
        except Exception as e:
            raise ValueError(f"שגיאה בעיבוד התמונה: {str(e)}")
    
    def _process_pdf_for_ocr(self, pdf_path):
        """עיבוד PDF לOCR - משופר"""
        try:
            # פתיחת ה-PDF
            pdf_document = fitz.open(pdf_path)
            
            # רשימת תמונות
            images = []
            
            # המרת כל העמודים ברזולוציה גבוהה יותר
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                # רזולוציה גבוהה יותר לטקסט יותר ברור
                pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                
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
        """חילוץ טקסט עם Tesseract - משופר"""
        try:
            extracted_texts = []
            
            # ניסיון 1: עברית + אנגלית עם PSM מתאים לטבלאות
            try:
                text1 = pytesseract.image_to_string(
                    image, 
                    lang='heb+eng', 
                    config='--psm 6 -c preserve_interword_spaces=1'
                )
                if text1.strip():
                    extracted_texts.append("=== חילוץ עם עברית ואנגלית (PSM 6) ===")
                    extracted_texts.append(text1)
            except Exception as e:
                extracted_texts.append(f"שגיאה בחילוץ עברית PSM 6: {e}")
            
            # ניסיון 2: PSM שונה - טוב לטבלאות
            try:
                text2 = pytesseract.image_to_string(
                    image, 
                    lang='heb+eng', 
                    config='--psm 4 -c preserve_interword_spaces=1'
                )
                if text2.strip():
                    extracted_texts.append("\n=== חילוץ עם PSM 4 (טבלאות) ===")
                    extracted_texts.append(text2)
            except Exception as e:
                extracted_texts.append(f"שגיאה ב-PSM 4: {e}")
            
            # ניסיון 3: רק אנגלית (גיבוי)
            try:
                text3 = pytesseract.image_to_string(image, lang='eng', config='--psm 6')
                if text3.strip():
                    extracted_texts.append("\n=== חילוץ עם אנגלית בלבד ===")
                    extracted_texts.append(text3)
            except Exception as e:
                extracted_texts.append(f"שגיאה בחילוץ אנגלית: {e}")
            
            # שילוב כל התוצאות
            final_text = "\n".join(extracted_texts)
            
            # בדיקה שחילצנו משהו שימושי
            if len(final_text.strip()) < 50:
                raise ValueError("לא הצלחתי לחלץ מספיק טקסט מהתמונה")
            
            return final_text
            
        except Exception as e:
            raise ValueError(f"שגיאה בחילוץ טקסט: {str(e)}")
    
    def _analyze_text_with_claude(self, extracted_text):
        """ניתוח הטקסט המחולץ עם Claude - פרומפט משופר"""
        
        prompt = f"""
אתה מומחה לחילוץ נתונים מחשבוניות ישראליות. חלץ את שורות הפריטים מהטקסט הזה.

⚠️ הוראות קריטיות:
• חשבוניות בעברית נקראות מימין לשמאל
• עמודות נפוצות: ש | מק"ט | תאור מוצר | כמות | מחיר ליחידה | הנחה | מחיר אחרי הנחה | סה"כ
• מק"ט ≠ ברקוד (רוב החשבוניות אין בהן ברקוד)
• שים לב לכיוון העמודות הנכון
• אם מחיר ליחידה = 0.000 אז חשב: סה"כ ÷ כמות = מחיר ליחידה

פורמט JSON נדרש:
{{
  "main_items": [
    {{
      "line": מספר_שורה,
      "barcode": "ברקוד_אם_קיים_או_ריק",
      "item_code": "מק_ט",
      "description": "תיאור_מלא_של_המוצר",
      "quantity": כמות_במספרים,
      "unit_price": מחיר_ליחידה_חשוב_נכון,
      "discount_percent": אחוז_הנחה_או_0,
      "price_after_discount": מחיר_אחרי_הנחה,
      "total_amount": סכום_כולל_של_השורה
    }}
  ],
  "summary": {{
    "total_lines": מספר_שורות_כולל,
    "subtotal": סכום_ביניים
  }}
}}

דוגמה לעמודות נפוצות בחשבוניות ישראליות:
- עמודת "כמות" - מכילה מספרים כמו 1, 2, 5.5 וכו'
- עמודת "מחיר ליחידה" - מחיר למוצר אחד
- עמודת "סה"כ" או "סה"כ מחיר" - מחיר כולל לשורה

הטקסט המחולץ (לאחר תיקון סיבוב):
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
    """פונקציה נוחה לעיבוד עם OCR"""
    processor = OCRProcessor()
    return processor.process_invoice_with_ocr(image_path, progress_callback)