"""
run_validation.py - הפעלת מערכת הוולידציה המתקדמת
"""

import sys
from pathlib import Path

# הוספת התיקייה הראשית ל-Python path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from validation import AdvancedValidationGUI


def main():
    """הפעלת מערכת הוולידציה"""
    try:
        print("Starting Advanced Validation Suite...")
        app = AdvancedValidationGUI()
        app.run()
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure all validation files are in the validation/ directory")
    except Exception as e:
        print(f"Error starting validation suite: {e}")


if __name__ == "__main__":
    main()