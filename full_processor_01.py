"""
full_processor.py - מעבד מאוחד לחשבוניות עם ארגון תיקיות לפי שיטה
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Callable

from config import OUTPUT_DIR, validate_api_key, MESSAGES
from processor import process_single_invoice
from ocr_processor import process_invoice_with_ocr
from intro_analyzer import analyze_intro


def get_method_directory(base_output_dir: Path, process_intro: bool, process_main: bool, use_ocr: bool) -> Path:
    """יצירת תיקיית שיטה לפי הפרמטרים"""
    
    # קביעת שם השיטה
    method_parts = []
    
    # סוג העיבוד
    if use_ocr:
        method_parts.append("OCR")
    else:
        method_parts.append("IMAGE")
    
    # סעיפים לעיבוד
    sections = []
    if process_intro:
        sections.append("INTRO")
    if process_main:
        sections.append("MAIN")
    
    if sections:
        method_parts.append("_".join(sections))
    else:
        method_parts.append("NO_SECTIONS")
    
    method_name = "_".join(method_parts)
    
    # יצירת תיקיית השיטה
    method_dir = base_output_dir / method_name
    method_dir.mkdir(parents=True, exist_ok=True)
    
    return method_dir


def generate_timestamped_filename(original_filename: str, timestamp: datetime) -> str:
    """יצירת שם קובץ עם זמן"""
    original_path = Path(original_filename)
    stem = original_path.stem
    
    # פורמט זמן: YYYYMMDD_HHMMSS
    time_str = timestamp.strftime("%Y%m%d_%H%M%S")
    
    # שם הקובץ החדש
    new_filename = f"{stem}_{time_str}_full_analysis.json"
    
    return new_filename


def process_full_invoice(
    file_path: str,
    process_intro: bool = True,
    process_main: bool = True,
    use_ocr: bool = True,
    progress_callback: Optional[Callable[[str], None]] = None
) -> Dict[str, Any]:
    """
    עיבוד מאוחד של חשבונית עם ארגון תיקיות לפי שיטה
    
    Args:
        file_path: נתיב קובץ החשבונית
        process_intro: האם לעבד מידע כללי
        process_main: האם לעבד שורות פריטים
        use_ocr: האם להשתמש ב-OCR
        progress_callback: פונקציה לעדכון התקדמות
        
    Returns:
        Dict עם תוצאות העיבוד
    """
    
    def log_progress(message: str):
        """עדכון התקדמות"""
        if progress_callback:
            progress_callback(message)
        print(f"[FULL_PROCESSOR] {message}")
    
    try:
        # בדיקת API Key
        if not validate_api_key():
            return {
                "success": False,
                "message": MESSAGES["error_api_key"],
                "error": "Missing or invalid API key"
            }
        
        start_time = time.time()
        processing_timestamp = datetime.now()
        
        log_progress("Starting unified processing...")
        log_progress(f"File: {Path(file_path).name}")
        log_progress(f"Mode: {'OCR' if use_ocr else 'Image'}")
        
        sections = []
        if process_intro:
            sections.append("INTRO")
        if process_main:
            sections.append("MAIN")
        log_progress(f"Sections: {', '.join(sections) if sections else 'None'}")
        
        # בדיקה שיש לפחות סעיף אחד לעיבוד
        if not process_intro and not process_main:
            return {
                "success": False,
                "message": "יש לבחור לפחות סעיף אחד לעיבוד",
                "error": "No sections selected for processing"
            }
        
        # הכנת מבנה התוצאה
        result = {
            "success": True,
            "processing_info": {
                "file_path": file_path,
                "process_intro": process_intro,
                "process_main": process_main,
                "use_ocr": use_ocr,
                "start_time": processing_timestamp.strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        
        # עיבוד INTRO
        if process_intro:
            log_progress("Processing INTRO section...")
            try:
                # קריאה לanalyze_intro בלי use_ocr אם הפונקציה לא תומכת בזה
                try:
                    intro_result = analyze_intro(file_path, use_ocr=use_ocr)
                except TypeError as e:
                    if "unexpected keyword argument 'use_ocr'" in str(e):
                        log_progress("analyze_intro doesn't support use_ocr parameter, using default mode")
                        intro_result = analyze_intro(file_path)
                    else:
                        raise e
                
                if intro_result["success"]:
                    # נסה לגשת לנתונים בדרכים שונות
                    intro_data = intro_result.get("data") or intro_result.get("intro") or intro_result
                    result["intro"] = intro_data
                    log_progress(f"INTRO completed: {len(intro_data)} fields extracted" if isinstance(intro_data, dict) else "INTRO completed")
                else:
                    log_progress(f"INTRO failed: {intro_result.get('message', 'Unknown error')}")
                    result["intro"] = {"error": intro_result.get("message", "Failed to process INTRO")}
            except Exception as e:
                log_progress(f"INTRO error: {str(e)}")
                result["intro"] = {"error": str(e)}
        
        # עיבוד MAIN
        if process_main:
            log_progress("Processing MAIN section...")
            try:
                if use_ocr:
                    main_result = process_invoice_with_ocr(file_path)
                else:
                    main_result = process_single_invoice(file_path)
                
                if main_result.get("success", False):
                    # נסה לגשת לנתונים בדרכים שונות
                    main_data = main_result.get("data") or main_result.get("main") or main_result
                    result["main"] = main_data
                    
                    # נסה לחלץ מספר שורות ללוג
                    try:
                        if isinstance(main_data, dict) and "summary" in main_data:
                            lines_count = main_data["summary"].get("total_lines", "Unknown")
                        elif isinstance(main_data, dict) and "main_items" in main_data:
                            lines_count = len(main_data["main_items"])
                        else:
                            lines_count = "Unknown"
                        log_progress(f"MAIN completed: {lines_count} lines")
                    except Exception:
                        log_progress("MAIN completed")
                else:
                    log_progress(f"MAIN failed: {main_result.get('message', 'Unknown error')}")
                    result["main"] = {"error": main_result.get("message", "Failed to process MAIN")}
                    
                # שמירת טקסט OCR אם זמין
                if "extracted_text" in main_result:
                    result["extracted_text"] = main_result["extracted_text"]
                    
            except Exception as e:
                log_progress(f"MAIN error: {str(e)}")
                result["main"] = {"error": str(e)}
        
        # חישוב זמן עיבוד
        end_time = time.time()
        processing_time = end_time - start_time
        
        # יצירת תיקיית פלט לפי שיטה
        base_output_dir = Path(OUTPUT_DIR)
        method_dir = get_method_directory(base_output_dir, process_intro, process_main, use_ocr)
        
        log_progress(f"Method directory: {method_dir.name}")
        
        # יצירת שם קובץ עם זמן
        output_filename = generate_timestamped_filename(file_path, processing_timestamp)
        output_path = method_dir / output_filename
        
        # הוספת סיכום
        result["summary"] = {
            "processing_time_seconds": processing_time,
            "processing_time_formatted": f"{processing_time:.1f} שניות",
            "processed_sections": sections,
            "analysis_timestamp": processing_timestamp.isoformat()
        }
        
        # הוספת נתונים ספציפיים מכל סעיף
        if process_intro and "intro" in result and "error" not in result["intro"]:
            intro_data = result["intro"]
            if "metadata" in intro_data:
                result["summary"]["intro_fields_extracted"] = intro_data["metadata"].get("extracted_fields_count", 0)
                result["summary"]["intro_completeness"] = intro_data["metadata"].get("completeness_score", 0.0)
        
        if process_main and "main" in result and "error" not in result["main"]:
            main_data = result["main"]
            if "summary" in main_data:
                result["summary"]["main_lines_extracted"] = main_data["summary"].get("total_lines", 0)
                result["summary"]["main_subtotal"] = main_data["summary"].get("subtotal", 0.0)
        
        result["summary"]["total_sections_processed"] = len(sections)
        
        # שמירת הקובץ
        log_progress("Saving results...")
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
                
            result["output_file"] = str(output_path)
            result["json_data"] = result.copy()  # עבור תצוגה ב-GUI
            
            log_progress(f"Results saved to: {output_path}")
            log_progress(f"Processing completed in {processing_time:.1f} seconds")
            
            return {
                "success": True,
                "message": f"עיבוד הושלם בהצלחה ב-{processing_time:.1f} שניות",
                "output_file": str(output_path),
                "json_data": result,
                "extracted_text": result.get("extracted_text", ""),
                "processing_info": {
                    "method_directory": str(method_dir),
                    "filename": output_filename,
                    "sections_processed": sections,
                    "processing_time": processing_time
                }
            }
            
        except Exception as e:
            log_progress(f"Error saving file: {str(e)}")
            return {
                "success": False,
                "message": f"שגיאה בשמירת הקובץ: {str(e)}",
                "error": str(e)
            }
    
    except Exception as e:
        log_progress(f"Unexpected error: {str(e)}")
        return {
            "success": False,
            "message": f"שגיאה לא צפויה: {str(e)}",
            "error": str(e)
        }


def main():
    """בדיקה של הפונקציה"""
    # דוגמה לשימוש
    test_file = "path/to/test/invoice.jpg"
    
    result = process_full_invoice(
        file_path=test_file,
        process_intro=True,
        process_main=True,
        use_ocr=True
    )
    
    print("Result:", result["success"])
    if result["success"]:
        print("Output file:", result.get("output_file", "No file"))
    else:
        print("Error:", result.get("message", "Unknown error"))


if __name__ == "__main__":
    main()