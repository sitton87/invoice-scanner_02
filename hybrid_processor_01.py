"""
hybrid_01.py - מעבד היברידי פשוט עם pdf2image + OpenAI/Claude
"""

import json
import os
import datetime
from pathlib import Path
import pytesseract
import anthropic
from pdf2image import convert_from_path
from PIL import Image
import cv2
import numpy as np

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, validate_api_key, get_custom_output_filename


class SimpleHybridProcessor:
    """מעבד היברידי פשוט עם pdf2image"""
    
    def __init__(self, use_openai=False):
        """
        אתחול המעבד
        
        Args:
            use_openai: האם להשתמש ב-OpenAI במקום Claude
        """
        self.use_openai = use_openai
        
        if use_openai:
            try:
                import openai
                self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            except ImportError:
                raise ValueError("OpenAI library not installed. Run: pip install openai")
        else:
            if not validate_api_key():
                raise ValueError("Claude API key not configured")
            self.claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    def process_invoice(self, file_path, progress_callback=None):
        """עיבוד חשבונית עם השיטה הפשוטה"""
        try:
            file_path = Path(file_path)
            
            if progress_callback:
                progress_callback("Starting simple hybrid processing...")
            
            # שלב 1: חילוץ טקסט
            if file_path.suffix.lower() == '.pdf':
                extracted_text = self._process_pdf_simple(file_path, progress_callback)
            else:
                extracted_text = self._process_image_simple(file_path, progress_callback)
            
            # שלב 2: עיבוד עם LLM
            if progress_callback:
                progress_callback(f"Processing with {'OpenAI' if self.use_openai else 'Claude'}...")
            
            if self.use_openai:
                structured_data = self._process_with_openai(extracted_text)
                method_used = "pdf2image_ocr_openai" if file_path.suffix.lower() == '.pdf' else "simple_ocr_openai"
            else:
                structured_data = self._process_with_claude(extracted_text)
                method_used = "pdf2image_ocr_claude" if file_path.suffix.lower() == '.pdf' else "simple_ocr_claude"
            
            # שלב 3: שמירה
            if progress_callback:
                progress_callback("שומר תוצאות...")
            
            # יצירת מבנה נתונים לשמירה
            result_data = {
                "json_data": structured_data,
                "extracted_text": extracted_text,
                "method_used": method_used,
                "processing_timestamp": datetime.datetime.now().isoformat()
            }
            
            output_path = self._save_result(file_path, result_data)
            
            return {
                "success": True,
                "json_data": structured_data,
                "extracted_text": extracted_text,
                "method_used": method_used,
                "output_file": str(output_path),
                "message": "Simple hybrid processing completed successfully!"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Error in simple hybrid processing: {str(e)}"
            }
    
    def _process_pdf_simple(self, pdf_path, progress_callback=None):
        """עיבוד PDF פשוט עם pdf2image"""
        try:
            if progress_callback:
                progress_callback("Converting PDF to images with pdf2image...")
            
            # המרה לתמונות עם DPI גבוה
            images = convert_from_path(
                str(pdf_path),
                dpi=300,
                poppler_path=r"C:\Program Files\poppler\poppler-25.07.0\Library\bin"
            )
            
            if progress_callback:
                progress_callback(f"Converted to {len(images)} images, extracting text...")
            
            # OCR על כל התמונות
            ocr_texts = []
            for i, img in enumerate(images):
                if progress_callback:
                    progress_callback(f"OCR on page {i+1}/{len(images)}...")
                
                # המרה ל-numpy array אם נדרש עיבוד
                img_array = np.array(img)
                
                # OCR ישיר
                page_text = pytesseract.image_to_string(img_array, lang='heb+eng')
                if page_text.strip():
                    ocr_texts.append(f"=== Page {i+1} ===")
                    ocr_texts.append(page_text)
            
            return "\n".join(ocr_texts)
            
        except Exception as e:
            raise ValueError(f"Error processing PDF with pdf2image: {str(e)}")
    
    def _process_image_simple(self, image_path, progress_callback=None):
        """עיבוד תמונה פשוט"""
        try:
            if progress_callback:
                progress_callback("Processing image with simple OCR...")
            
            # טעינת תמונה
            image = Image.open(image_path)
            
            # OCR ישיר
            extracted_text = pytesseract.image_to_string(image, lang='heb+eng')
            
            if len(extracted_text.strip()) < 50:
                # אם לא הצלחנו לחלץ מספיק טקסט, ננסה עיבוד מינימלי
                if progress_callback:
                    progress_callback("Low text yield, trying with image enhancement...")
                
                # המרה ל-numpy ועיבוד מינימלי
                img_array = np.array(image.convert('RGB'))
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                
                # הגברת ניגודיות בסיסית
                enhanced = cv2.equalizeHist(gray)
                
                # OCR שוב
                extracted_text = pytesseract.image_to_string(enhanced, lang='heb+eng')
            
            return extracted_text
            
        except Exception as e:
            raise ValueError(f"Error processing image: {str(e)}")
    
    def _process_with_openai(self, extracted_text):
        """עיבוד עם OpenAI"""
        try:
            prompt = f"""
Extract all item lines from this Hebrew/English invoice text and return as JSON:

{{
  "main_items": [
    {{
      "line": line_number,
      "barcode": "barcode_if_exists",
      "item_code": "item_code",
      "description": "product_description",
      "quantity": quantity_number,
      "unit_price": unit_price_number,
      "discount_percent": discount_percentage,
      "price_after_discount": discounted_price,
      "total_amount": line_total
    }}
  ],
  "summary": {{
    "total_lines": total_number_of_lines,
    "subtotal": subtotal_amount
  }}
}}

Invoice text:
{extracted_text[:4000]}

Extract ALL lines from the table!
"""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",  # או gpt-4 אם זמין
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4000
            )
            
            response_text = response.choices[0].message.content
            return self._extract_json_from_response(response_text)
            
        except Exception as e:
            raise ValueError(f"Error with OpenAI processing: {str(e)}")
    
    def _process_with_claude(self, extracted_text):
        """עיבוד עם Claude"""
        try:
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
{extracted_text[:4000]}

חלץ את כל השורות בטבלה!
"""
            
            response = self.claude_client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=8000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text
            return self._extract_json_from_response(response_text)
            
        except Exception as e:
            raise ValueError(f"Error with Claude processing: {str(e)}")
    
    def _extract_json_from_response(self, response_text):
        """חילוץ JSON מתשובת ה-LLM"""
        try:
            # חיפוש JSON בתשובה
            start_pos = response_text.find('{')
            if start_pos == -1:
                raise ValueError("No JSON found in response")
            
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
            raise ValueError(f"Error parsing JSON: {str(e)}")
    
    def _save_result(self, original_file_path, result_data):
        """שמירת התוצאה לקובץ"""
        try:
            # Simple Hybrid תמיד עושה MAIN בלבד (כרגע)
            output_path = get_custom_output_filename(original_file_path, "HYBRID", "MAIN")
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            
            return output_path
            
        except Exception as e:
            raise ValueError(f"שגיאה בשמירת קובץ: {str(e)}")


# פונקציות נוחות
def process_invoice_simple_hybrid(file_path, use_openai=False, progress_callback=None):
    """פונקציה נוחה לעיבוד עם היברידי פשוט"""
    processor = SimpleHybridProcessor(use_openai=use_openai)
    return processor.process_invoice(file_path, progress_callback)


def process_invoice_simple_claude(file_path, progress_callback=None):
    """פונקציה נוחה לעיבוד עם Claude"""
    return process_invoice_simple_hybrid(file_path, use_openai=False, progress_callback=progress_callback)


def process_invoice_simple_openai(file_path, progress_callback=None):
    """פונקציה נוחה לעיבוד עם OpenAI"""
    return process_invoice_simple_hybrid(file_path, use_openai=True, progress_callback=progress_callback)