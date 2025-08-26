"""
intro_analyzer.py - מנתח החלק הפותח של החשבונית (INTRO)
"""

import json
import anthropic
from pathlib import Path
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, validate_api_key


class IntroAnalyzer:
    """מחלקה לניתוח החלק הפותח של החשבונית"""
    
    def __init__(self):
        """אתחול מנתח ה-INTRO"""
        if not validate_api_key():
            raise ValueError("מפתח API לא תקין")
        
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    def analyze_intro(self, image_path=None, extracted_text=None, progress_callback=None):
        """
        ניתוח החלק הפותח של החשבונית
        
        Args:
            image_path: נתיב לתמונת החשבונית (אם משתמשים במצב תמונה)
            extracted_text: טקסט מחולץ (אם משתמשים במצב OCR)
            progress_callback: פונקציה לעדכון התקדמות
            
        Returns:
            dict: פרטי ה-INTRO בפורמט JSON
        """
        try:
            if progress_callback:
                progress_callback("מנתח פרטי חשבונית (INTRO)...")
            
            # הכנת הפרומפט לניתוח INTRO
            intro_prompt = self._create_intro_prompt()
            
            if extracted_text:
                # מצב OCR - שליחת טקסט
                result = self._analyze_intro_from_text(extracted_text, intro_prompt)
            else:
                # מצב תמונה - שליחת תמונה
                result = self._analyze_intro_from_image(image_path, intro_prompt)
            
            return result
            
        except Exception as e:
            raise ValueError(f"שגיאה בניתוח INTRO: {str(e)}")
    
    def _create_intro_prompt(self):
        """יצירת פרומפט לניתוח INTRO"""
        return """
נתח את החלק הפותח (INTRO) של החשבונית וחלץ את המידע הבא בפורמט JSON:

{
  "invoice_info": {
    "number": "מספר_חשבונית",
    "date": "תאריך_חשבונית",
    "type": "סוג_מסמך",
    "due_date": "תאריך_לתשלום",
    "reference": "מספר_הזמנה_או_התייחסות",
    "currency": "מטבע"
  },
  "company_info": {
    "name": "שם_החברה_המוכרת",
    "address": "כתובת_החברה",
    "city": "עיר",
    "postal_code": "מיקוד", 
    "phone": "טלפון",
    "fax": "פקס",
    "email": "אימייל",
    "website": "אתר",
    "tax_id": "מספר_עוסק_מורשה_או_חפ",
    "business_license": "מספר_רישיון_עסק"
  },
  "customer_info": {
    "name": "שם_הלקוח",
    "address": "כתובת_הלקוח",
    "city": "עיר_הלקוח",
    "postal_code": "מיקוד_לקוח",
    "phone": "טלפון_לקוח",
    "email": "אימייל_לקוח",
    "tax_id": "חפ_או_עמ_של_הלקוח",
    "contact_person": "איש_קשר"
  },
  "payment_terms": {
    "due_date": "תאריך_לתשלום",
    "payment_method": "אמצעי_תשלום",
    "bank_details": "פרטי_בנק",
    "credit_terms": "תנאי_אשראי",
    "notes": "הערות_תשלום"
  },
  "additional_info": {
    "delivery_address": "כתובת_משלוח",
    "order_number": "מספר_הזמנה",
    "delivery_date": "תאריך_משלוח",
    "agent_name": "שם_סוכן",
    "agent_phone": "טלפון_סוכן",
    "notes": "הערות_נוספות"
  }
}

הוראות חשובות:
• אם שדה לא קיים או לא ברור - השאר מחרוזת ריקה ""
• חלץ רק מידע שמופיע בפועל בחשבונית  
• הקפד על דיוק בפרטים כמו מספרים ותאריכים
• אל תמציא מידע שלא קיים
"""
    
    def _analyze_intro_from_text(self, extracted_text, intro_prompt):
        """ניתוח INTRO מטקסט מחולץ (מצב OCR)"""
        try:
            full_prompt = f"""
{intro_prompt}

הטקסט המחולץ מהחשבונית:
{extracted_text[:3000]}
"""
            
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4000,
                messages=[
                    {
                        "role": "user",
                        "content": full_prompt
                    }
                ]
            )
            
            response_text = response.content[0].text
            return self._extract_json_from_response(response_text)
            
        except Exception as e:
            raise ValueError(f"שגיאה בניתוח INTRO מטקסט: {str(e)}")
    
    def _analyze_intro_from_image(self, image_path, intro_prompt):
        """ניתוח INTRO מתמונה (מצב תמונה)"""
        try:
            import base64
            
            # קריאת התמונה וקידוד base64
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4000,
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
                                "text": intro_prompt
                            }
                        ]
                    }
                ]
            )
            
            response_text = response.content[0].text
            return self._extract_json_from_response(response_text)
            
        except Exception as e:
            raise ValueError(f"שגיאה בניתוח INTRO מתמונה: {str(e)}")
    
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
            parsed_json = json.loads(json_text)
            
            # ניקוי וולידציה של הנתונים
            return self._clean_and_validate_intro(parsed_json)
            
        except json.JSONDecodeError as e:
            raise ValueError(f"שגיאה בפרסור JSON: {str(e)}")
    
    def _clean_and_validate_intro(self, intro_data):
        """ניקוי וולידציה של נתוני INTRO"""
        try:
            # וידוא שכל הקטגוריות הראשיות קיימות
            required_sections = ['invoice_info', 'company_info', 'customer_info', 'payment_terms', 'additional_info']
            
            for section in required_sections:
                if section not in intro_data:
                    intro_data[section] = {}
            
            # ניקוי שדות ריקים ו-null
            for section_name, section_data in intro_data.items():
                if isinstance(section_data, dict):
                    for key, value in section_data.items():
                        # המרת None ו-null למחרוזת ריקה
                        if value is None or str(value).lower() in ['null', 'none', 'n/a']:
                            intro_data[section_name][key] = ""
                        # ניקוי רווחים
                        elif isinstance(value, str):
                            intro_data[section_name][key] = value.strip()
            
            # הוספת metadata
            intro_data['metadata'] = {
                'extracted_fields_count': self._count_non_empty_fields(intro_data),
                'completeness_score': self._calculate_completeness_score(intro_data),
                'analysis_timestamp': self._get_current_timestamp()
            }
            
            return intro_data
            
        except Exception as e:
            raise ValueError(f"שגיאה בניקוי נתוני INTRO: {str(e)}")
    
    def _count_non_empty_fields(self, intro_data):
        """ספירת שדות לא ריקים"""
        count = 0
        for section_name, section_data in intro_data.items():
            if isinstance(section_data, dict) and section_name != 'metadata':
                for value in section_data.values():
                    if isinstance(value, str) and value.strip():
                        count += 1
        return count
    
    def _calculate_completeness_score(self, intro_data):
        """חישוב ציון שלמות (אחוז השדות שמולאו)"""
        total_fields = 0
        filled_fields = 0
        
        for section_name, section_data in intro_data.items():
            if isinstance(section_data, dict) and section_name != 'metadata':
                for value in section_data.values():
                    total_fields += 1
                    if isinstance(value, str) and value.strip():
                        filled_fields += 1
        
        if total_fields == 0:
            return 0
        
        return round((filled_fields / total_fields) * 100, 1)
    
    def _get_current_timestamp(self):
        """קבלת timestamp נוכחי"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# פונקציה נוחה לשימוש מהיר
def analyze_intro(image_path=None, extracted_text=None, progress_callback=None):
    """
    פונקציה נוחה לניתוח INTRO
    
    Args:
        image_path: נתיב לתמונת החשבונית
        extracted_text: טקסט מחולץ
        progress_callback: פונקציה לעדכון התקדמות
        
    Returns:
        dict: נתוני INTRO
    """
    analyzer = IntroAnalyzer()
    return analyzer.analyze_intro(image_path, extracted_text, progress_callback)