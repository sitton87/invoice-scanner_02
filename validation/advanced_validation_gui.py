"""
advanced_validation_gui.py - GUI מתקדם לוולידציה ברמת תווים
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
from pathlib import Path
import json
import threading
from typing import Dict, List, Any

from .validation_processor import ValidationProcessor


class GroundTruthEditor:
    """עורך נתוני Ground Truth"""
    
    def __init__(self, parent, template_data: Dict[str, Any], callback):
        self.parent = parent
        self.template_data = template_data
        self.callback = callback
        self.entries = {}
        self.create_editor_window()
    
    def create_editor_window(self):
        """יצירת חלון עריכת Ground Truth"""
        self.window = tk.Toplevel(self.parent)
        self.window.title("Edit Ground Truth Data")
        self.window.geometry("1200x800")
        self.window.transient(self.parent)
        self.window.grab_set()
        
        # כותרת
        ttk.Label(self.window, text="Enter Ground Truth Data", 
                 font=('Arial', 14, 'bold')).pack(pady=10)
        
        # הסבר
        ttk.Label(self.window, 
                 text="Fill in the correct values for each field. Empty fields will be ignored.",
                 font=('Arial', 10)).pack(pady=5)
        
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
        template = self.template_data['template']
        fields = self.template_data['fields']
        
        row = 0
        for line_key, line_data in template.items():
            # כותרת שורה
            line_label = ttk.Label(scrollable_frame, text=f"Line {line_key.split('_')[1]}", 
                                  font=('Arial', 12, 'bold'))
            line_label.grid(row=row, column=0, columnspan=4, sticky='w', pady=(10, 5))
            row += 1
            
            # שדות השורה
            for i, field in enumerate(fields):
                if field == 'line':
                    continue
                    
                col = i % 4
                if col == 0:
                    row += 1
                
                # Label
                ttk.Label(scrollable_frame, text=f"{field}:").grid(
                    row=row, column=col*2, sticky='w', padx=5, pady=2)
                
                # Entry
                entry_key = f"{line_key}_{field}"
                entry = ttk.Entry(scrollable_frame, width=15)
                entry.grid(row=row, column=col*2+1, padx=5, pady=2)
                
                # הוספת תמיכה בהעתק-הדבק
                self.add_copy_paste_support(entry)
                
                self.entries[entry_key] = entry
            
            row += 1
        
        # Pack canvas
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # כפתורי פעולה
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        
        ttk.Button(buttons_frame, text="Save Ground Truth", 
                  command=self.save_ground_truth).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Cancel", 
                  command=self.window.destroy).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Load from File", 
                  command=self.load_from_file).pack(side=tk.RIGHT, padx=5)
    
    def add_copy_paste_support(self, entry_widget):
        """הוספת תמיכה בהעתק-הדבק לEntry widget"""
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
                if entry_widget.selection_present():
                    entry_widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
                entry_widget.insert(tk.INSERT, clipboard_text)
                return "break"
            except:
                pass
        
        def cut_text(event=None):
            try:
                if entry_widget.selection_present():
                    text = entry_widget.selection_get()
                    entry_widget.clipboard_clear()
                    entry_widget.clipboard_append(text)
                    entry_widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
                return "break"
            except:
                pass
        
        def select_all(event=None):
            try:
                entry_widget.select_range(0, tk.END)
                return "break"
            except:
                pass
        
        # קישור קיצורי המקלדת
        entry_widget.bind('<Control-c>', copy_text)
        entry_widget.bind('<Control-v>', paste_text)  
        entry_widget.bind('<Control-x>', cut_text)
        entry_widget.bind('<Control-a>', select_all)
        
        # גם תמיכה במקלדת ימנית
        entry_widget.bind('<Button-3>', self.create_context_menu(entry_widget))
    
    def create_context_menu(self, entry_widget):
        """יצירת תפריט לחיצה ימנית"""
        def show_context_menu(event):
            context_menu = tk.Menu(self.window, tearoff=0)
            
            context_menu.add_command(label="Cut", command=lambda: self.cut_text_widget(entry_widget))
            context_menu.add_command(label="Copy", command=lambda: self.copy_text_widget(entry_widget))  
            context_menu.add_command(label="Paste", command=lambda: self.paste_text_widget(entry_widget))
            context_menu.add_separator()
            context_menu.add_command(label="Select All", command=lambda: entry_widget.select_range(0, tk.END))
            
            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                context_menu.grab_release()
        
        return show_context_menu
    
    def copy_text_widget(self, widget):
        """העתק טקסט מ-widget"""
        try:
            widget.clipboard_clear()
            if widget.selection_present():
                text = widget.selection_get()
            else:
                text = widget.get()
            widget.clipboard_append(text)
        except:
            pass
    
    def paste_text_widget(self, widget):
        """הדבק טקסט ל-widget"""
        try:
            clipboard_text = widget.clipboard_get()
            if widget.selection_present():
                widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
            widget.insert(tk.INSERT, clipboard_text)
        except:
            pass
    
    def cut_text_widget(self, widget):
        """חתוך טקסט מ-widget"""
        try:
            if widget.selection_present():
                text = widget.selection_get()
                widget.clipboard_clear()
                widget.clipboard_append(text)
                widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except:
            pass
    
    def save_ground_truth(self):
        """שמירת נתוני Ground Truth"""
        ground_truth_data = []
        template = self.template_data['template']
        
        for line_key in template.keys():
            line_num = int(line_key.split('_')[1])
            line_data = {'line': line_num}
            
            for field in self.template_data['fields']:
                if field == 'line':
                    continue
                
                entry_key = f"{line_key}_{field}"
                if entry_key in self.entries:
                    value = self.entries[entry_key].get().strip()
                    if value:
                        # נסה להמיר למספר אם אפשר
                        try:
                            if '.' in value:
                                line_data[field] = float(value)
                            else:
                                line_data[field] = int(value)
                        except ValueError:
                            line_data[field] = value
            
            ground_truth_data.append(line_data)
        
        self.callback(ground_truth_data)
        self.window.destroy()
    
    def load_from_file(self):
        """טעינת Ground Truth מקובץ"""
        filename = filedialog.askopenfilename(
            title="Select Ground Truth File",
            filetypes=[("JSON files", "*.json")]
        )
        
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # חילוץ נתונים מהקובץ
                if isinstance(data, list):
                    gt_data = data
                elif 'ground_truth' in data:
                    gt_data = data['ground_truth']
                elif 'main_items' in data:
                    gt_data = data['main_items']
                else:
                    messagebox.showerror("Error", "Could not find ground truth data in file")
                    return
                
                # מילוי השדות
                for item in gt_data:
                    line_num = item.get('line', 1)
                    line_key = f"line_{line_num}"
                    
                    for field, value in item.items():
                        if field == 'line':
                            continue
                        
                        entry_key = f"{line_key}_{field}"
                        if entry_key in self.entries:
                            self.entries[entry_key].delete(0, tk.END)
                            self.entries[entry_key].insert(0, str(value))
                
                messagebox.showinfo("Success", "Ground truth data loaded from file")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file: {str(e)}")


class AdvancedValidationGUI:
    """GUI מתקדם לוולידציה"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.processor = ValidationProcessor()
        self.setup_window()
        self.create_widgets()
        
    def setup_window(self):
        """הגדרת החלון הראשי"""
        self.root.title("Advanced Validation Suite - Character-Level KPI")
        self.root.geometry("1400x900")
        self.root.resizable(True, True)
        
        # מרכז החלון
        self.center_window()
        
    def center_window(self):
        """מרכז את החלון במסך"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
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
            text="Advanced Validation Suite - Character-Level Analysis",
            font=('Arial', 16, 'bold')
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # פנל שמאל - בקרה
        self.create_control_panel(main_frame)
        
        # פנל ימין - תוצאות
        self.create_results_panel(main_frame)
        
        # שורת סטטוס
        self.status_var = tk.StringVar(value="Ready to load JSON files...")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
    
    def create_control_panel(self, parent):
        """יצירת פנל הבקרה"""
        control_frame = ttk.Frame(parent, width=400)
        control_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        control_frame.grid_propagate(False)
        
        # קטגוריה 1: טעינת קבצי JSON
        files_frame = ttk.LabelFrame(control_frame, text="JSON Files (1-5)", padding="10")
        files_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(files_frame, text="Load JSON Files", 
                  command=self.load_json_files, width=30).pack(pady=2)
        ttk.Button(files_frame, text="Clear JSON Files", 
                  command=self.clear_json_files, width=30).pack(pady=2)
        
        # רשימת קבצים
        self.files_listbox = tk.Listbox(files_frame, height=4)
        self.files_listbox.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        # קטגוריה 2: Ground Truth
        gt_frame = ttk.LabelFrame(control_frame, text="Ground Truth", padding="10")
        gt_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(gt_frame, text="Load Ground Truth File", 
                  command=self.load_ground_truth_file, width=30).pack(pady=2)
        ttk.Button(gt_frame, text="Edit Ground Truth", 
                  command=self.edit_ground_truth, width=30).pack(pady=2)
        
        self.gt_status_var = tk.StringVar(value="No ground truth loaded")
        ttk.Label(gt_frame, textvariable=self.gt_status_var, 
                 foreground='gray').pack(pady=2)
        
        # קטגוריה 3: פעולות
        actions_frame = ttk.LabelFrame(control_frame, text="Actions", padding="10")
        actions_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.run_button = ttk.Button(actions_frame, text="RUN VALIDATION", 
                                    command=self.run_validation, width=30, 
                                    style="Accent.TButton")
        self.run_button.pack(pady=2)
        self.run_button.config(state='disabled')
        
        ttk.Button(actions_frame, text="Export Results", 
                  command=self.export_results, width=30).pack(pady=2)
        ttk.Button(actions_frame, text="Clear All", 
                  command=self.clear_all, width=30).pack(pady=2)
        
        # קטגוריה 4: מידע מהיר
        info_frame = ttk.LabelFrame(control_frame, text="Status", padding="10")
        info_frame.pack(fill=tk.BOTH, expand=True)
        
        self.info_text = tk.Text(info_frame, height=8, wrap=tk.WORD, font=('Consolas', 9))
        self.info_text.pack(fill=tk.BOTH, expand=True)
    
    def create_results_panel(self, parent):
        """יצירת פנל התוצאות"""
        results_frame = ttk.LabelFrame(parent, text="Validation Results", padding="10")
        results_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Notebook לתוצאות
        self.notebook = ttk.Notebook(results_frame)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # טאב 1: סיכום KPI
        self.create_summary_tab()
        
        # טאב 2: פירוט שדות
        self.create_details_tab()
        
        # טאב 3: דוח מלא
        self.create_report_tab()
        
        # טאב 4: לוגים
        self.create_logs_tab()
    
    def create_summary_tab(self):
        """יצירת טאב סיכום KPI"""
        summary_frame = ttk.Frame(self.notebook)
        self.notebook.add(summary_frame, text="KPI Summary")
        
        summary_frame.columnconfigure(0, weight=1)
        summary_frame.rowconfigure(0, weight=1)
        
        # טבלת תוצאות
        tree_frame = ttk.Frame(summary_frame)
        tree_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        self.summary_tree = ttk.Treeview(tree_frame, columns=('accuracy', 'chars', 'rank'), show='headings')
        self.summary_tree.heading('#0', text='File')
        self.summary_tree.heading('accuracy', text='Accuracy')
        self.summary_tree.heading('chars', text='Characters')
        self.summary_tree.heading('rank', text='Rank')
        
        self.summary_tree.column('accuracy', width=100)
        self.summary_tree.column('chars', width=150)
        self.summary_tree.column('rank', width=80)
        
        self.summary_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # סקרולבר
        summary_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.summary_tree.yview)
        summary_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.summary_tree.configure(yscrollcommand=summary_scroll.set)
    
    def create_details_tab(self):
        """יצירת טאב פירוט שדות"""
        details_frame = ttk.Frame(self.notebook)
        self.notebook.add(details_frame, text="Field Details")
        
        details_frame.columnconfigure(0, weight=1)
        details_frame.rowconfigure(1, weight=1)
        
        # בחירת קובץ
        select_frame = ttk.Frame(details_frame)
        select_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        ttk.Label(select_frame, text="Select file:").pack(side=tk.LEFT, padx=(0, 5))
        self.file_combo = ttk.Combobox(select_frame, state="readonly")
        self.file_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.file_combo.bind('<<ComboboxSelected>>', self.on_file_select)
        
        # טבלת פירוט
        details_tree_frame = ttk.Frame(details_frame)
        details_tree_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=5)
        details_tree_frame.columnconfigure(0, weight=1)
        details_tree_frame.rowconfigure(0, weight=1)
        
        self.details_tree = ttk.Treeview(details_tree_frame, 
                                        columns=('accuracy', 'correct', 'total', 'errors'), 
                                        show='headings')
        self.details_tree.heading('#0', text='Field')
        self.details_tree.heading('accuracy', text='Accuracy')
        self.details_tree.heading('correct', text='Correct')
        self.details_tree.heading('total', text='Total')
        self.details_tree.heading('errors', text='Errors')
        
        self.details_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        details_scroll = ttk.Scrollbar(details_tree_frame, orient="vertical", command=self.details_tree.yview)
        details_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.details_tree.configure(yscrollcommand=details_scroll.set)
    
    def create_report_tab(self):
        """יצירת טאב דוח מלא"""
        report_frame = ttk.Frame(self.notebook)
        self.notebook.add(report_frame, text="Full Report")
        
        report_frame.columnconfigure(0, weight=1)
        report_frame.rowconfigure(0, weight=1)
        
        self.report_text = scrolledtext.ScrolledText(
            report_frame,
            wrap=tk.WORD,
            font=('Consolas', 10)
        )
        self.report_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
    
    def create_logs_tab(self):
        """יצירת טאב לוגים"""
        logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(logs_frame, text="Logs")
        
        logs_frame.columnconfigure(0, weight=1)
        logs_frame.rowconfigure(1, weight=1)
        
        # כפתורי בקרה
        logs_controls = ttk.Frame(logs_frame)
        logs_controls.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        ttk.Button(logs_controls, text="Clear Logs", command=self.clear_logs).pack(side=tk.LEFT)
        ttk.Button(logs_controls, text="Copy Logs", command=self.copy_logs).pack(side=tk.LEFT, padx=(10, 0))
        
        # טקסט לוגים
        self.logs_text = scrolledtext.ScrolledText(
            logs_frame,
            wrap=tk.WORD,
            font=('Consolas', 9),
            bg='#2d3748',
            fg='#e2e8f0'
        )
        self.logs_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=5)
    
    def load_json_files(self):
        """טעינת קבצי JSON"""
        filetypes = [("JSON files", "*.json"), ("All files", "*.*")]
        filenames = filedialog.askopenfilenames(title="Select JSON files (1-5)", filetypes=filetypes)
        
        if not filenames:
            return
        
        if len(filenames) > 5:
            messagebox.showwarning("Warning", "Maximum 5 files allowed. Taking first 5.")
            filenames = filenames[:5]
        
        load_results = self.processor.load_json_files(list(filenames))
        
        # עדכון רשימת הקבצים
        self.files_listbox.delete(0, tk.END)
        for file_key, success in load_results.items():
            status = "✓" if success else "✗"
            self.files_listbox.insert(tk.END, f"{status} {file_key}")
        
        self.update_status_info()
        self.update_run_button()
        self.status_var.set(f"Loaded {sum(load_results.values())} of {len(load_results)} files")
    
    def clear_json_files(self):
        """ניקוי קבצי JSON"""
        self.processor.loaded_files.clear()
        self.files_listbox.delete(0, tk.END)
        self.update_status_info()
        self.update_run_button()
        self.status_var.set("JSON files cleared")
    
    def load_ground_truth_file(self):
        """טעינת קובץ Ground Truth"""
        filename = filedialog.askopenfilename(
            title="Select Ground Truth File",
            filetypes=[("JSON files", "*.json")]
        )
        
        if filename:
            success = self.processor.load_ground_truth(filename)
            if success:
                gt_count = len(self.processor.ground_truth_data)
                self.gt_status_var.set(f"Ground truth loaded: {gt_count} lines")
                self.update_run_button()
                self.status_var.set(f"Ground truth loaded successfully")
            else:
                self.gt_status_var.set("Failed to load ground truth")
                messagebox.showerror("Error", "Failed to load ground truth file")
    
    def edit_ground_truth(self):
        """עריכת Ground Truth"""
        if not self.processor.loaded_files:
            messagebox.showwarning("Warning", "Load JSON files first")
            return
        
        template_data = self.processor.extract_all_fields_template()
        editor = GroundTruthEditor(self.root, template_data, self.on_ground_truth_saved)
    
    def on_ground_truth_saved(self, ground_truth_data):
        """טיפול בשמירת Ground Truth"""
        success = self.processor.load_ground_truth(ground_truth_data=ground_truth_data)
        if success:
            gt_count = len(ground_truth_data)
            self.gt_status_var.set(f"Ground truth saved: {gt_count} lines")
            self.update_run_button()
            self.status_var.set("Ground truth data saved")
        else:
            messagebox.showerror("Error", "Failed to save ground truth data")
    
    def run_validation(self):
        """הרצת תהליך הוולידציה"""
        if not self.processor.loaded_files:
            messagebox.showwarning("Warning", "No JSON files loaded")
            return
        
        if not self.processor.ground_truth_data:
            messagebox.showwarning("Warning", "No ground truth data available")
            return
        
        # הרצה בthread נפרד
        self.run_button.config(state='disabled', text="Running...")
        self.status_var.set("Running validation...")
        
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
        """טיפול בהשלמת הוולידציה"""
        self.run_button.config(state='normal', text="RUN VALIDATION")
        self.status_var.set("Validation completed successfully")
        
        # עדכון התוצאות
        self.update_summary_display(results)
        self.update_details_display(results)
        self.update_report_display(results)
        self.update_logs_display()
        
        messagebox.showinfo("Success", "Validation completed successfully!")
    
    def on_validation_error(self, error_msg):
        """טיפול בשגיאת וולידציה"""
        self.run_button.config(state='normal', text="RUN VALIDATION")
        self.status_var.set("Validation failed")
        messagebox.showerror("Error", f"Validation failed: {error_msg}")
        self.update_logs_display()
    
    def update_summary_display(self, results):
        """עדכון תצוגת הסיכום"""
        # ניקוי הטבלה
        for item in self.summary_tree.get_children():
            self.summary_tree.delete(item)
        
        # הוספת נתונים
        comparison_summary = self.processor.get_comparison_summary()
        for file_key, summary in comparison_summary.items():
            kpi_data = results['kpi_results'][file_key]
            chars_info = f"{kpi_data['correct_characters']:,}/{kpi_data['total_characters']:,}"
            
            self.summary_tree.insert('', 'end', text=file_key, values=(
                summary['accuracy_percent'],
                chars_info,
                f"#{summary['rank']}"
            ))
        
        # עדכון combo box
        self.file_combo['values'] = list(comparison_summary.keys())
        if self.file_combo['values']:
            self.file_combo.set(self.file_combo['values'][0])
            self.on_file_select()
    
    def update_details_display(self, results):
        """עדכון תצוגת הפירוט"""
        # יעודכן ב-on_file_select
        pass
    
    def on_file_select(self, event=None):
        """טיפול בבחירת קובץ לפירוט"""
        selected_file = self.file_combo.get()
        if not selected_file or not self.processor.validation_results:
            return
        
        # ניקוי הטבלה
        for item in self.details_tree.get_children():
            self.details_tree.delete(item)
        
        # קבלת פירוט השדות
        field_details = self.processor.get_field_comparison_details(selected_file)
        
        for field_name, field_data in field_details.items():
            self.details_tree.insert('', 'end', text=field_name, values=(
                field_data['accuracy_percent'],
                f"{field_data['correct_chars']:,}",
                f"{field_data['total_chars']:,}",
                f"{field_data['error_chars']:,}"
            ))
    
    def update_report_display(self, results):
        """עדכון תצוגת הדוח"""
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(1.0, results['detailed_report'])
    
    def update_logs_display(self):
        """עדכון תצוגת הלוגים"""
        self.logs_text.delete(1.0, tk.END)
        logs = self.processor.kpi_calculator.get_logs()
        
        for log_entry in logs:
            timestamp = log_entry['timestamp']
            level = log_entry['level']
            message = log_entry['message']
            
            log_line = f"[{timestamp}] {level}: {message}\n"
            self.logs_text.insert(tk.END, log_line)
    
    def export_results(self):
        """יצוא תוצאות"""
        if not self.processor.validation_results:
            messagebox.showwarning("Warning", "No results to export")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            success = self.processor.export_results(filename)
            if success:
                messagebox.showinfo("Success", f"Results exported to {filename}")
            else:
                messagebox.showerror("Error", "Failed to export results")
    
    def clear_logs(self):
        """ניקוי לוגים"""
        self.processor.kpi_calculator.clear_logs()
        self.logs_text.delete(1.0, tk.END)
    
    def copy_logs(self):
        """העתקת לוגים"""
        logs_content = self.logs_text.get(1.0, tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(logs_content)
        messagebox.showinfo("Success", "Logs copied to clipboard")
    
    def clear_all(self):
        """ניקוי כל הנתונים"""
        self.processor.clear_data()
        self.files_listbox.delete(0, tk.END)
        self.gt_status_var.set("No ground truth loaded")
        
        # ניקוי תצוגות
        for item in self.summary_tree.get_children():
            self.summary_tree.delete(item)
        for item in self.details_tree.get_children():
            self.details_tree.delete(item)
        
        self.file_combo['values'] = []
        self.report_text.delete(1.0, tk.END)
        self.logs_text.delete(1.0, tk.END)
        
        self.update_status_info()
        self.update_run_button()
        self.status_var.set("All data cleared")
    
    def update_status_info(self):
        """עדכון מידע סטטוס"""
        info_lines = []
        info_lines.append("=== STATUS ===")
        info_lines.append(f"JSON files: {len(self.processor.loaded_files)}")
        
        if self.processor.loaded_files:
            info_lines.append("Files:")
            for file_key in self.processor.loaded_files.keys():
                info_lines.append(f"  - {file_key}")
        
        if self.processor.ground_truth_data:
            info_lines.append(f"\nGround truth: {len(self.processor.ground_truth_data)} lines")
        else:
            info_lines.append("\nGround truth: Not loaded")
        
        ready = len(self.processor.loaded_files) > 0 and self.processor.ground_truth_data is not None
        info_lines.append(f"\nReady for validation: {'Yes' if ready else 'No'}")
        
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(1.0, "\n".join(info_lines))
    
    def update_run_button(self):
        """עדכון מצב כפתור הרצה"""
        ready = len(self.processor.loaded_files) > 0 and self.processor.ground_truth_data is not None
        self.run_button.config(state='normal' if ready else 'disabled')
    
    def run(self):
        """הפעלת הממשק"""
        self.root.mainloop()


def main():
    """פונקציה ראשית"""
    app = AdvancedValidationGUI()
    app.run()


if __name__ == "__main__":
    main()