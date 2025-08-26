"""
main.py - הקובץ הראשי של Invoice2Claude עם תמיכה ב-OCR
"""

import sys
import os
from pathlib import Path

# הוספת הנתיב הנוכחי לPython path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

try:
    from ui import create_and_run_gui
    from config import validate_api_key, ANTHROPIC_API_KEY
    from processor import InvoiceProcessor
    # ייבוא מעבד OCR החדש
    from full_processor import OCRProcessor
    # ייבוא מנתח INTRO החדש
    from intro_analyzer import IntroAnalyzer
    # ייבוא המעבד המלא החדש
    from full_processor import FullInvoiceProcessor, process_full_invoice
except ImportError as e:
    print(f"שגיאה בייבוא מודולים: {e}")
    print("ודא שכל הקבצים נמצאים באותה תיקייה")
    sys.exit(1)


def check_dependencies():
    """בדיקת תלויות הפרויקט כולל OCR"""
    missing_deps = []
    
    # בדיקת ספריות חיצוניות
    try:
        import anthropic
    except ImportError:
        missing_deps.append("anthropic")
    
    try:
        import PIL
    except ImportError:
        missing_deps.append("Pillow")
        
    try:
        import fitz
    except ImportError:
        missing_deps.append("PyMuPDF")
    
    try:
        import easyocr
    except ImportError:
        missing_deps.append("easyocr")
        
    try:
        import pytesseract
    except ImportError:
        missing_deps.append("pytesseract")
        
    try:
        import cv2
    except ImportError:
        missing_deps.append("opencv-python")
    
    # בדיקת ספריות מובנות
    try:
        import tkinter
    except ImportError:
        missing_deps.append("tkinter (מובנה בPython)")
    
    if missing_deps:
        print("❌ חסרות ספריות נדרשות:")
        for dep in missing_deps:
            print(f"  - {dep}")
        print("\nהתקן את הספריות עם:")
        print("pip install anthropic Pillow PyMuPDF easyocr pytesseract opencv-python numpy")
        return False
    
    print("✅ כל הספריות מותקנות")
    return True


def check_config():
    """בדיקת הגדרות הפרויקט"""
    issues = []
    
    # בדיקת API Key
    if not validate_api_key():
        issues.append("מפתח API לא הוגדר או לא תקין")
    
    # בדיקת תיקיות
    required_dirs = ['output', 'temp']
    for dir_name in required_dirs:
        if not (current_dir / dir_name).exists():
            try:
                (current_dir / dir_name).mkdir(exist_ok=True)
                print(f"✅ נוצרה תיקיית {dir_name}")
            except Exception:
                issues.append(f"לא ניתן ליצור תיקיית {dir_name}")
    
    if issues:
        print("⚠️ בעיות בהגדרות:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    
    return True


def print_welcome():
    """הדפסת הודעת פתיחה"""
    print("=" * 60)
    print("🎯 Invoice2Claude - מעבד חשבוניות עם OCR")
    print("=" * 60)
    print("📋 מערכת לחילוץ פרטי פריטים מחשבוניות")
    print("🔍 תמיכה ב-OCR מתקדם לדיוק גבוה יותר")
    print()


def print_instructions():
    """הדפסת הוראות שימוש"""
    print("📖 הוראות שימוש:")
    print("1. ודא שמפתח API מוגדר בקובץ config.py")
    print("2. הרץ את התוכנה")
    print("3. בחר קובץ חשבונית (תמונה או PDF)")
    print("4. בחר מצב עיבוד: OCR או תמונה")
    print("5. לחץ 'עבד חשבונית'")
    print("6. התוצאה תישמר כקובץ JSON")
    print()
    print("💡 מצב OCR מומלץ לחשבוניות עם הרבה שורות!")
    print()


def print_system_info():
    """הדפסת מידע מערכת"""
    print("🔧 מידע מערכת:")
    print(f"Python: {sys.version.split()[0]}")
    print(f"תיקיית עבודה: {current_dir}")
    
    # בדיקת גרסאות ספריות
    try:
        import anthropic
        print(f"Anthropic: {anthropic.__version__}")
    except:
        print("Anthropic: לא מותקן")
    
    try:
        import PIL
        print(f"Pillow: {PIL.__version__}")
    except:
        print("Pillow: לא מותקן")
        
    try:
        import fitz
        print(f"PyMuPDF: {fitz.__version__}")
    except:
        print("PyMuPDF: לא מותקן")
        
    try:
        import easyocr
        print(f"EasyOCR: זמין")
    except:
        print("EasyOCR: לא מותקן")
        
    try:
        import pytesseract
        print(f"Pytesseract: זמין")
    except:
        print("Pytesseract: לא מותקן")
    
    print()


def run_cli_mode():
    """מצב שורת פקודה (לבדיקה מהירה)"""
    print("🖥️ מצב שורת פקודה")
    print("(למצב גרפי, הרץ ללא ארגומנטים)")
    print()
    
    if len(sys.argv) < 2:
        print("שימוש: python main.py <נתיב_לקובץ_חשבונית> [--ocr] [--intro-only] [--main-only]")
        print("דגלים:")
        print("  --ocr        : השתמש במצב OCR")
        print("  --intro-only : עבד רק INTRO")
        print("  --main-only  : עבד רק MAIN")
        print("  ברירת מחדל : INTRO + MAIN במצב תמונה")
        return
    
    file_path = sys.argv[1]
    use_ocr = "--ocr" in sys.argv
    intro_only = "--intro-only" in sys.argv
    main_only = "--main-only" in sys.argv
    
    # הגדרת מה לעבד
    process_intro = not main_only  # אם לא main-only, תעבד intro
    process_main = not intro_only   # אם לא intro-only, תעבד main
    
    if not os.path.exists(file_path):
        print(f"❌ קובץ לא נמצא: {file_path}")
        return
    
    print(f"📄 מעבד קובץ: {file_path}")
    print(f"🔍 מצב: {'OCR' if use_ocr else 'תמונה'}")
    print(f"📋 חלקים: {', '.join([s for s in ['INTRO' if process_intro else '', 'MAIN' if process_main else ''] if s])}")
    
    try:
        def progress_callback(message):
            print(f"🔄 {message}")
        
        # שימוש במעבד המלא החדש
        result = process_full_invoice(
            file_path=file_path,
            process_intro=process_intro,
            process_main=process_main,
            use_ocr=use_ocr,
            progress_callback=progress_callback
        )
        
        if result["success"]:
            print(f"✅ {result['message']}")
            if 'output_file' in result:
                print(f"📁 קובץ נשמר ב: {result['output_file']}")
            
            # הצגת סטטיסטיקות
            if 'summary' in result:
                summary = result['summary']
                print(f"⏱️ זמן עיבוד: {summary.get('processing_time_formatted', 'N/A')}")
                print(f"📊 חלקים שעובדו: {', '.join(summary.get('processed_sections', []))}")
                
                if 'intro_fields_extracted' in summary:
                    print(f"📝 שדות INTRO: {summary['intro_fields_extracted']} ({summary.get('intro_completeness', 0)}% שלמות)")
                
                if 'main_lines_extracted' in summary:
                    print(f"📋 שורות MAIN: {summary['main_lines_extracted']}")
        else:
            print(f"❌ {result['message']}")
            if 'error' in result:
                print(f"שגיאה: {result['error']}")
    
    except Exception as e:
        print(f"❌ שגיאה: {e}")


def main():
    """פונקציה ראשית"""
    print_welcome()
    print_system_info()
    
    # בדיקת תלויות
    if not check_dependencies():
        input("\nלחץ Enter לסגירה...")
        return
    
    # בדיקת הגדרות
    config_ok = check_config()
    
    print_instructions()
    
    # אם יש ארגומנטים - מצב CLI
    if len(sys.argv) > 1:
        run_cli_mode()
        return
    
    # אחרת - מצב גרפי
    if not config_ok:
        print("⚠️ יש בעיות בהגדרות, אך ניתן להמשיך")
        print("הממשק הגרפי יציג הודעות מתאימות")
        print()
    
    try:
        print("🚀 מפעיל ממשק גרפי...")
        create_and_run_gui()
        
    except KeyboardInterrupt:
        print("\n👋 נסגר על ידי המשתמש")
    except Exception as e:
        print(f"\n❌ שגיאה בהפעלת הממשק: {e}")
        print("\nניסיון פתרון:")
        print("1. ודא שכל הקבצים קיימים")
        print("2. בדוק שTkinter מותקן")
        print("3. הרץ: pip install --upgrade tkinter")
    
    print("\n👋 להתראות!")


if __name__ == "__main__":
    main()