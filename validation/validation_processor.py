"""
validation_processor.py - מעבד תהליכי הוולידציה
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from .character_kpi_calculator import CharacterKPICalculator


class ValidationProcessor:
    """מעבד תהליכי הוולידציה"""
    
    def __init__(self):
        self.kpi_calculator = CharacterKPICalculator()
        self.loaded_files = {}  # {file_key: json_data}
        self.ground_truth_data = None
        self.validation_results = None
        
    def load_json_files(self, file_paths: List[str]) -> Dict[str, bool]:
        """טעינת קבצי JSON (1-5 קבצים)"""
        if len(file_paths) > 5:
            raise ValueError("Maximum 5 JSON files allowed")
        
        results = {}
        self.loaded_files.clear()
        
        for file_path in file_paths:
            try:
                file_key = Path(file_path).stem
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.loaded_files[file_key] = data
                results[file_key] = True
                self.kpi_calculator.log(f"Loaded file: {file_key}", "INFO")
                
            except Exception as e:
                results[Path(file_path).stem] = False
                self.kpi_calculator.log(f"Failed to load {file_path}: {str(e)}", "ERROR")
        
        self.kpi_calculator.log(f"Total files loaded: {len(self.loaded_files)}", "INFO")
        return results
    
    def load_ground_truth(self, ground_truth_path: str = None, 
                         ground_truth_data: List[Dict[str, Any]] = None) -> bool:
        """טעינת נתוני Ground Truth"""
        try:
            if ground_truth_path:
                with open(ground_truth_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # חילוץ main_items מקובץ Ground Truth
                if isinstance(data, dict):
                    if 'ground_truth' in data:
                        self.ground_truth_data = data['ground_truth']
                    elif 'main_items' in data:
                        self.ground_truth_data = data['main_items']
                    elif 'main' in data and 'main_items' in data['main']:
                        self.ground_truth_data = data['main']['main_items']
                    else:
                        self.ground_truth_data = [data]  # קובץ בודד
                elif isinstance(data, list):
                    self.ground_truth_data = data
                    
                self.kpi_calculator.log(f"Ground truth loaded from file: {len(self.ground_truth_data)} lines", "INFO")
                
            elif ground_truth_data:
                self.ground_truth_data = ground_truth_data
                self.kpi_calculator.log(f"Ground truth loaded from data: {len(self.ground_truth_data)} lines", "INFO")
            
            return True
            
        except Exception as e:
            self.kpi_calculator.log(f"Failed to load ground truth: {str(e)}", "ERROR")
            return False
    
    def extract_all_fields_template(self) -> Dict[str, List[str]]:
        """חילוץ template של כל השדות מהקבצים הטעונים"""
        # שדות סטנדרטיים שתמיד חייבים להיות
        standard_fields = [
            'barcode', 'item_code', 'description', 'quantity', 
            'unit_price', 'discount_percent', 'price_after_discount', 'total_amount'
        ]
        
        all_fields = set(standard_fields)
        line_numbers = set()
        
        # איסוף שדות נוספים מהקבצים
        for file_key, file_data in self.loaded_files.items():
            items = self.kpi_calculator.extract_main_items(file_data)
            for item in items:
                all_fields.update(item.keys())
                line_numbers.add(item.get('line', 1))
        
        # וידוא שיש לפחות שורה אחת אם אין קבצים
        if not line_numbers:
            line_numbers.add(1)
        
        # יצירת template לכל שורה עם כל השדות הסטנדרטיים
        template = {}
        sorted_lines = sorted(line_numbers)
        sorted_fields = sorted([field for field in all_fields if field != 'line'])
        
        # וידוא שהשדות הסטנדרטיים נמצאים ראשונים
        final_fields = []
        for field in standard_fields:
            if field in sorted_fields:
                final_fields.append(field)
        
        # הוספת שדות נוספים שאולי נמצאו
        for field in sorted_fields:
            if field not in standard_fields:
                final_fields.append(field)
        
        for line_num in sorted_lines:
            template[f"line_{line_num}"] = {field: "" for field in final_fields}
        
        self.kpi_calculator.log(f"Generated template: {len(sorted_lines)} lines, {len(final_fields)} fields (including all standard fields)", "INFO")
        return {
            'template': template,
            'fields': final_fields,
            'lines': sorted_lines
        }
    
    def run_validation(self) -> Dict[str, Any]:
        """הרצת תהליך הוולידציה המלא"""
        if not self.loaded_files:
            raise ValueError("No JSON files loaded")
        
        if not self.ground_truth_data:
            raise ValueError("No ground truth data available")
        
        self.kpi_calculator.log("Starting validation process", "INFO")
        
        # חילוץ main_items מכל קובץ
        predicted_files = {}
        for file_key, file_data in self.loaded_files.items():
            items = self.kpi_calculator.extract_main_items(file_data)
            predicted_files[file_key] = items
            self.kpi_calculator.log(f"Extracted {len(items)} items from {file_key}", "INFO")
        
        # הרצת חישוב KPIs
        kpi_results = self.kpi_calculator.calculate_global_kpis(
            self.ground_truth_data, 
            predicted_files
        )
        
        # יצירת דוח מפורט
        detailed_report = self.kpi_calculator.generate_detailed_report(kpi_results)
        
        self.validation_results = {
            'kpi_results': kpi_results,
            'detailed_report': detailed_report,
            'ground_truth_lines': len(self.ground_truth_data),
            'files_processed': len(predicted_files),
            'timestamp': datetime.now().isoformat(),
            'logs': self.kpi_calculator.get_logs()
        }
        
        self.kpi_calculator.log("Validation process completed", "INFO")
        return self.validation_results
    
    def get_comparison_summary(self) -> Dict[str, Any]:
        """קבלת סיכום השוואה קצר"""
        if not self.validation_results:
            return {}
        
        kpi_results = self.validation_results['kpi_results']
        summary = {}
        
        for file_key, results in kpi_results.items():
            summary[file_key] = {
                'accuracy': results['overall_accuracy'],
                'accuracy_percent': f"{results['overall_accuracy']:.1%}",
                'rank': 0  # יחושב אחר כך
            }
        
        # דירוג לפי דיוק
        sorted_files = sorted(summary.items(), key=lambda x: x[1]['accuracy'], reverse=True)
        for i, (file_key, data) in enumerate(sorted_files):
            summary[file_key]['rank'] = i + 1
        
        return summary
    
    def export_results(self, output_path: str) -> bool:
        """יצוא תוצאות לקובץ"""
        if not self.validation_results:
            return False
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(self.validation_results, f, ensure_ascii=False, indent=2)
            
            self.kpi_calculator.log(f"Results exported to: {output_path}", "INFO")
            return True
            
        except Exception as e:
            self.kpi_calculator.log(f"Export failed: {str(e)}", "ERROR")
            return False
    
    def get_field_comparison_details(self, file_key: str) -> Dict[str, Any]:
        """קבלת פירוט השוואה לכל שדה"""
        if not self.validation_results or file_key not in self.validation_results['kpi_results']:
            return {}
        
        file_results = self.validation_results['kpi_results'][file_key]
        field_details = {}
        
        for field_name, field_data in file_results['field_accuracies'].items():
            field_details[field_name] = {
                'accuracy': field_data['accuracy'],
                'accuracy_percent': f"{field_data['accuracy']:.1%}",
                'total_chars': field_data['total_chars'],
                'correct_chars': field_data['correct_chars'],
                'error_chars': field_data['total_chars'] - field_data['correct_chars']
            }
        
        return field_details
    
    def clear_data(self):
        """ניקוי כל הנתונים"""
        self.loaded_files.clear()
        self.ground_truth_data = None
        self.validation_results = None
        self.kpi_calculator.clear_logs()
        self.kpi_calculator.log("All data cleared", "INFO")


def main():
    """בדיקה של המחלקה"""
    processor = ValidationProcessor()
    
    # דוגמה לשימוש
    try:
        # טעינת קבצים
        files = ["file1.json", "file2.json"]
        load_results = processor.load_json_files(files)
        print("Load results:", load_results)
        
        # יצירת ground truth דמה
        gt_data = [
            {"line": 1, "item_code": "ABC123", "description": "Product A"},
            {"line": 2, "item_code": "DEF456", "description": "Product B"}
        ]
        processor.load_ground_truth(ground_truth_data=gt_data)
        
        # הרצת validation (ייכשל כי אין קבצים אמיתיים)
        # results = processor.run_validation()
        
    except Exception as e:
        print("Demo error (expected):", str(e))


if __name__ == "__main__":
    main()