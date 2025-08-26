"""
character_kpi_calculator.py - מחשבון KPI מתקדם ברמת תווים
"""

import json
from typing import Dict, List, Any, Tuple
from datetime import datetime


class CharacterKPICalculator:
    """מחשבון KPI מתקדם עם השוואה ברמת תווים"""
    
    def __init__(self):
        self.calculation_logs = []
        # שדות למדידה - סטנדרטיים
        self.measured_fields = [
            'barcode', 'item_code', 'description', 'quantity', 'unit_price', 
            'discount_percent', 'price_after_discount', 'total_amount'
        ]
    
    def log(self, message: str, level: str = "INFO"):
        """הוספת לוג למערכת"""
        self.calculation_logs.append({
            'timestamp': datetime.now().strftime("%H:%M:%S.%f")[:-3],
            'level': level,
            'message': message
        })
    
    def extract_main_items(self, json_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """חילוץ main_items מ-JSON"""
        if isinstance(json_data, dict):
            # נתיב 1: main.main_items
            if 'main' in json_data and isinstance(json_data['main'], dict):
                if 'main_items' in json_data['main']:
                    return json_data['main']['main_items']
            
            # נתיב 2: main_items ישיר
            if 'main_items' in json_data:
                return json_data['main_items']
            
            # נתיב 3: data
            if 'data' in json_data and isinstance(json_data['data'], list):
                return json_data['data']
        
        self.log(f"Could not find main_items in JSON structure", "WARNING")
        return []
    
    def compare_characters(self, ground_truth: str, predicted: str) -> Dict[str, Any]:
        """השוואת תווים ברמה גרנולרית"""
        gt_str = str(ground_truth).strip()
        pred_str = str(predicted).strip()
        
        # אם שניהם ריקים
        if not gt_str and not pred_str:
            return {
                'total_chars': 0,
                'correct_chars': 0,
                'accuracy': 1.0,
                'char_scores': []
            }
        
        # אם אחד מהם ריק
        if not gt_str or not pred_str:
            longer_str = gt_str or pred_str
            return {
                'total_chars': len(longer_str),
                'correct_chars': 0,
                'accuracy': 0.0,
                'char_scores': [0] * len(longer_str)
            }
        
        # השוואה תו-תו
        max_len = max(len(gt_str), len(pred_str))
        char_scores = []
        correct_chars = 0
        
        for i in range(max_len):
            gt_char = gt_str[i] if i < len(gt_str) else ''
            pred_char = pred_str[i] if i < len(pred_str) else ''
            
            if gt_char == pred_char:
                char_scores.append(1)
                correct_chars += 1
            else:
                char_scores.append(0)
        
        accuracy = correct_chars / max_len if max_len > 0 else 1.0
        
        return {
            'total_chars': max_len,
            'correct_chars': correct_chars,
            'accuracy': accuracy,
            'char_scores': char_scores
        }
    
    def calculate_line_kpis(self, ground_truth_line: Dict[str, Any], 
                           predicted_files_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """חישוב KPIs לשורה אחת"""
        line_results = {}
        
        for file_key, file_line_data in predicted_files_data.items():
            field_results = {}
            total_line_chars = 0
            correct_line_chars = 0
            measured_fields_count = 0
            
            for field in self.measured_fields:
                gt_value = ground_truth_line.get(field, '')
                
                # אם הערך ב-Ground Truth ריק - מדלגים על השדה הזה
                if not str(gt_value).strip():
                    self.log(f"Skipping empty field '{field}' in Ground Truth", "DEBUG")
                    continue
                
                pred_value = file_line_data.get(field, '')
                comparison_result = self.compare_characters(gt_value, pred_value)
                field_results[field] = comparison_result
                
                total_line_chars += comparison_result['total_chars']
                correct_line_chars += comparison_result['correct_chars']
                measured_fields_count += 1
            
            line_accuracy = correct_line_chars / total_line_chars if total_line_chars > 0 else 1.0
            
            line_results[file_key] = {
                'field_results': field_results,
                'line_accuracy': line_accuracy,
                'total_chars': total_line_chars,
                'correct_chars': correct_line_chars,
                'measured_fields': measured_fields_count
            }
            
            if measured_fields_count == 0:
                self.log(f"No fields to measure in line for file {file_key}", "WARNING")
        
        return line_results
    
    def calculate_global_kpis(self, ground_truth_data: List[Dict[str, Any]], 
                             predicted_files: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """חישוב KPIs גלובליים"""
        self.log("Starting global KPI calculation", "INFO")
        
        # בדיקת תואמות באורכים
        gt_lines_count = len(ground_truth_data)
        self.log(f"Ground truth lines: {gt_lines_count}", "INFO")
        
        for file_key, file_data in predicted_files.items():
            file_lines_count = len(file_data)
            self.log(f"File {file_key} lines: {file_lines_count}", "INFO")
            if file_lines_count != gt_lines_count:
                self.log(f"Length mismatch error: {file_key} has {file_lines_count} lines, GT has {gt_lines_count}", "ERROR")
        
        # יצירת מפה של שורות לפי line number
        gt_map = {item.get('line', i+1): item for i, item in enumerate(ground_truth_data)}
        files_map = {}
        all_line_numbers = set(gt_map.keys())
        
        for file_key, file_data in predicted_files.items():
            files_map[file_key] = {item.get('line', i+1): item for i, item in enumerate(file_data)}
            all_line_numbers.update(files_map[file_key].keys())
        
        self.log(f"Processing {len(all_line_numbers)} unique lines", "INFO")
        
        # חישוב KPIs לכל שורה
        global_results = {}
        
        for file_key in predicted_files.keys():
            total_chars = 0
            correct_chars = 0
            field_stats = {field: {'total_chars': 0, 'correct_chars': 0, 'measured_count': 0} for field in self.measured_fields}
            processed_lines = 0
            total_measured_fields = 0
            
            for line_num in sorted(all_line_numbers):
                if line_num not in gt_map:
                    self.log(f"Line {line_num} missing from ground truth", "WARNING")
                    continue
                
                if line_num not in files_map[file_key]:
                    self.log(f"Line {line_num} missing from file {file_key}", "WARNING")
                    continue
                
                gt_line = gt_map[line_num]
                pred_line = files_map[file_key][line_num]
                
                line_kpis = self.calculate_line_kpis(gt_line, {file_key: pred_line})
                file_line_result = line_kpis[file_key]
                
                total_chars += file_line_result['total_chars']
                correct_chars += file_line_result['correct_chars']
                processed_lines += 1
                total_measured_fields += file_line_result['measured_fields']
                
                # צבירת נתוני שדות - רק שדות שנמדדו בפועל
                for field, field_result in file_line_result['field_results'].items():
                    field_stats[field]['total_chars'] += field_result['total_chars']
                    field_stats[field]['correct_chars'] += field_result['correct_chars']
                    field_stats[field]['measured_count'] += 1
            
            # חישוב דיוק כולל
            overall_accuracy = correct_chars / total_chars if total_chars > 0 else 0.0
            
            # חישוב דיוק לכל שדה - רק שדות שנמדדו
            field_accuracies = {}
            for field, stats in field_stats.items():
                if stats['measured_count'] > 0:  # רק שדות שאכן נמדדו
                    field_accuracy = stats['correct_chars'] / stats['total_chars'] if stats['total_chars'] > 0 else 0.0
                    field_accuracies[field] = {
                        'accuracy': field_accuracy,
                        'total_chars': stats['total_chars'],
                        'correct_chars': stats['correct_chars'],
                        'measured_in_lines': stats['measured_count']
                    }
            
            global_results[file_key] = {
                'overall_accuracy': overall_accuracy,
                'total_characters': total_chars,
                'correct_characters': correct_chars,
                'processed_lines': processed_lines,
                'total_measured_fields': total_measured_fields,
                'field_accuracies': field_accuracies
            }
            
            self.log(f"File {file_key}: {overall_accuracy:.3f} accuracy ({correct_chars}/{total_chars} chars, {total_measured_fields} fields measured)", "INFO")
        
        return global_results
    
    def generate_detailed_report(self, kpi_results: Dict[str, Any]) -> str:
        """יצירת דוח מפורט"""
        report_lines = []
        report_lines.append("=== DETAILED CHARACTER-LEVEL KPI REPORT ===\n")
        
        # סיכום כללי
        report_lines.append("SUMMARY:")
        for file_key, results in kpi_results.items():
            accuracy = results['overall_accuracy']
            total_chars = results['total_characters']
            correct_chars = results['correct_characters']
            measured_fields = results.get('total_measured_fields', 0)
            
            report_lines.append(f"  {file_key}: {accuracy:.1%} ({correct_chars:,}/{total_chars:,} chars, {measured_fields} fields)")
        
        report_lines.append("")
        
        # פירוט לכל קובץ
        for file_key, results in kpi_results.items():
            report_lines.append(f"--- {file_key} DETAILED ANALYSIS ---")
            report_lines.append(f"Overall Accuracy: {results['overall_accuracy']:.3f}")
            report_lines.append(f"Total Characters: {results['total_characters']:,}")
            report_lines.append(f"Correct Characters: {results['correct_characters']:,}")
            report_lines.append(f"Processed Lines: {results['processed_lines']}")
            report_lines.append(f"Total Measured Fields: {results.get('total_measured_fields', 0)}")
            report_lines.append("")
            
            report_lines.append("Field-by-Field Breakdown (only measured fields):")
            field_accuracies = results.get('field_accuracies', {})
            if field_accuracies:
                for field, field_data in field_accuracies.items():
                    acc = field_data['accuracy']
                    total = field_data['total_chars']
                    correct = field_data['correct_chars']
                    lines_measured = field_data.get('measured_in_lines', 0)
                    report_lines.append(f"  {field}: {acc:.3f} ({correct}/{total} chars in {lines_measured} lines)")
            else:
                report_lines.append("  No fields were measured (all Ground Truth fields were empty)")
            
            report_lines.append("")
        
        return "\n".join(report_lines)
    
    def get_logs(self) -> List[Dict[str, str]]:
        """קבלת כל הלוגים"""
        return self.calculation_logs.copy()
    
    def clear_logs(self):
        """ניקוי לוגים"""
        self.calculation_logs.clear()


def main():
    """בדיקה של המחלקה"""
    calculator = CharacterKPICalculator()
    
    # דוגמה
    gt_line = {'item_code': 'ABC123', 'description': 'Product A', 'quantity': 10}
    pred_files = {
        'file1': {'item_code': 'ABC123', 'description': 'Product B', 'quantity': 10},
        'file2': {'item_code': 'ABC124', 'description': 'Product A', 'quantity': 11}
    }
    
    result = calculator.calculate_line_kpis(gt_line, pred_files)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()