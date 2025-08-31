"""
full_processor.py - מעבד מלא לחשבוניות (INTRO + MAIN)
"""

import json
import time
from datetime import datetime
from pathlib import Path

# ייבוא המעבדים הספציפיים
from intro_analyzer import IntroAnalyzer
from processor import InvoiceProcessor
from ocr_processor import OCRProcessor
from config import get_output_filename
from config import get_custom_output_filename

class FullInvoiceProcessor:
    """מעבד מלא לחשבוניות - INTRO + MAIN"""
    
    def __init__(self):
        """אתחול המעבד המלא"""
        self.intro_analyzer = IntroAnalyzer()
        self.main_processor = InvoiceProcessor()
        self.ocr_processor = OCRProcessor()
    
    def process_full_invoice(self, file_path, process_intro=True, process_main=True, 
                           use_ocr=True, progress_callback=None):
        """
        עיבוד מלא של חשבונית
        
        Args:
            file_path: נתיב לקובץ החשבונית
            process_intro: האם לעבד את ה-INTRO
            process_main: האם לעבד את ה-MAIN
            use_ocr: האם להשתמש ב-OCR
            progress_callback: פונקציה לעדכון התקדמות
            
        Returns:
            dict: תוצאת העיבוד המלא
        """
        start_time = time.time()
        
        try:
            if progress_callback:
                progress_callback("מתחיל עיבוד מלא של החשבונית...")
            
            # בדיקה שיש לפחות משהו לעבד
            if not process_intro and not process_main:
                raise ValueError("יש לבחור לפחות חלק אחד לעיבוד (INTRO או MAIN)")
            
            # הכנת המבנה הבסיסי
            result = {
                "success": True,
                "processing_info": {
                    "file_path": str(file_path),
                    "process_intro": process_intro,
                    "process_main": process_main,
                    "use_ocr": use_ocr,
                    "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            }
            
            # שלב 1: הכנת נתונים (OCR או תמונה)
            extracted_text = None
            processed_image_path = file_path
            
            if use_ocr:
                if progress_callback:
                    progress_callback("מבצע OCR לחילוץ טקסט...")
                
                ocr_result = self.ocr_processor.process_invoice_with_ocr(
                    file_path, 
                    lambda msg: progress_callback(f"OCR: {msg}") if progress_callback else None
                )
                
                if not ocr_result["success"]:
                    raise ValueError(f"שגיאה ב-OCR: {ocr_result['message']}")
                
                extracted_text = ocr_result["extracted_text"]
            else:
                # הכנת תמונה למצב תמונה רגיל
                processed_image_path = self._prepare_image_for_analysis(file_path)
            
            # שלב 2: עיבוד INTRO
            if process_intro:
                if progress_callback:
                    progress_callback("מנתח פרטי חשבונית (INTRO)...")
                
                try:
                    intro_data = self.intro_analyzer.analyze_intro(
                        image_path=processed_image_path if not use_ocr else None,
                        extracted_text=extracted_text if use_ocr else None,
                        progress_callback=lambda msg: progress_callback(f"INTRO: {msg}") if progress_callback else None
                    )
                    result["intro"] = intro_data
                    
                except Exception as e:
                    result["intro"] = {"error": str(e), "message": "שגיאה בניתוח INTRO"}
                    if progress_callback:
                        progress_callback(f"שגיאה ב-INTRO: {str(e)}")
            
            # שלב 3: עיבוד MAIN
            if process_main:
                if progress_callback:
                    progress_callback("מנתח שורות פריטים (MAIN)...")
                
                try:
                    if use_ocr:
                        # במצב OCR - נשתמש בטקסט המחולץ עם Claude
                        main_data = self._process_main_from_text(
                            extracted_text,
                            lambda msg: progress_callback(f"MAIN: {msg}") if progress_callback else None
                        )
                    else:
                        # במצב תמונה - נשתמש במעבד הרגיל
                        main_result = self.main_processor.process_invoice(
                            file_path,
                            lambda msg: progress_callback(f"MAIN: {msg}") if progress_callback else None
                        )
                        
                        if not main_result["success"]:
                            raise ValueError(main_result["message"])
                        
                        main_data = main_result["json_data"]
                    
                    result["main"] = main_data
                    
                except Exception as e:
                    result["main"] = {"error": str(e), "message": "שגיאה בניתוח MAIN"}
                    if progress_callback:
                        progress_callback(f"שגיאה ב-MAIN: {str(e)}")
            
            # שלב 4: חישוב סטטיסטיקות
            end_time = time.time()
            processing_time = end_time - start_time
            
            result["summary"] = self._create_summary(result, processing_time)
            
            # שלב 5: שמירת התוצאה
            if progress_callback:
                progress_callback("שומר תוצאות...")
            
            output_file = self._save_full_result(file_path, result)
            result["output_file"] = str(output_file)
            
            if progress_callback:
                progress_callback("הושלם בהצלחה!")
            
            result["message"] = "עיבוד מלא הושלם בהצלחה!"
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"שגיאה בעיבוד מלא: {str(e)}",
                "processing_time": time.time() - start_time
            }
    
    def _prepare_image_for_analysis(self, file_path):
        """הכנת תמונה לניתוח במצב תמונה"""
        # במצב תמונה רגיל, פשוט נחזיר את הנתיב
        # אפשר להוסיף כאן עיבוד תמונה אם נדרש
        return file_path
    
    def _process_main_from_text(self, extracted_text, progress_callback=None):
        """עיבוד MAIN מטקסט מחולץ (במצב OCR)"""
        try:
            # נשתמש בלוגיקה דומה למעבד OCR אבל רק ל-MAIN
            from config import CLAUDE_MODEL, ANTHROPIC_API_KEY
            import anthropic
            
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            
            prompt = f"""
חלץ את כל שורות הפריטים מהטקסט הזה ויצור JSON במבנה:

{{
  "main_items": [
    {{
      "line": מספר_שורה,
      "barcode": "ברקוד",
      "item_code": "קוד_פריט", 
      "description": "תיאור_מוצר",
      "quantity": כמות,
      "unit_price": מחיר_יחידה,
      "discount_percent": אחוז_הנחה,
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
{extracted_text[:4000]}

חשוב: חלץ את כל השורות - אל תדלג על כלום!
"""
            
            response = client.messages.create(
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
            
        except Exception as e:
            raise ValueError(f"שגיאה בעיבוד MAIN מטקסט: {str(e)}")
    
    def _create_summary(self, result, processing_time):
        """יצירת סיכום של העיבוד"""
        summary = {
            "processing_time_seconds": round(processing_time, 2),
            "processing_time_formatted": self._format_duration(processing_time),
            "processed_sections": []
        }
        
        # בדיקה אילו חלקים עובדו
        if "intro" in result:
            summary["processed_sections"].append("INTRO")
            if "metadata" in result["intro"]:
                summary["intro_fields_extracted"] = result["intro"]["metadata"].get("extracted_fields_count", 0)
                summary["intro_completeness"] = result["intro"]["metadata"].get("completeness_score", 0)
        
        if "main" in result:
            summary["processed_sections"].append("MAIN")
            if "summary" in result["main"]:
                summary["main_lines_extracted"] = result["main"]["summary"].get("total_lines", 0)
                summary["main_subtotal"] = result["main"]["summary"].get("subtotal", 0)
        
        # סטטיסטיקות כלליות
        summary["total_sections_processed"] = len(summary["processed_sections"])
        summary["analysis_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return summary
    
    def _format_duration(self, seconds):
        """פורמט זמן נוח לקריאה"""
        if seconds < 60:
            return f"{seconds:.1f} שניות"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            remaining_seconds = seconds % 60
            return f"{minutes}:{remaining_seconds:04.1f} דקות"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            remaining_seconds = seconds % 60
            return f"{hours}:{minutes:02d}:{remaining_seconds:04.1f} שעות"
    
    def _save_full_result(self, original_file_path, result):
        """שמירת התוצאה המלאה לקובץ עם timestamp"""
        try:
            # קביעת שיטה מתוך הנתונים
            processing_info = result.get("processing_info", {})
            use_ocr = processing_info.get("use_ocr", True)
            method = "OCR" if use_ocr else "IMAGE"
            
            # קביעת חלקים שעובדו
            sections_processed = result.get("summary", {}).get("processed_sections", [])
            if not sections_processed:
                # חישוב מהנתונים הקיימים
                sections_processed = []
                if "intro" in result:
                    sections_processed.append("INTRO")
                if "main" in result:
                    sections_processed.append("MAIN")
            
            output_path = get_custom_output_filename(original_file_path, method, sections_processed)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            return output_path
            
        except Exception as e:
            raise ValueError(f"שגיאה בשמירת קובץ: {str(e)}")


# פונקציה נוחה לשימוש מהיר
def process_full_invoice(file_path, process_intro=True, process_main=True, 
                        use_ocr=True, progress_callback=None):
    """
    פונקציה נוחה לעיבוד מלא של חשבונית
    
    Args:
        file_path: נתיב לקובץ החשבונית
        process_intro: האם לעבד INTRO
        process_main: האם לעבד MAIN
        use_ocr: האם להשתמש ב-OCR
        progress_callback: פונקציה לעדכון התקדמות
        
    Returns:
        dict: תוצאת העיבוד המלא
    """
    processor = FullInvoiceProcessor()
    return processor.process_full_invoice(
        file_path, process_intro, process_main, use_ocr, progress_callback
    )