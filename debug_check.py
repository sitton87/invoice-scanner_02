# debug_check.py - בדיקה איזה מעבד רץ

import sys
from pathlib import Path

# בדיקת ספריות
missing_libs = []

try:
    import imutils
    print("✅ imutils מותקן")
except ImportError:
    missing_libs.append("imutils")
    print("❌ imutils חסר")

try:
    import pdfplumber  
    print("✅ pdfplumber מותקן")
except ImportError:
    missing_libs.append("pdfplumber")
    print("❌ pdfplumber חסר")

# בדיקת קבצים
files_to_check = [
    "ui.py",
    "full_processor.py", 
    "ocr_processor.py",
    "hybrid_processor.py"
]

print("\n📁 קבצים שקיימים:")
for file_name in files_to_check:
    if Path(file_name).exists():
        print(f"✅ {file_name}")
    else:
        print(f"❌ {file_name}")

# בדיקת imports ב-ui.py
print("\n🔍 בדיקת imports ב-ui.py:")
try:
    with open("ui.py", "r", encoding="utf-8") as f:
        content = f.read()
        
    if "from hybrid_processor import" in content:
        print("✅ ui.py מנסה לייבא מhybrid_processor")
    elif "from ocr_processor import" in content:  
        print("⚠️ ui.py מייבא מocr_processor הישן")
    elif "from full_processor import" in content:
        print("⚠️ ui.py מייבא מfull_processor")
    else:
        print("❓ לא מצאתי import למעבד")
        
except Exception as e:
    print(f"❌ שגיאה בקריאת ui.py: {e}")

if missing_libs:
    print(f"\n🔧 להתקין: pip install {' '.join(missing_libs)}")
else:
    print("\n✅ כל הספריות מותקנות!")

# בדיקת הפרומפט הנוכחי
print("\n📝 בדיקת פרומפט ב-config.py:")
try:
    with open("config.py", "r", encoding="utf-8") as f:
        content = f.read()
        
    if "מימין לשמאל" in content:
        print("✅ פרומפט מכיל הוראות כיוון")
    else:
        print("❌ פרומפט לא מכיל הוראות כיוון")
        
    if "עמודות נפוץ" in content or "עמודות נפוצות" in content:
        print("✅ פרומפט מכיל הסבר עמודות")
    else:
        print("❌ פרומפט לא מכיל הסבר עמודות")
    
    if "אל תחשב" in content:
        print("✅ פרומפט מכיל הוראות לא לחשב")
    else:
        print("❌ פרומפט לא מכיל הוראות לא לחשב")
        
    if "45.00 שק" in content:
        print("✅ פרומפט מכיל דוגמאות ספציפיות")
    else:
        print("❌ פרומפט לא מכיל דוגמאות ספציפיות")
        
    # בדיקה שהפרומפט נקרא נכון
    try:
        from config import SYSTEM_PROMPT, USER_PROMPT
        print("✅ SYSTEM_PROMPT נקרא בהצלחה")
        if "אל תחשב" in SYSTEM_PROMPT:
            print("✅ SYSTEM_PROMPT מכיל הוראות נכונות")
        else:
            print("❌ SYSTEM_PROMPT לא מכיל הוראות נכונות")
            
        print("✅ USER_PROMPT נקרא בהצלחה")
    except Exception as e:
        print(f"❌ שגיאה בייבוא פרומפטים: {e}")
        
except Exception as e:
    print(f"❌ שגיאה בקריאת config.py: {e}")

print("\n" + "="*50)
print("💡 סיכום הבעיה:")
if missing_libs:
    print("❌ חסרות ספריות - המעבד ההיברידי לא רץ")
    print("🔧 פתרון: התקן הספריות או תשפר את הפרומפט הקיים")
else:
    print("✅ הספריות מותקנות - הבעיה כנראה בפרומפט")
    print("🔧 פתרון: שפר את הפרומפט לזיהוי נכון של כיוון הטבלה")