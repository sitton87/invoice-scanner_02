"""
business_validation_adapter.py - מתאם בין המערכת העסקית למערכת הוולידציה הקיימת
"""

from typing import Dict, List, Any, Optional
from decimal import Decimal
import json
from datetime import datetime

# ייבוא המערכת העסקית
from validation.schemas import Invoice, LineItem, InvoiceIntro, InvoiceFinal
from validation.validator import BusinessValidator
from validation.rules import run_all_rules


class BusinessValidationAdapter:
    """מתאם המחבר בין מבנה הנתונים הקיים לוולידציה העסקית"""
    
    def __init__(self):
        self.validator = BusinessValidator()
        self.conversion_logs = []
    
    def log(self, message: str, level: str = "INFO"):
        """הוספת לוג למערכת"""
        self.conversion_logs.append({
            'timestamp': datetime.now().strftime("%H:%M:%S.%f")[:-3],
            'level': level,
            'message': message
        })
    
    def convert_json_to_invoice(self, json_data: Dict[str, Any]) -> Optional[Invoice]:
        """המרת נתוני JSON לאובייקט Invoice לוולידציה עסקית"""
        try:
            # חילוץ main_items מהנתונים
            main_items = self.extract_main_items(json_data)
            if not main_items:
                self.log("No main_items found in JSON data", "ERROR")
                return None
            
            # המרת שורות לפורמט LineItem
            lines = []
            for i, item in enumerate(main_items):
                try:
                    line = self.convert_item_to_line_item(item, i + 1)
                    if line:
                        lines.append(line)
                except Exception as e:
                    self.log(f"Failed to convert line {i+1}: {str(e)}", "ERROR")
                    continue
            
            if not lines:
                self.log("No valid lines found after conversion", "ERROR")
                return None
            
            # יצירת intro (מידע כללי על החשבונית)
            intro = self.extract_invoice_intro(json_data)
            
            # יצירת final (סיכום כספי)
            final = self.extract_invoice_final(json_data, lines)
            
            # יצירת אובייקט Invoice
            invoice = Invoice(
                intro=intro,
                lines=lines,
                final=final
            )
            
            self.log(f"Successfully converted invoice with {len(lines)} lines", "INFO")
            return invoice
            
        except Exception as e:
            self.log(f"Failed to convert JSON to Invoice: {str(e)}", "ERROR")
            return None
    
    def extract_main_items(self, json_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """חילוץ main_items מהנתונים (נוסח מקורי מהמערכת הקיימת)"""
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
        
        return []
    
    def convert_item_to_line_item(self, item: Dict[str, Any], line_no: int) -> Optional[LineItem]:
        """המרת item יחיד לאובייקט LineItem"""
        try:
            # שדות חובה
            description = str(item.get('description', '')).strip()
            if not description:
                raise ValueError("Missing description")
            
            qty = self.safe_decimal(item.get('quantity', 1))
            unit_price = self.safe_decimal(item.get('unit_price', 0))
            
            # שדות אופציונליים
            discount_pct = self.safe_decimal(item.get('discount_percent', 0))
            vat_pct = self.safe_decimal(item.get('vat_percent', 17))
            line_total = self.safe_decimal(item.get('total_amount', 0))
            
            # אם line_total לא סופק, נחשב אותו
            if line_total == 0:
                price_after_discount = unit_price * (1 - discount_pct / 100)
                line_total = qty * price_after_discount
            
            line_item = LineItem(
                line_no=line_no,
                barcode=item.get('barcode'),
                item_code=item.get('item_code'),
                description=description,
                qty=qty,
                unit_price=unit_price,
                discount_pct=discount_pct,
                price_after_discount=self.safe_decimal(item.get('price_after_discount', 0)),
                vat_pct=vat_pct,
                line_total=line_total
            )
            
            return line_item
            
        except Exception as e:
            self.log(f"Error converting item to LineItem: {str(e)}", "ERROR")
            return None
    
    def extract_invoice_intro(self, json_data: Dict[str, Any]) -> Optional[InvoiceIntro]:
        """חילוץ מידע כללי על החשבונית"""
        try:
            # חיפוש במקומות שונים במבנה הנתונים
            intro_data = {}
            
            # חיפוש בשורש
            if 'supplier_name' in json_data:
                intro_data['supplier_name'] = json_data['supplier_name']
            if 'invoice_number' in json_data:
                intro_data['invoice_number'] = json_data['invoice_number']
            if 'invoice_date' in json_data:
                intro_data['invoice_date'] = json_data['invoice_date']
            
            # חיפוש במידע כללי
            if 'header' in json_data:
                header = json_data['header']
                intro_data.update({
                    'supplier_name': header.get('supplier_name', intro_data.get('supplier_name')),
                    'invoice_number': header.get('invoice_number', intro_data.get('invoice_number')),
                    'invoice_date': header.get('invoice_date', intro_data.get('invoice_date')),
                    'customer_name': header.get('customer_name')
                })
            
            if intro_data:
                return InvoiceIntro(**intro_data)
            
            return None
            
        except Exception as e:
            self.log(f"Error extracting intro: {str(e)}", "WARNING")
            return None
    
    def extract_invoice_final(self, json_data: Dict[str, Any], lines: List[LineItem]) -> Optional[InvoiceFinal]:
        """חילוץ/חישוב סיכום כספי"""
        try:
            # חישוב סכום השורות
            subtotal = sum([line.line_total for line in lines], Decimal("0"))
            
            # חיפוש VAT amount או חישוב
            vat_amount = Decimal("0")
            total = subtotal
            
            # חיפוש בנתוני הסיכום
            if 'summary' in json_data:
                summary = json_data['summary']
                subtotal = self.safe_decimal(summary.get('subtotal', subtotal))
                vat_amount = self.safe_decimal(summary.get('vat_amount', 0))
                total = self.safe_decimal(summary.get('total', subtotal + vat_amount))
            elif 'totals' in json_data:
                totals = json_data['totals']
                subtotal = self.safe_decimal(totals.get('subtotal', subtotal))
                vat_amount = self.safe_decimal(totals.get('vat_amount', 0))
                total = self.safe_decimal(totals.get('total', subtotal + vat_amount))
            else:
                # אם אין נתוני סיכום, נחשב VAT בהתבסס על השורות
                vat_amount = sum([
                    line.line_total * line.vat_pct / 100 
                    for line in lines
                ], Decimal("0"))
                total = subtotal + vat_amount
            
            return InvoiceFinal(
                subtotal=subtotal,
                vat_amount=vat_amount,
                total=total
            )
            
        except Exception as e:
            self.log(f"Error extracting final: {str(e)}", "ERROR")
            return None
    
    def safe_decimal(self, value: Any) -> Decimal:
        """המרה בטוחה לערך Decimal"""
        if value is None or value == "":
            return Decimal("0")
        
        try:
            # ניקוי הערך מתווים לא רלוונטיים
            if isinstance(value, str):
                value = value.strip().replace(",", "").replace("₪", "").replace("$", "")
            
            return Decimal(str(value))
        except:
            return Decimal("0")
    
    def validate_business_logic(self, json_files_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """הרצת וולידציה עסקית על כל הקבצים"""
        results = {}
        
        for file_key, items_list in json_files_data.items():
            self.log(f"Starting business validation for file: {file_key}", "INFO")
            
            # המרה לפורמט חשבונית
            file_json = {'main_items': items_list}
            invoice = self.convert_json_to_invoice(file_json)
            
            if invoice:
                try:
                    # הרצת וולידציה עסקית
                    validation_result = self.validator.validate(invoice.model_dump())
                    
                    results[file_key] = {
                        'success': True,
                        'score': validation_result['score'],
                        'status': validation_result['status'],
                        'issues': validation_result['issues'],
                        'lines_validated': len(invoice.lines),
                        'conversion_logs': self.conversion_logs.copy()
                    }
                    
                    self.log(f"Business validation completed for {file_key}: Score {validation_result['score']}, Status {validation_result['status']}", "INFO")
                    
                except Exception as e:
                    results[file_key] = {
                        'success': False,
                        'error': str(e),
                        'conversion_logs': self.conversion_logs.copy()
                    }
                    self.log(f"Business validation failed for {file_key}: {str(e)}", "ERROR")
            else:
                results[file_key] = {
                    'success': False,
                    'error': 'Failed to convert to invoice format',
                    'conversion_logs': self.conversion_logs.copy()
                }
                self.log(f"Failed to convert {file_key} to invoice format", "ERROR")
            
            # ניקוי לוגים לקובץ הבא
            self.conversion_logs.clear()
        
        return results
    
    def generate_business_validation_report(self, results: Dict[str, Any]) -> str:
        """יצירת דוח וולידציה עסקית"""
        report_lines = []
        report_lines.append("=== BUSINESS VALIDATION REPORT ===\n")
        
        # סיכום כללי
        total_files = len(results)
        successful_files = sum(1 for r in results.values() if r.get('success', False))
        
        report_lines.append(f"FILES PROCESSED: {total_files}")
        report_lines.append(f"SUCCESSFUL VALIDATIONS: {successful_files}")
        report_lines.append(f"FAILED VALIDATIONS: {total_files - successful_files}\n")
        
        # פירוט לכל קובץ
        for file_key, result in results.items():
            report_lines.append(f"--- {file_key} ---")
            
            if result.get('success', False):
                score = result.get('score', 0)
                status = result.get('status', 'UNKNOWN')
                issues = result.get('issues', [])
                
                report_lines.append(f"Score: {score}/100")
                report_lines.append(f"Status: {status}")
                report_lines.append(f"Lines Validated: {result.get('lines_validated', 0)}")
                
                if issues:
                    report_lines.append(f"Issues Found: {len(issues)}")
                    for issue in issues:
                        severity = issue.get('severity', 'UNKNOWN')
                        code = issue.get('code', 'UNKNOWN')
                        message = issue.get('message', 'No message')
                        report_lines.append(f"  [{severity}] {code}: {message}")
                else:
                    report_lines.append("No issues found")
            else:
                error = result.get('error', 'Unknown error')
                report_lines.append(f"FAILED: {error}")
            
            report_lines.append("")
        
        return "\n".join(report_lines)
    
    def get_logs(self) -> List[Dict[str, str]]:
        """קבלת כל הלוגים"""
        return self.conversion_logs.copy()
    
    def clear_logs(self):
        """ניקוי לוגים"""
        self.conversion_logs.clear()


def main():
    """בדיקה של המתאם"""
    adapter = BusinessValidationAdapter()
    
    # דוגמה לנתונים
    sample_data = {
        'main_items': [
            {
                'description': 'Product A',
                'quantity': 2,
                'unit_price': 100,
                'discount_percent': 10,
                'total_amount': 180
            }
        ]
    }
    
    # בדיקת המרה
    invoice = adapter.convert_json_to_invoice(sample_data)
    if invoice:
        print("Conversion successful!")
        print(f"Lines: {len(invoice.lines)}")
    else:
        print("Conversion failed")
    
    # הדפסת לוגים
    for log in adapter.get_logs():
        print(f"[{log['level']}] {log['message']}")


if __name__ == "__main__":
    main()