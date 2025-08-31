#!/usr/bin/env python3
"""
main_validation_app.py - אפליקציית הווליזציה הראשית
"""

import sys
import os
from pathlib import Path

# הוספת הנתיב הנוכחי ל-sys.path כדי לאפשר import של המודולים
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

try:
    from enhanced_validation_gui import EnhancedValidationGUI
    from enhanced_validation_processor import EnhancedValidationProcessor
    from character_kpi_calculator import CharacterKPICalculator

except ImportError as e:
    print(f"שגיאה בטעינת מודולים: {e}")
    print("וודא שכל הקבצים הנדרשים קיימים באותה תיקיה:")
    print("- enhanced_validation_gui.py")
    print("- enhanced_validation_processor.py") 
    print("- character_kpi_calculator.py")
    sys.exit(1)


def check_dependencies():
    """בדיקת תלויות נדרשות"""
    required_modules = ['tkinter', 'json', 'pathlib', 'threading', 'typing']
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        print(f"מודולים חסרים: {', '.join(missing_modules)}")
        return False
    
    return True


def create_data_directory():
    """יצירת תיקיית נתונים אם לא קיימת"""
    data_dir = Path("validation_data")
    data_dir.mkdir(exist_ok=True)
    
    # יצירת תת-תיקיות
    (data_dir / "exports").mkdir(exist_ok=True)
    (data_dir / "templates").mkdir(exist_ok=True)
    (data_dir / "logs").mkdir(exist_ok=True)
    
    return data_dir


def main():
    """פונקציה ראשית"""
    print("🔧 מתחיל אפליקציית וולידציה מתקדמת...")
    
    # בדיקת תלויות
    if not check_dependencies():
        print("❌ שגיאה: תלויות חסרות")
        sys.exit(1)
    
    # יצירת תיקיית נתונים
    try:
        data_dir = create_data_directory()
        print(f"📁 תיקיית נתונים: {data_dir}")
    except Exception as e:
        print(f"❌ שגיאה ביצירת תיקיית נתונים: {e}")
        sys.exit(1)
    
    # הפעלת האפליקציה
    try:
        print("🚀 מפעיל ממשק משתמש...")
        app = EnhancedValidationGUI()
        app.run()
        
    except Exception as e:
        print(f"❌ שגיאה בהפעלת האפליקציה: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("✅ האפליקציה הסתיימה בהצלחה")


if __name__ == "__main__":
    main()