"""
enhanced_validation_processor.py - מעבד תהליכי וולידציה מעודכן עם תמיכה בשתי שיטות
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

from character_kpi_calculator import CharacterKPICalculator
from business_validation_adapter import BusinessValidationAdapter


class ValidationMethod(Enum):
    """סוגי שיטות וולידציה"""
    CHARACTER_LEVEL = "character_level"
    BUSINESS_LOGIC = "business_logic"
    BOTH = "both"


class EnhancedValidationProcessor:
    """מעבד תהליכי וולידציה משופר עם תמיכה בשתי שיטות"""
    
    def __init__(self):
        self.kpi_calculator = CharacterKPICalculator()
        self.business_adapter = BusinessValidationAdapter()
        self.loaded_files = {}  # {file_key: json_data}
        self.ground_truth_data = None
        self.validation_results = None
        self.extracted_files_data = {}  # נתונים מחולצים מהקבצים
        self.validation_method = ValidationMethod.CHARACTER_LEVEL  # ברירת מחדל
        
    def set_validation_method(self, method: ValidationMethod):
        """הגדרת שיטת הוולידציה"""
        self.validation_method = method
        self.kpi_calculator.log(f"Validation method set to: {method.value}", "INFO")
    
    def get_validation_method(self) -> ValidationMethod:
        """קבלת שיטת הוולידציה הנוכחית"""
        return self.validation_method
        
    def load_json_files(self, file_paths: List[str]) -> Dict[str, bool]:
        """טעינת קבצי JSON (1-5 קבצים)"""
        if len(file_paths) > 5:
            raise ValueError("Maximum 5 JSON files allowed")
        
        results = {}
        self.loaded_files.clear()
        self.extracted_files_data.clear()
        
        for file_path in file_paths:
            try:
                file_key = Path(file_path).stem
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.loaded_files[file_key] = data
                
                # חילוץ main_items מיד
                extracted_items = self.kpi_calculator.extract_main_items(data)
                self.extracted_files_data[file_key] = extracted_items
                
                results[file_key] = True
                self.kpi_calculator.log(f"Loaded file: {file_key} ({len(extracted_items)} items)", "INFO")
                
            except Exception as e:
                results[Path(file_path).stem] = False
                self.kpi_calculator.log(f"Failed to load {file_path}: {str(e)}", "ERROR")
        
        self.kpi_calculator.log(f"Total files loaded: {len(self.loaded_files)}", "INFO")
        return results
    
    def load_ground_truth(self, ground_truth_path: str = None, 
                         ground_truth_data: List[Dict[str, Any]] = None) -> bool:
        """טעינת נתוני Ground Truth - נדרש רק לוולידציה ברמת תווים"""
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
    
    def is_ground_truth_required(self) -> bool:
        """בדיקה האם נדרש Ground Truth לשיטת הוולידציה הנבחרת"""
        return self.validation_method in [ValidationMethod.CHARACTER_LEVEL, ValidationMethod.BOTH]
    
    def can_run_validation(self) -> bool:
        """בדיקה האם ניתן להריץ וולידציה"""
        if not self.extracted_files_data:
            return False
        
        # אם נבחרה וולידציה עסקית בלבד, לא נדרש Ground Truth
        if self.validation_method == ValidationMethod.BUSINESS_LOGIC:
            return True
        
        # אחרת נדרש Ground Truth
        return self.ground_truth_data is not None
    
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
        for file_key, items in self.extracted_files_data.items():
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
        """הרצת תהליך וולידציה המלא לפי השיטה הנבחרת"""
        if not self.extracted_files_data:
            raise ValueError("No JSON files loaded")
        
        validation_results = {
            'method_used': self.validation_method.value,
            'timestamp': datetime.now().isoformat(),
            'files_processed': len(self.extracted_files_data)
        }
        
        self.kpi_calculator.log(f"Starting validation process with method: {self.validation_method.value}", "INFO")
        
        # הרצת וולידציה לפי השיטה הנבחרת
        if self.validation_method == ValidationMethod.CHARACTER_LEVEL:
            validation_results.update(self.run_character_validation())
            
        elif self.validation_method == ValidationMethod.BUSINESS_LOGIC:
            validation_results.update(self.run_business_validation())
            
        elif self.validation_method == ValidationMethod.BOTH:
            # הרצת שתי הוולידציות
            char_results = self.run_character_validation()
            business_results = self.run_business_validation()
            
            # שילוב התוצאות
            validation_results.update({
                'character_level': char_results,
                'business_logic': business_results,
                'combined_analysis': self.combine_validation_results(char_results, business_results)
            })
        
        # שמירת התוצאות
        self.validation_results = validation_results
        
        self.kpi_calculator.log("Validation process completed", "INFO")
        return validation_results
    
    def run_character_validation(self) -> Dict[str, Any]:
        """הרצת וולידציה ברמת תווים"""
        if not self.ground_truth_data:
            raise ValueError("No ground truth data available for character-level validation")
        
        self.kpi_calculator.log("Running character-level validation", "INFO")
        
        # הרצת חישוב KPIs
        kpi_results = self.kpi_calculator.calculate_global_kpis(
            self.ground_truth_data, 
            self.extracted_files_data
        )
        
        # יצירת דוח מפורט
        detailed_report = self.kpi_calculator.generate_detailed_report(kpi_results)
        
        # הכנת נתונים לטבלה המורחבת
        expanded_table_data = self.prepare_expanded_table_data(kpi_results)
        
        return {
            'type': 'character_level',
            'kpi_results': kpi_results,
            'detailed_report': detailed_report,
            'expanded_table_data': expanded_table_data,
            'ground_truth_lines': len(self.ground_truth_data),
            'character_logs': self.kpi_calculator.get_logs()
        }
    
    def run_business_validation(self) -> Dict[str, Any]:
        """הרצת וולידציה עסקית"""
        self.kpi_calculator.log("Running business logic validation", "INFO")
        
        # הרצת וולידציה עסקית
        business_results = self.business_adapter.validate_business_logic(self.extracted_files_data)
        
        # יצירת דוח עסקי
        business_report = self.business_adapter.generate_business_validation_report(business_results)
        
        # חישוב סטטיסטיקות כלליות
        total_files = len(business_results)
        successful_validations = sum(1 for r in business_results.values() if r.get('success', False))
        average_score = 0
        
        if successful_validations > 0:
            scores = [r.get('score', 0) for r in business_results.values() if r.get('success', False)]
            average_score = sum(scores) / len(scores)
        
        return {
            'type': 'business_logic',
            'business_results': business_results,
            'detailed_report': business_report,
            'statistics': {
                'total_files': total_files,
                'successful_validations': successful_validations,
                'failed_validations': total_files - successful_validations,
                'average_score': average_score
            },
            'business_logs': self.business_adapter.get_logs()
        }
    
    def combine_validation_results(self, char_results: Dict[str, Any], business_results: Dict[str, Any]) -> Dict[str, Any]:
        """שילוב תוצאות משתי השיטות"""
        combined = {
            'files_analysis': {},
            'overall_summary': {}
        }
        
        # ניתוח לכל קובץ
        for file_key in self.extracted_files_data.keys():
            file_analysis = {
                'file_name': file_key
            }
            
            # נתוני וולידציה ברמת תווים
            if file_key in char_results.get('kpi_results', {}):
                char_data = char_results['kpi_results'][file_key]
                file_analysis['character_accuracy'] = char_data['overall_accuracy']
                file_analysis['character_score'] = f"{char_data['overall_accuracy']:.1%}"
            
            # נתוני וולידציה עסקית
            if file_key in business_results.get('business_results', {}):
                business_data = business_results['business_results'][file_key]
                if business_data.get('success', False):
                    file_analysis['business_score'] = business_data['score']
                    file_analysis['business_status'] = business_data['status']
                    file_analysis['business_issues'] = len(business_data.get('issues', []))
                else:
                    file_analysis['business_score'] = 0
                    file_analysis['business_status'] = 'FAILED'
                    file_analysis['business_error'] = business_data.get('error', 'Unknown error')
            
            # ציון משוקלל (אם יש נתונים משתי השיטות)
            if 'character_accuracy' in file_analysis and 'business_score' in file_analysis:
                char_weight = 0.6  # משקל גבוה יותר לדיוק תווים
                business_weight = 0.4
                combined_score = (
                    file_analysis['character_accuracy'] * char_weight + 
                    file_analysis['business_score'] / 100 * business_weight
                )
                file_analysis['combined_score'] = f"{combined_score:.1%}"
            
            combined['files_analysis'][file_key] = file_analysis
        
        # סיכום כללי
        char_avg = sum(
            analysis.get('character_accuracy', 0) 
            for analysis in combined['files_analysis'].values()
        ) / len(combined['files_analysis'])
        
        business_avg = business_results['statistics']['average_score'] / 100
        
        combined['overall_summary'] = {
            'average_character_accuracy': f"{char_avg:.1%}",
            'average_business_score': f"{business_avg:.1%}",
            'files_analyzed': len(combined['files_analysis'])
        }
        
        return combined
    
    def prepare_expanded_table_data(self, kpi_results: Dict[str, Any]) -> Dict[str, Any]:
        """הכנת נתונים לטבלה המורחבת - רק לוולידציה ברמת תווים"""
        expanded_data = {
            'columns': [],
            'rows': []
        }
        
        file_keys = list(kpi_results.keys())
        
        # בניית עמודות
        expanded_data['columns'] = ['field', 'source_data']
        for file_key in file_keys:
            expanded_data['columns'].extend([f'{file_key}_result', f'{file_key}_score'])
        expanded_data['columns'].append('overall_score')
        
        # איסוף כל השדות הייחודיים
        all_fields = set()
        for file_key in file_keys:
            if 'field_accuracies' in kpi_results[file_key]:
                all_fields.update(kpi_results[file_key]['field_accuracies'].keys())
        
        # איסוף נתוני מקור (Ground Truth) לפי שדה
        gt_by_field = self.organize_ground_truth_by_field()
        
        # בניית שורות הנתונים
        for field in sorted(all_fields):
            row_data = {
                'field': field,
                'source_data': self.format_source_data(gt_by_field.get(field, [])),
                'file_results': {},
                'overall_score': 0
            }
            
            field_scores = []
            for file_key in file_keys:
                if field in kpi_results[file_key].get('field_accuracies', {}):
                    field_data = kpi_results[file_key]['field_accuracies'][field]
                    accuracy = field_data['accuracy']
                    
                    row_data['file_results'][file_key] = {
                        'result': f"{field_data['correct_chars']}/{field_data['total_chars']}",
                        'score': f"{accuracy:.1%}",
                        'accuracy_numeric': accuracy
                    }
                    field_scores.append(accuracy)
                else:
                    row_data['file_results'][file_key] = {
                        'result': "-",
                        'score': "-",
                        'accuracy_numeric': 0
                    }
                    field_scores.append(0)
            
            # חישוב ציון כללי לשדה
            if field_scores:
                row_data['overall_score'] = sum(field_scores) / len(field_scores)
            
            expanded_data['rows'].append(row_data)
        
        return expanded_data
    
    def organize_ground_truth_by_field(self) -> Dict[str, List[str]]:
        """ארגון נתוני Ground Truth לפי שדה"""
        gt_by_field = {}
        
        if not self.ground_truth_data:
            return gt_by_field
        
        for gt_item in self.ground_truth_data:
            for field, value in gt_item.items():
                if field != 'line' and value is not None:
                    if field not in gt_by_field:
                        gt_by_field[field] = []
                    gt_by_field[field].append(str(value))
        
        return gt_by_field
    
    def format_source_data(self, values: List[str]) -> str:
        """עיצוב נתוני המקור לתצוגה"""
        if not values:
            return "-"
        
        # הצגת עד 2 ערכים ראשונים
        if len(values) <= 2:
            return ', '.join(values)
        else:
            return f"{', '.join(values[:2])} ועוד {len(values)-2}..."
    
    def get_expanded_table_data(self) -> Optional[Dict[str, Any]]:
        """קבלת נתוני הטבלה המורחבת"""
        if not self.validation_results:
            return None
        
        return self.validation_results.get('expanded_table_data')
    
    def get_comparison_summary(self) -> Dict[str, Any]:
        """קבלת סיכום השוואה קצר - מותאם לשיטת הוולידציה"""
        if not self.validation_results:
            return {}
        
        summary = {}
        
        if self.validation_method == ValidationMethod.CHARACTER_LEVEL:
            kpi_results = self.validation_results['kpi_results']
            for file_key, results in kpi_results.items():
                summary[file_key] = {
                    'accuracy': results['overall_accuracy'],
                    'accuracy_percent': f"{results['overall_accuracy']:.1%}",
                    'type': 'character',
                    'rank': 0  # יחושב אחר כך
                }
        
        elif self.validation_method == ValidationMethod.BUSINESS_LOGIC:
            business_results = self.validation_results['business_results']
            for file_key, results in business_results.items():
                if results.get('success', False):
                    score = results['score'] / 100
                    summary[file_key] = {
                        'accuracy': score,
                        'accuracy_percent': f"{score:.1%}",
                        'status': results['status'],
                        'type': 'business',
                        'rank': 0
                    }
                else:
                    summary[file_key] = {
                        'accuracy': 0,
                        'accuracy_percent': "0%",
                        'status': 'FAILED',
                        'error': results.get('error', 'Unknown error'),
                        'type': 'business',
                        'rank': 999  # דירוג נמוך לקבצים כושלים
                    }
        
        elif self.validation_method == ValidationMethod.BOTH:
            combined_analysis = self.validation_results['combined_analysis']['files_analysis']
            for file_key, analysis in combined_analysis.items():
                if 'combined_score' in analysis:
                    combined_score = float(analysis['combined_score'].rstrip('%')) / 100
                    summary[file_key] = {
                        'accuracy': combined_score,
                        'accuracy_percent': analysis['combined_score'],
                        'character_score': f"{analysis.get('character_accuracy', 0):.1%}",
                        'business_score': f"{analysis.get('business_score', 0)}",
                        'business_status': analysis.get('business_status', 'N/A'),
                        'type': 'combined',
                        'rank': 0
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
            # הוספת מידע נוסף לייצוא
            export_data = self.validation_results.copy()
            export_data['export_metadata'] = {
                'exported_at': datetime.now().isoformat(),
                'validation_method': self.validation_method.value,
                'files_exported': list(self.extracted_files_data.keys()),
                'ground_truth_required': self.is_ground_truth_required(),
                'ground_truth_count': len(self.ground_truth_data) if self.ground_truth_data else 0
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            self.kpi_calculator.log(f"Results exported to: {output_path}", "INFO")
            return True
            
        except Exception as e:
            self.kpi_calculator.log(f"Export failed: {str(e)}", "ERROR")
            return False
    
    def get_field_comparison_details(self, file_key: str) -> Dict[str, Any]:
        """קבלת פירוט השוואה לכל שדה - רק לוולידציה ברמת תווים"""
        if (self.validation_method == ValidationMethod.BUSINESS_LOGIC or
            not self.validation_results or 
            'kpi_results' not in self.validation_results):
            return {}
        
        kpi_results = self.validation_results.get('kpi_results', {})
        if self.validation_method == ValidationMethod.BOTH:
            kpi_results = self.validation_results['character_level'].get('kpi_results', {})
        
        if file_key not in kpi_results:
            return {}
        
        file_results = kpi_results[file_key]
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
        self.extracted_files_data.clear()
        self.ground_truth_data = None
        self.validation_results = None
        self.kpi_calculator.clear_logs()
        self.business_adapter.clear_logs()
        self.kpi_calculator.log("All data cleared", "INFO")


def main():
    """בדיקה של המחלקה"""
    processor = EnhancedValidationProcessor()
    
    # דוגמה לשימוש
    try:
        # בחירת שיטת וולידציה
        processor.set_validation_method(ValidationMethod.BUSINESS_LOGIC)
        
        # בדיקה האם נדרש Ground Truth
        print(f"Ground Truth required: {processor.is_ground_truth_required()}")
        print(f"Can run validation: {processor.can_run_validation()}")
        
    except Exception as e:
        print("Demo error:", str(e))


if __name__ == "__main__":
    main()
    
    ValidationProcessor = EnhancedValidationProcessor