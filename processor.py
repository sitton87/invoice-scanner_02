"""
processor.py - מעבד החשבוניות הראשי - עם תמיכה בכל עמודי PDF
"""

import base64
import json
import anthropic
from pathlib import Path
from PIL import Image
import fitz  # PyMuPDF
import tempfile
import os
import io

from config import (
    ANTHROPIC_API_KEY, CLAUDE_MODEL, SYSTEM_PROMPT, USER_PROMPT,
    TEMP_DIR, MAX_IMAGE_SIZE, IMAGE_QUALITY, SUPPORTED_IMAGE_FORMATS,
    validate_api_key, get_output_filename, is_supported_format
)


class InvoiceProcessor:
    """מחלקה לעיבוד חשבוניות"""
    
    def __init__(self):
        """אתחול המעבד"""
        if not validate_api_key():
            raise ValueError("מפתח API לא תקין. ערוך את קובץ config.py")
        
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    def process_invoice(self, file_path, progress_callback=None):
        """
        עיבוד חשבונית מקובץ
        
        Args:
            file_path (str): נתיב לקובץ החשבונית
            progress_callback (function): פונקציה לעדכון התקדמות
            
        Returns:
            dict: תוצאת העיבוד עם JSON ונתיב קובץ הפלט
        """
        try:
            if progress_callback:
                progress_callback("בודק פורמט קובץ...")
            
            # בדיקת פורמט
            if not is_supported_format(file_path):
                raise ValueError("פורמט קובץ לא נתמך")
            
            if progress_callback:
                progress_callback("מכין תמונה לעיבוד...")
            
            # המרה לתמונה אם נדרש
            image_path = self._prepare_image(file_path)
            
            if progress_callback:
                progress_callback("שולח לClaude לניתוח...")
            
            # עיבוד עם Claude
            result_json = self._process_with_claude(image_path)
            
            if progress_callback:
                progress_callback("שומר תוצאות...")
            
            # שמירת התוצאה
            output_path = self._save_result(file_path, result_json)
            
            # ניקוי קבצים זמניים
            self._cleanup_temp_files(image_path, file_path)
            
            if progress_callback:
                progress_callback("הושלם בהצלחה!")
            
            return {
                "success": True,
                "json_data": result_json,
                "output_file": str(output_path),
                "message": "החשבונית עובדה בהצלחה!"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"שגיאה בעיבוד: {str(e)}"
            }
    
    def _prepare_image(self, file_path):
        """הכנת תמונה לעיבוד"""
        file_path = Path(file_path)
        
        # אם זה PDF - המר לתמונה
        if file_path.suffix.lower() == '.pdf':
            return self._pdf_to_image(file_path)
        
        # אם זה תמונה - בדוק גודל ואופטמיז
        elif file_path.suffix.lower() in SUPPORTED_IMAGE_FORMATS:
            return self._optimize_image(file_path)
        
        else:
            raise ValueError("פורמט קובץ לא נתמך")
    
    def _pdf_to_image(self, pdf_path):
        """המרת PDF לתמונה מאוחדת של כל העמודים"""
        try:
            # פתיחת ה-PDF
            pdf_document = fitz.open(pdf_path)
            
            # רשימת תמונות לאיחוד
            images = []
            
            # המרת כל העמודים לתמונות
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))  # הגדלה לאיכות טובה יותר
                
                # המרה ל-PIL Image
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                images.append(img)
            
            pdf_document.close()
            
            # איחוד כל העמודים לתמונה אחת ארוכה
            combined_image = self._combine_images_vertically(images)
            
            # שמירה כתמונה זמנית
            temp_image_path = TEMP_DIR / f"temp_combined_{pdf_path.stem}.png"
            combined_image.save(temp_image_path, 'PNG')
            
            # אופטימיזציה של התמונה המאוחדת
            return self._optimize_image(temp_image_path)
            
        except Exception as e:
            raise ValueError(f"שגיאה בהמרת PDF: {str(e)}")
    
    def _combine_images_vertically(self, images):
        """איחוד רשימת תמונות לתמונה אחת אנכית"""
        if not images:
            raise ValueError("אין תמונות לאיחוד")
        
        # חישוב רוחב מקסימלי וגובה כולל
        max_width = max(img.width for img in images)
        total_height = sum(img.height for img in images)
        
        # יצירת תמונה חדשה
        combined = Image.new('RGB', (max_width, total_height), 'white')
        
        # הדבקת כל התמונות
        y_offset = 0
        for img in images:
            # המרה ל-RGB אם נדרש
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # מרכוז התמונה אם היא צרה יותר
            x_offset = (max_width - img.width) // 2
            combined.paste(img, (x_offset, y_offset))
            y_offset += img.height
        
        return combined
    
    def _optimize_image(self, image_path):
        """אופטימיזציה של תמונה"""
        try:
            with Image.open(image_path) as img:
                # המרה ל-RGB אם נדרש
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # שינוי גודל אם גדול מדי
                if img.size[0] > MAX_IMAGE_SIZE[0] or img.size[1] > MAX_IMAGE_SIZE[1]:
                    img.thumbnail(MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)
                
                # שמירה כקובץ זמני מאופטמיז
                temp_image_path = TEMP_DIR / f"optimized_{Path(image_path).stem}.jpg"
                img.save(temp_image_path, 'JPEG', quality=IMAGE_QUALITY, optimize=True)
                
                return temp_image_path
                
        except Exception as e:
            raise ValueError(f"שגיאה באופטימיזציה: {str(e)}")
    
    def _process_with_claude(self, image_path):
        """עיבוד התמונה עם Claude"""
        try:
            # קריאת התמונה וקידוד base64
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            # שליחה לClaude
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=8000,  # חזרנו לגבול המקסימלי המותר
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_data
                                }
                            },
                            {
                                "type": "text",
                                "text": USER_PROMPT
                            }
                        ]
                    }
                ]
            )
            
            # חילוץ התשובה
            response_text = response.content[0].text
            
            # ניסיון לחלץ JSON מהתשובה
            return self._extract_json_from_response(response_text)
            
        except anthropic.APIError as e:
            raise ValueError(f"שגיאת API: {str(e)}")
        except Exception as e:
            raise ValueError(f"שגיאה בעיבוד עם Claude: {str(e)}")
    
    def _extract_json_from_response(self, response_text):
        """חילוץ JSON מתשובת Claude"""
        try:
            # חיפוש JSON בתשובה
            start_markers = ['```json', '{']
            end_markers = ['```', '}']
            
            # ניסיון למצוא JSON
            json_start = -1
            for marker in start_markers:
                pos = response_text.find(marker)
                if pos != -1:
                    json_start = pos + len(marker) if marker == '```json' else pos
                    break
            
            if json_start == -1:
                raise ValueError("לא נמצא JSON בתשובה")
            
            # חיפוש סוף ה-JSON
            if response_text[json_start:].strip().startswith('{'):
                # ספירת סוגריים למציאת סוף ה-JSON
                brace_count = 0
                json_end = json_start
                for i, char in enumerate(response_text[json_start:], json_start):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                
                json_text = response_text[json_start:json_end]
            else:
                # אם יש ```json בהתחלה
                json_end = response_text.find('```', json_start)
                if json_end == -1:
                    json_end = len(response_text)
                json_text = response_text[json_start:json_end]
            
            # ניסיון לפרס את ה-JSON
            return json.loads(json_text.strip())
            
        except json.JSONDecodeError as e:
            raise ValueError(f"שגיאה בפרסור JSON: {str(e)}")
        except Exception as e:
            raise ValueError(f"שגיאה בחילוץ JSON: {str(e)}")
    
    def _save_result(self, original_file_path, json_data):
        """שמירת התוצאה לקובץ"""
        try:
            output_path = get_output_filename(original_file_path)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            return output_path
            
        except Exception as e:
            raise ValueError(f"שגיאה בשמירת קובץ: {str(e)}")
    
    def _cleanup_temp_files(self, temp_image_path, original_file_path):
        """ניקוי קבצים זמניים"""
        try:
            # מחיקת קובץ תמונה זמני אם זה לא הקובץ המקורי
            if temp_image_path != Path(original_file_path) and Path(temp_image_path).exists():
                Path(temp_image_path).unlink()
                
            # מחיקת קבצים זמניים נוספים
            for temp_file in TEMP_DIR.glob("temp_*"):
                try:
                    temp_file.unlink()
                except:
                    pass  # לא נעצור אם יש בעיה במחיקה
                    
        except Exception:
            # אם יש בעיה בניקוי - לא נעצור את התהליך
            pass


# פונקציה נוחה לשימוש מהיר
def process_single_invoice(file_path, progress_callback=None):
    """
    פונקציה נוחה לעיבוד חשבונית יחידה
    
    Args:
        file_path (str): נתיב לקובץ החשבונית
        progress_callback (function): פונקציה לעדכון התקדמות
        
    Returns:
        dict: תוצאת העיבוד
    """
    processor = InvoiceProcessor()
    return processor.process_invoice(file_path, progress_callback)