"""
enhanced_validation_gui.py - GUI בסיסי לוולידציה עם פיצ'ר ייצוא תבניות
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
from pathlib import Path
import json
import threading
from typing import Dict, List, Any, Optional
from datetime import datetime

from character_kpi_calculator import CharacterKPICalculator
from enhanced_validation_processor import EnhancedValidationProcessor, ValidationMethod


class SourceDataManager:
    """מנהל נתוני מקור בסיסי"""
    
    def __init__(self, data_dir: str = "validation_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.sources_file = self.data_dir / "source_templates.json"
        self.load_saved_sources()
    
    def load_saved_sources(self):
        """טעינת נתוני מקור שמורים"""
        try:
            if self.sources_file.exists():
                with open(self.sources_file, 'r', encoding='utf-8') as f:
                    self.saved_sources = json.load(f)
            else:
                self.saved_sources = {}
        except Exception:
            self.saved_sources = {}
    
    def save_source_template(self, name: str, template_data: Dict[str, Any]) -> bool:
        """שמירת תבנית נתוני מקור"""
        try:
            self.saved_sources[name] = template_data
            with open(self.sources_file, 'w', encoding='utf-8') as f:
                json.dump(self.saved_sources, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    
    def get_saved_sources(self) -> Dict[str, Any]:
        """קבלת כל נתוני המקור השמורים"""
        return self.saved_sources.copy()


class GroundTruthEditor:
    """עורך נתוני Ground Truth מתקדם עם ייצוא וייבוא"""
    
    def __init__(self, parent, template_data: Dict[str, Any], callback, source_manager: SourceDataManager):
        self.parent = parent
        self.template_data = template_data
        self.callback = callback
        self.source_manager = source_manager
        self.entries = {}
        self.create_editor_window()
    
    def create_editor_window(self):
        """יצירת חלון עריכת Ground Truth עם פיצ'רים מתקדמים"""
        self.window = tk.Toplevel(self.parent)
        self.window.title("Edit Ground Truth Data")
        self.window.geometry("1200x750")
        self.window.transient(self.parent)
        self.window.grab_set()
        
        # כותרת
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(title_frame, text="עריכת נתוני מקור", 
                 font=('Arial', 16, 'bold')).pack(side=tk.TOP, pady=5)
        
        ttk.Label(title_frame, 
                 text="מלא את הערכים הנכונים עבור כל שדה. שדות ריקים יתעלמו מהם.",
                 font=('Arial', 10)).pack(side=tk.TOP, pady=2)
        
        # פריים עליון - כפתורים
        top_frame = ttk.Frame(self.window)
        top_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # שורה ראשונה - תבניות שמורות
        templates_frame = ttk.Frame(top_frame)
        templates_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(templates_frame, text="תבניות שמורות:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.template_var = tk.StringVar()
        saved_sources = list(self.source_manager.get_saved_sources().keys())
        self.template_combo = ttk.Combobox(templates_frame, textvariable=self.template_var, 
                                          values=saved_sources, state="readonly", width=20)
        self.template_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.template_combo.bind('<<ComboboxSelected>>', self.load_template)
        
        ttk.Button(templates_frame, text="טען תבנית", 
                  command=self.load_selected_template).pack(side=tk.LEFT, padx=5)
        
        # שורה שנייה - פעולות קובץ ונתונים
        actions_frame = ttk.Frame(top_frame)
        actions_frame.pack(fill=tk.X)
        
        # צד שמאל - פעולות קובץ
        file_frame = ttk.LabelFrame(actions_frame, text="קבצים", padding="5")
        file_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(file_frame, text="ייבוא מקובץ", 
                  command=self.import_template_from_file, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(file_frame, text="ייצוא לקובץ", 
                  command=self.export_template_to_file, width=12).pack(side=tk.LEFT, padx=2)
        
        # צד ימין - פעולות נתונים
        data_frame = ttk.LabelFrame(actions_frame, text="נתונים", padding="5")
        data_frame.pack(side=tk.RIGHT)
        
        ttk.Button(data_frame, text="העתק הכל", 
                  command=self.copy_all_data, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(data_frame, text="הדבק הכל", 
                  command=self.paste_all_data, width=12).pack(side=tk.LEFT, padx=2)
        
        # Frame עיקרי עם גלילה
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Canvas לגלילה
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # יצירת שדות עריכה
        self.create_field_entries(scrollable_frame)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # הוספת תמיכה בגלילה עם עכבר
        self.bind_mouse_scroll(canvas)
        
        # כפתורי פעולה תחתונים
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        
        # שמירה כתבנית
        save_template_frame = ttk.Frame(buttons_frame)
        save_template_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(save_template_frame, text="שם תבנית:").pack(side=tk.LEFT, padx=(0, 5))
        self.template_name_var = tk.StringVar()
        template_name_entry = ttk.Entry(save_template_frame, textvariable=self.template_name_var, width=20)
        template_name_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(save_template_frame, text="שמור כתבנית", 
                  command=self.save_as_template).pack(side=tk.LEFT, padx=5)
        
        # כפתורי פעולה ראשיים
        action_frame = ttk.Frame(buttons_frame)
        action_frame.pack(side=tk.RIGHT)
        
        ttk.Button(action_frame, text="שמור נתוני מקור", 
                  command=self.save_ground_truth).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="ביטול", 
                  command=self.window.destroy).pack(side=tk.LEFT, padx=5)
    
    def export_template_to_file(self):
        """ייצוא התבנית הנוכחית לקובץ JSON"""
        try:
            # איסוף הנתונים הנוכחיים
            ground_truth_data = self.collect_current_data()
            
            if not ground_truth_data or all(len(item) <= 1 for item in ground_truth_data):
                messagebox.showwarning("אזהרה", "אין נתונים לייצוא")
                return
            
            # בחירת מיקום השמירה
            filename = filedialog.asksaveasfilename(
                title="שמור תבנית כ-JSON",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialfilename="ground_truth_template.json"
            )
            
            if not filename:
                return
            
            # הכנת נתונים מפורטים לייצוא
            export_data = {
                "template_info": {
                    "created_at": datetime.now().isoformat(),
                    "fields_count": len(self.template_data['fields']) - 1,  # מבלי 'line'
                    "lines_count": len(ground_truth_data),
                    "description": "Ground Truth Template exported from Advanced Validation Suite"
                },
                "ground_truth_data": ground_truth_data,
                "fields_structure": {
                    "available_fields": [f for f in self.template_data['fields'] if f != 'line'],
                    "line_numbers": [item.get('line', i+1) for i, item in enumerate(ground_truth_data)]
                }
            }
            
            # שמירה לקובץ
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            messagebox.showinfo("הצלחה", f"התבנית יוצאה בהצלחה לקובץ:\n{filename}")
            
        except Exception as e:
            messagebox.showerror("שגיאה", f"שגיאה בייצוא התבנית: {str(e)}")

    def import_template_from_file(self):
        """ייבוא תבנית מקובץ JSON"""
        try:
            # בחירת קובץ לייבוא
            filename = filedialog.askopenfilename(
                title="טען תבנית מקובץ JSON",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if not filename:
                return
            
            # טעינת הקובץ
            with open(filename, 'r', encoding='utf-8') as f:
                imported_data = json.load(f)
            
            # בדיקת פורמט הקובץ
            if isinstance(imported_data, dict) and 'ground_truth_data' in imported_data:
                # פורמט מלא (עם metadata)
                template_data = imported_data['ground_truth_data']
                info = imported_data.get('template_info', {})
                
                # הצגת מידע על התבנית
                created_at = info.get('created_at', 'לא ידוע')
                fields_count = info.get('fields_count', 'לא ידוע')
                lines_count = info.get('lines_count', len(template_data))
                
                message = f"מידע על התבנית:\nנוצרה: {created_at}\nשדות: {fields_count}\nשורות: {lines_count}\n\nהאם לטעון תבנית זו?"
                
                if not messagebox.askyesno("אשר ייבוא", message):
                    return
                    
            elif isinstance(imported_data, list):
                # פורמט פשוט (רשימת נתונים בלבד)
                template_data = imported_data
                
            elif isinstance(imported_data, dict) and any(key in imported_data for key in ['main_items', 'ground_truth', 'data']):
                # פורמט Ground Truth רגיל
                if 'ground_truth' in imported_data:
                    template_data = imported_data['ground_truth']
                elif 'main_items' in imported_data:
                    template_data = imported_data['main_items']
                elif 'data' in imported_data:
                    template_data = imported_data['data']
                else:
                    raise ValueError("פורמט קובץ לא מזוהה")
            else:
                raise ValueError("פורמט קובץ לא תקין")
            
            # טעינת הנתונים לממשק
            if isinstance(template_data, list) and template_data:
                self.load_data_to_entries(template_data)
                messagebox.showinfo("הצלחה", f"התבנית נטענה בהצלחה מהקובץ:\n{Path(filename).name}")
            else:
                messagebox.showwarning("אזהרה", "הקובץ לא כולל נתונים תקינים")
                
        except Exception as e:
            messagebox.showerror("שגיאה", f"שגיאה בייבוא התבנית: {str(e)}")
    
    def create_field_entries(self, parent):
        """יצירת שדות עריכה"""
        template = self.template_data['template']
        fields = self.template_data['fields']
        
        # כותרות עמודות
        headers_frame = ttk.Frame(parent)
        headers_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(headers_frame, text="שורה", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, padx=5, pady=5, sticky='w')
        
        for i, field in enumerate(fields):
            if field != 'line':
                ttk.Label(headers_frame, text=field, font=('Arial', 10, 'bold')).grid(
                    row=0, column=i+1, padx=5, pady=5, sticky='w')
        
        # יצירת שורות נתונים
        data_frame = ttk.Frame(parent)
        data_frame.pack(fill=tk.BOTH, expand=True)
        
        row = 0
        for line_key, line_data in template.items():
            line_num = line_key.split('_')[1]
            
            # תווית שורה
            ttk.Label(data_frame, text=f"שורה {line_num}", 
                     font=('Arial', 10, 'bold'), foreground='#666').grid(
                row=row, column=0, padx=5, pady=2, sticky='w')
            
            # שדות השורה
            col = 1
            for field in fields:
                if field == 'line':
                    continue
                
                entry_key = f"{line_key}_{field}"
                entry = ttk.Entry(data_frame, width=15)
                entry.grid(row=row, column=col, padx=2, pady=2, sticky='ew')
                
                # הוספת תמיכה בהעתק-הדבק מקלדת
                self.add_copy_paste_support(entry)
                
                self.entries[entry_key] = entry
                col += 1
            
            row += 1
        
        # הגדרת משקלי עמודות להתרחבות
        for i in range(len(fields)):
            data_frame.columnconfigure(i, weight=1)
    
    def bind_mouse_scroll(self, canvas):
        """הוספת תמיכה בגלילה עם עכבר"""
        def on_mouse_wheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def bind_to_mousewheel(event):
            canvas.bind_all("<MouseWheel>", on_mouse_wheel)
        
        def unbind_from_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
        
        canvas.bind('<Enter>', bind_to_mousewheel)
        canvas.bind('<Leave>', unbind_from_mousewheel)
    
    def add_copy_paste_support(self, entry_widget):
        """הוספת תמיכה בהעתק-הדבק למיקרו widget"""
        def copy_text(event=None):
            try:
                entry_widget.clipboard_clear()
                if entry_widget.selection_present():
                    text = entry_widget.selection_get()
                else:
                    text = entry_widget.get()
                entry_widget.clipboard_append(text)
                return "break"
            except:
                pass
        
        def paste_text(event=None):
            try:
                clipboard_text = entry_widget.clipboard_get()
                cleaned_text = self.clean_quotes(clipboard_text)
                if entry_widget.selection_present():
                    entry_widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
                entry_widget.insert(tk.INSERT, cleaned_text)
                return "break"
            except:
                pass
        
        # קישור קיצורי המקלדת
        entry_widget.bind('<Control-c>', copy_text)
        entry_widget.bind('<Control-v>', paste_text)
    
    def clean_quotes(self, text: str) -> str:
        """ניקוי מרכאות מתחילה וסוף הטקסט"""
        text = text.strip()
        if (text.startswith('"') and text.endswith('"')) or \
           (text.startswith("'") and text.endswith("'")):
            return text[1:-1]
        return text
    
    def copy_all_data(self):
        """העתק כל הנתונים ללוח"""
        try:
            all_data = []
            template = self.template_data['template']
            
            for line_key in sorted(template.keys()):
                line_data = {}
                line_num = int(line_key.split('_')[1])
                line_data['line'] = line_num
                
                for field in self.template_data['fields']:
                    if field == 'line':
                        continue
                    
                    entry_key = f"{line_key}_{field}"
                    if entry_key in self.entries:
                        value = self.entries[entry_key].get().strip()
                        if value:
                            line_data[field] = self.convert_to_number(value)
                
                all_data.append(line_data)
            
            json_text = json.dumps(all_data, ensure_ascii=False, indent=2)
            self.window.clipboard_clear()
            self.window.clipboard_append(json_text)
            messagebox.showinfo("הצלחה", "כל הנתונים הועתקו ללוח")
            
        except Exception as e:
            messagebox.showerror("שגיאה", f"שגיאה בהעתקה: {str(e)}")
    
    def paste_all_data(self):
        """הדבק נתונים מהלוח"""
        try:
            clipboard_text = self.window.clipboard_get()
            data = json.loads(clipboard_text)
            
            if isinstance(data, list):
                self.load_data_to_entries(data)
                messagebox.showinfo("הצלחה", "הנתונים הודבקו בהצלחה")
            else:
                messagebox.showerror("שגיאה", "פורמט נתונים לא תקין")
                
        except Exception as e:
            messagebox.showerror("שגיאה", f"שגיאה בהדבקה: {str(e)}")
    
    def load_data_to_entries(self, data: List[Dict[str, Any]]):
        """טעינת נתונים לשדות העריכה"""
        # ניקוי שדות קיימים
        for entry in self.entries.values():
            entry.delete(0, tk.END)
        
        # מילוי נתונים חדשים
        for item in data:
            line_num = item.get('line', 1)
            line_key = f"line_{line_num}"
            
            for field, value in item.items():
                if field == 'line':
                    continue
                
                entry_key = f"{line_key}_{field}"
                if entry_key in self.entries:
                    cleaned_value = self.clean_quotes(str(value))
                    self.entries[entry_key].insert(0, cleaned_value)
    
    def convert_to_number(self, value: str):
        """המרה למספר אם אפשר"""
        value = value.strip()
        if not value:
            return value
        
        try:
            if '.' in value or ',' in value:
                value = value.replace(',', '.')
                return float(value)
            else:
                return int(value)
        except ValueError:
            return value
    
    def save_as_template(self):
        """שמירה כתבנית"""
        template_name = self.template_name_var.get().strip()
        if not template_name:
            messagebox.showwarning("שגיאה", "יש להזין שם לתבנית")
            return
        
        ground_truth_data = self.collect_current_data()
        success = self.source_manager.save_source_template(template_name, ground_truth_data)
        
        if success:
            saved_sources = list(self.source_manager.get_saved_sources().keys())
            self.template_combo['values'] = saved_sources
            messagebox.showinfo("הצלחה", f"התבנית '{template_name}' נשמרה בהצלחה")
        else:
            messagebox.showerror("שגיאה", "שגיאה בשמירת התבנית")
    
    def load_selected_template(self):
        """טעינת תבנית נבחרת"""
        template_name = self.template_var.get()
        if not template_name:
            messagebox.showwarning("שגיאה", "יש לבחור תבנית")
            return
        
        saved_sources = self.source_manager.get_saved_sources()
        if template_name in saved_sources:
            template_data = saved_sources[template_name]
            self.load_data_to_entries(template_data)
            messagebox.showinfo("הצלחה", f"התבנית '{template_name}' נטענה בהצלחה")
    
    def load_template(self, event=None):
        """טעינת תבנית עם אירוע combo"""
        self.load_selected_template()
    
    def collect_current_data(self) -> List[Dict[str, Any]]:
        """איסוף הנתונים הנוכחיים"""
        ground_truth_data = []
        template = self.template_data['template']
        
        for line_key in sorted(template.keys()):
            line_num = int(line_key.split('_')[1])
            line_data = {'line': line_num}
            
            for field in self.template_data['fields']:
                if field == 'line':
                    continue
                
                entry_key = f"{line_key}_{field}"
                if entry_key in self.entries:
                    value = self.entries[entry_key].get().strip()
                    if value:
                        converted_value = self.convert_to_number(value)
                        line_data[field] = converted_value
            
            ground_truth_data.append(line_data)
        
        return ground_truth_data
    
    def save_ground_truth(self):
        """שמירת נתוני Ground Truth"""
        ground_truth_data = self.collect_current_data()
        self.callback(ground_truth_data)
        self.window.destroy()


class EnhancedValidationGUI:
    """GUI בסיסי לוולידציה"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.processor = EnhancedValidationProcessor()
        self.source_manager = SourceDataManager()
        self.setup_window()
        self.create_widgets()
        
    def setup_window(self):
        """הגדרת החלון הראשי"""
        self.root.title("Advanced Validation Suite - Enhanced")
        self.root.geometry("1200x800")
        self.root.resizable(True, True)
        
    def create_widgets(self):
        """יצירת רכיבי הממשק"""
        # פריים ראשי
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # כותרת
        title_label = ttk.Label(
            main_frame,
            text="Advanced Validation Suite - Character-Level & Business Logic",
            font=('Arial', 16, 'bold')
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # פנל שמאל - בקרה
        self.create_control_panel(main_frame)
        
        # פנל ימין - תוצאות
        self.create_results_panel(main_frame)
        
        # שורת סטטוס
        self.status_var = tk.StringVar(value="מוכן לטעינת קבצי JSON...")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
    
    def create_control_panel(self, parent):
        """יצירת פנל בקרה"""
        control_frame = ttk.Frame(parent, width=400)
        control_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        control_frame.grid_propagate(False)
        
        # שיטת וולידציה
        method_frame = ttk.LabelFrame(control_frame, text="שיטת וולידציה", padding="10")
        method_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.validation_method_var = tk.StringVar(value=ValidationMethod.CHARACTER_LEVEL.value)
        
        ttk.Radiobutton(method_frame, text="השוואה ברמת תווים", 
                       variable=self.validation_method_var, 
                       value=ValidationMethod.CHARACTER_LEVEL.value,
                       command=self.on_method_changed).pack(anchor=tk.W)
        
        ttk.Radiobutton(method_frame, text="וולידציה עסקית", 
                       variable=self.validation_method_var,
                       value=ValidationMethod.BUSINESS_LOGIC.value,
                       command=self.on_method_changed).pack(anchor=tk.W)
        
        ttk.Radiobutton(method_frame, text="שתי השיטות", 
                       variable=self.validation_method_var,
                       value=ValidationMethod.BOTH.value,
                       command=self.on_method_changed).pack(anchor=tk.W)
        
        # קבצי JSON
        files_frame = ttk.LabelFrame(control_frame, text="קבצי JSON", padding="10")
        files_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(files_frame, text="טען קבצי JSON", 
                  command=self.load_json_files, width=30).pack(pady=2)
        
        self.files_listbox = tk.Listbox(files_frame, height=4)
        self.files_listbox.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        # Ground Truth
        self.gt_frame = ttk.LabelFrame(control_frame, text="נתוני מקור (Ground Truth)", padding="10")
        self.gt_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(self.gt_frame, text="טען מקובץ", 
                  command=self.load_ground_truth_file, width=30).pack(pady=2)
        
        ttk.Button(self.gt_frame, text="עריכה ידנית", 
           command=self.edit_ground_truth, width=30).pack(pady=2)
        
        self.gt_status_var = tk.StringVar(value="לא נטענו נתוני מקור")
        ttk.Label(self.gt_frame, textvariable=self.gt_status_var, 
                 foreground='gray').pack(pady=2)
        
        # פעולות
        actions_frame = ttk.LabelFrame(control_frame, text="פעולות", padding="10")
        actions_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.run_button = ttk.Button(actions_frame, text="הרץ וולידציה", 
                                    command=self.run_validation, width=30)
        self.run_button.pack(pady=2)
        self.run_button.config(state='disabled')
        
        ttk.Button(actions_frame, text="נקה הכל", 
                  command=self.clear_all, width=30).pack(pady=2)
        
        # עדכון ראשוני
        self.on_method_changed()
    
    def create_results_panel(self, parent):
        """יצירת פנל התוצאות המשופר עם טאבים מתקדמים"""
        results_frame = ttk.LabelFrame(parent, text="תוצאות וולידציה", padding="10")
        results_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Notebook לתוצאות
        self.notebook = ttk.Notebook(results_frame)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # טאב 1: סיכום
        self.create_summary_tab()
        
        # טאב 2: טבלה מורחבת (לוולידציה ברמת תווים)
        self.create_expanded_table_tab()
        
        # טאב 3: וולידציה עסקית
        self.create_business_validation_tab()
        
        # טאב 4: השוואה משולבת
        self.create_combined_analysis_tab()
        
        # טאב 5: דוח מלא
        self.create_report_tab()
    
    def create_summary_tab(self):
        """יצירת טאב סיכום"""
        summary_frame = ttk.Frame(self.notebook)
        self.notebook.add(summary_frame, text="סיכום")
        
        # יצירת TreeView לסיכום
        columns = ('accuracy', 'type')
        self.summary_tree = ttk.Treeview(summary_frame, columns=columns, show='tree headings', height=10)
        
        # הגדרת כותרות עמודות
        self.summary_tree.heading('#0', text='קובץ')
        self.summary_tree.heading('accuracy', text='דיוק')
        self.summary_tree.heading('type', text='סוג')
        
        # הגדרת רוחב עמודות
        self.summary_tree.column('#0', width=200)
        self.summary_tree.column('accuracy', width=100)
        self.summary_tree.column('type', width=100)
        
        # הוספת scrollbar
        summary_scrollbar = ttk.Scrollbar(summary_frame, orient="vertical", command=self.summary_tree.yview)
        self.summary_tree.configure(yscrollcommand=summary_scrollbar.set)
        
        # מיקום הרכיבים
        self.summary_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        summary_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_expanded_table_tab(self):
        """יצירת טאב טבלה מורחבת"""
        expanded_frame = ttk.Frame(self.notebook)
        self.notebook.add(expanded_frame, text="טבלה מורחבת")
        
        # יצירת טקסט עם scrollbar
        self.expanded_text = scrolledtext.ScrolledText(expanded_frame, wrap=tk.WORD, height=20)
        self.expanded_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_business_validation_tab(self):
        """יצירת טאב ווליידציה עסקית"""
        business_frame = ttk.Frame(self.notebook)
        self.notebook.add(business_frame, text="ווליידציה עסקית")
        
        # יצירת טקסט עם scrollbar
        self.business_text = scrolledtext.ScrolledText(business_frame, wrap=tk.WORD, height=20)
        self.business_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_combined_analysis_tab(self):
        """יצירת טאב השוואה משולבת"""
        combined_frame = ttk.Frame(self.notebook)
        self.notebook.add(combined_frame, text="השוואה משולבת")
        
        # יצירת טקסט עם scrollbar
        self.combined_text = scrolledtext.ScrolledText(combined_frame, wrap=tk.WORD, height=20)
        self.combined_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_report_tab(self):
        """יצירת טאב דוח מלא"""
        report_frame = ttk.Frame(self.notebook)
        self.notebook.add(report_frame, text="דוח מלא")
        
        # יצירת טקסט עם scrollbar
        self.report_text = scrolledtext.ScrolledText(report_frame, wrap=tk.WORD, height=20)
        self.report_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def on_method_changed(self):
        """טיפול בשינוי שיטת ווליידציה"""
        method = ValidationMethod(self.validation_method_var.get())
        self.processor.set_validation_method(method)
        
        # הצבה/הסתרה של Ground Truth לפי השיטה
        if method == ValidationMethod.BUSINESS_LOGIC:
            self.gt_frame.pack_forget()
        else:
            # תיקון הבעיה: הסרת הפרמטר before הבעייתי
            self.gt_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.update_run_button()
    
    def edit_ground_truth(self):
        """עריכת Ground Truth - פונקציה מעודכנת"""
        if not self.processor.loaded_files:
            messagebox.showwarning("אזהרה", "טען קבצי JSON תחילה")
            return
        
        template_data = self.processor.extract_all_fields_template()
        editor = GroundTruthEditor(self.root, template_data, self.on_ground_truth_saved, self.source_manager)

    def on_ground_truth_saved(self, ground_truth_data):
        """טיפול בשמירת Ground Truth"""
        success = self.processor.load_ground_truth(ground_truth_data=ground_truth_data)
        if success:
            gt_count = len(ground_truth_data)
            self.gt_status_var.set(f"נתוני מקור נשמרו: {gt_count} שורות")
            self.update_run_button()
            self.status_var.set("נתוני המקור נשמרו")
        else:
            messagebox.showerror("שגיאה", "שגיאה בשמירת נתוני המקור")
    
    def load_json_files(self):
        """טעינת קבצי JSON"""
        filetypes = [("JSON files", "*.json"), ("All files", "*.*")]
        filenames = filedialog.askopenfilenames(title="בחר קבצי JSON", filetypes=filetypes)
        
        if not filenames:
            return
        
        load_results = self.processor.load_json_files(list(filenames))
        
        # עדכון רשימת הקבצים
        self.files_listbox.delete(0, tk.END)
        for file_key, success in load_results.items():
            status = "✓" if success else "✗"
            self.files_listbox.insert(tk.END, f"{status} {file_key}")
        
        self.update_run_button()
        self.status_var.set(f"נטענו {sum(load_results.values())} מתוך {len(load_results)} קבצים")
    
    def load_ground_truth_file(self):
        """טעינת קובץ Ground Truth"""
        filename = filedialog.askopenfilename(
            title="בחר קובץ נתוני מקור",
            filetypes=[("JSON files", "*.json")]
        )
        
        if filename:
            success = self.processor.load_ground_truth(filename)
            if success:
                gt_count = len(self.processor.ground_truth_data)
                self.gt_status_var.set(f"נתוני מקור נטענו: {gt_count} שורות")
                self.update_run_button()
                self.status_var.set("נתוני מקור נטענו בהצלחה")
            else:
                self.gt_status_var.set("שגיאה בטעינת נתוני מקור")
                messagebox.showerror("שגיאה", "שגיאה בטעינת קובץ נתוני המקור")
    
    def run_validation(self):
        """הרצת תהליך וולידציה"""
        if not self.processor.can_run_validation():
            messagebox.showwarning("אזהרה", "לא ניתן להריץ וולידציה - חסרים נתונים")
            return
        
        self.run_button.config(state='disabled', text="מריץ...")
        self.status_var.set("מריץ וולידציה...")
        
        def run_in_background():
            try:
                results = self.processor.run_validation()
                self.root.after(0, lambda: self.on_validation_complete(results))
            except Exception as e:
                self.root.after(0, lambda: self.on_validation_error(str(e)))
        
        thread = threading.Thread(target=run_in_background)
        thread.daemon = True
        thread.start()
    
    def on_validation_complete(self, results):
        """טיפול בהשלמת וולידציה"""
        self.run_button.config(state='normal', text="הרץ וולידציה")
        self.status_var.set("וולידציה הושלמה בהצלחה")
        
        # עדכון תוצאות
        self.update_results_display(results)
        
        messagebox.showinfo("הצלחה", "וולידציה הושלמה בהצלחה!")
    
    def on_validation_error(self, error_msg):
        """טיפול בשגיאות וולידציה"""
        self.run_button.config(state='normal', text="הרץ וולידציה")
        self.status_var.set("וולידציה נכשלה")
        messagebox.showerror("שגיאה", f"וולידציה נכשלה: {error_msg}")
    
    def update_results_display(self, results):
        """עדכון תצוגת התוצאות"""
        # ניקוי הטבלה
        for item in self.summary_tree.get_children():
            self.summary_tree.delete(item)
        
        method = self.processor.get_validation_method()
        
        if method == ValidationMethod.CHARACTER_LEVEL:
            self.update_character_results(results)
        elif method == ValidationMethod.BUSINESS_LOGIC:
            self.update_business_results(results)
        elif method == ValidationMethod.BOTH:
            self.update_combined_results(results)
        
        # עדכון דוח
        report = results.get('detailed_report', 'אין דוח זמין')
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(1.0, report)
    
    def update_character_results(self, results):
        """עדכון תוצאות השוואת תווים"""
        kpi_results = results.get('kpi_results', {})
        for file_key, file_results in kpi_results.items():
            accuracy = f"{file_results['overall_accuracy']:.1%}"
            self.summary_tree.insert('', 'end', text=file_key, values=(accuracy, "תווים"))
    
    def update_business_results(self, results):
        """עדכון תוצאות וולידציה עסקית"""
        business_results = results.get('business_results', {})
        for file_key, file_results in business_results.items():
            if file_results.get('success', False):
                score = f"{file_results['score']}/100"
                status = file_results['status']
            else:
                score = "כשל"
                status = "שגיאה"
            self.summary_tree.insert('', 'end', text=file_key, values=(score, status))
    
    def update_combined_results(self, results):
        """עדכון תוצאות משולבות"""
        combined = results.get('combined_analysis', {})
        files_analysis = combined.get('files_analysis', {})
        
        for file_key, analysis in files_analysis.items():
            combined_score = analysis.get('combined_score', 'N/A')
            self.summary_tree.insert('', 'end', text=file_key, values=(combined_score, "משולב"))
    
    def update_run_button(self):
        """עדכון מצב כפתור הרצה"""
        can_run = self.processor.can_run_validation()
        self.run_button.config(state='normal' if can_run else 'disabled')
    
    def clear_all(self):
        """ניקוי כל הנתונים"""
        self.processor.clear_data()
        self.files_listbox.delete(0, tk.END)
        self.gt_status_var.set("לא נטענו נתוני מקור")
        
        for item in self.summary_tree.get_children():
            self.summary_tree.delete(item)
        
        self.report_text.delete(1.0, tk.END)
        self.update_run_button()
        self.status_var.set("כל הנתונים נוקו")
    
    def run(self):
        """הפעלת הממשק"""
        self.root.mainloop()


def main():
    """פונקציה ראשית"""
    app = EnhancedValidationGUI()
    app.run()


if __name__ == "__main__":
    main()