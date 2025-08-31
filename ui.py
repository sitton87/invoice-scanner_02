"""
ui.py - Graphical User Interface with OCR and Hybrid Support
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
from pathlib import Path
import webbrowser
import json

from config import (
    WINDOW_TITLE, WINDOW_SIZE, MESSAGES, SUPPORTED_FORMATS,
    validate_api_key
)
from processor import process_single_invoice
from ocr_processor import process_invoice_with_ocr
from full_processor import process_full_invoice
from hybrid_processor_01 import process_invoice_simple_claude


class InvoiceProcessorGUI:
    """Graphical interface for invoice processor with OCR and Hybrid support"""
    
    def __init__(self):
        """Initialize the interface"""
        self.root = tk.Tk()
        self.processing = False
        self.processing_mode = tk.StringVar(value="ocr")  # Default OCR
        self.process_intro = tk.BooleanVar(value=True)  # Default INTRO
        self.process_main = tk.BooleanVar(value=True)   # Default MAIN
        self.setup_window()
        self.create_widgets()
        
    def setup_window(self):
        """Setup main window"""
        self.root.title(WINDOW_TITLE + " + OCR + Hybrid")
        self.root.geometry("700x800")
        self.root.resizable(True, True)
        
        # Center window on screen
        self.center_window()
        
        # Set colors and design
        self.root.configure(bg="#a2b920")
        
    def center_window(self):
        """Center window on screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
    def create_widgets(self):
        """Create interface components"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Set expansion
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(8, weight=1)  # Results row will expand
        
        # Title
        title_label = ttk.Label(
            main_frame, 
            text="Invoice Processor for Claude + OCR + Hybrid", 
            font=('Arial', 16, 'bold')
        )
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Instructions
        instructions = """Select an invoice file (image or PDF) for processing.
The system will extract invoice details and item lines and save them as a unified JSON file.
🎯 Hybrid mode automatically chooses the best method per file type!"""
        
        instructions_label = ttk.Label(
            main_frame, 
            text=instructions, 
            justify=tk.CENTER,
            wraplength=650
        )
        instructions_label.grid(row=1, column=0, columnspan=3, pady=(0, 20))
        
        # Processing settings frame - side by side
        settings_frame = ttk.LabelFrame(main_frame, text="Processing Settings", padding="15")
        settings_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        settings_frame.columnconfigure(0, weight=1)
        settings_frame.columnconfigure(1, weight=1)
        
        # Left column - Processing mode
        mode_column = ttk.Frame(settings_frame)
        mode_column.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=(0, 10))
        
        mode_label = ttk.Label(mode_column, text="Processing Mode:", font=('Arial', 10, 'bold'))
        mode_label.pack(anchor=tk.W, pady=(0, 8))
        
        # Hybrid mode as first radio button
        hybrid_radio = ttk.Radiobutton(
            mode_column, 
            text="🎯 Hybrid Mode (Smart Auto)", 
            variable=self.processing_mode,
            value="hybrid"
        )
        hybrid_radio.pack(anchor=tk.W, pady=2)
        
        # OCR mode radio button
        ocr_radio = ttk.Radiobutton(
            mode_column, 
            text="🔍 OCR Mode (Recommended)", 
            variable=self.processing_mode,
            value="ocr"
        )
        ocr_radio.pack(anchor=tk.W, pady=2)
        
        # Image mode radio button
        image_radio = ttk.Radiobutton(
            mode_column, 
            text="📷 Image Mode", 
            variable=self.processing_mode,
            value="image"
        )
        image_radio.pack(anchor=tk.W, pady=2)
        
        # Right column - Sections to process
        sections_column = ttk.Frame(settings_frame)
        sections_column.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N), padx=(10, 0))
        
        sections_label = ttk.Label(sections_column, text="Sections to Process:", font=('Arial', 10, 'bold'))
        sections_label.pack(anchor=tk.W, pady=(0, 8))
        
        intro_check = ttk.Checkbutton(
            sections_column,
            text="📋 INTRO (Invoice Details)",
            variable=self.process_intro,
            command=self._validate_section_selection
        )
        intro_check.pack(anchor=tk.W, pady=2)
        
        main_check = ttk.Checkbutton(
            sections_column,
            text="🛒 MAIN (Item Lines)",
            variable=self.process_main,
            command=self._validate_section_selection
        )
        main_check.pack(anchor=tk.W, pady=2)
        
        # File selection button
        self.select_button = ttk.Button(
            main_frame,
            text="📁 Select Invoice File",
            command=self.select_file,
            width=25
        )
        self.select_button.grid(row=3, column=0, columnspan=3, pady=(0, 20))
        
        # Selected file display
        self.file_label = ttk.Label(
            main_frame, 
            text="No file selected", 
            foreground='gray',
            wraplength=600
        )
        self.file_label.grid(row=4, column=0, columnspan=3, pady=(0, 20))
        
        # Progress bar
        self.progress_var = tk.StringVar(value="")
        self.progress_label = ttk.Label(main_frame, textvariable=self.progress_var)
        self.progress_label.grid(row=5, column=0, columnspan=3, pady=(0, 10))
        
        self.progress_bar = ttk.Progressbar(
            main_frame, 
            mode='indeterminate',
            length=500
        )
        self.progress_bar.grid(row=6, column=0, columnspan=3, pady=(0, 20))
        
        # Process button
        self.process_button = ttk.Button(
            main_frame,
            text="🚀 Process Invoice",
            command=self.process_file,
            state='disabled',
            width=25
        )
        self.process_button.grid(row=7, column=0, columnspan=3, pady=(0, 20))
        
        # Results frame - resizable
        results_frame = ttk.LabelFrame(main_frame, text="Results and Log", padding="10")
        results_frame.grid(row=8, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 15))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)  # Text box will expand
        
        # Internal frame for text and scrollbar
        text_frame = ttk.Frame(results_frame)
        text_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        # Text box for results - resizable
        self.results_text = tk.Text(
            text_frame, 
            height=12,  # Increased base height
            wrap=tk.WORD,
            font=('Consolas', 9),
            bg='white',
            fg='black'
        )
        self.results_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollbar for results
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.results_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.results_text.configure(yscrollcommand=scrollbar.set)
        
        # Action buttons
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=9, column=0, pady=(10, 0))
        
        self.open_output_button = ttk.Button(
            buttons_frame,
            text="📂 Open Output Folder",
            command=self.open_output_folder,
            state='disabled'
        )
        self.open_output_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.copy_log_button = ttk.Button(
            buttons_frame,
            text="📋 Copy Log",
            command=self.copy_log_to_clipboard
        )
        self.copy_log_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.clear_button = ttk.Button(
            buttons_frame,
            text="🗑️ Clear Results",
            command=self.clear_results
        )
        self.clear_button.pack(side=tk.LEFT)
        
        # Check API Key
        self.check_api_key()
        
        # Debug message to ensure log is working
        self.add_to_log("🎯 Interface loaded successfully - log ready for operation!")
    
    def _validate_section_selection(self):
        """Validation that at least one section is selected"""
        if not self.process_intro.get() and not self.process_main.get():
            # If both are unchecked, check MAIN back
            self.process_main.set(True)
            messagebox.showwarning("Selection Required", "You must select at least one section to process!")
        
        # Update process button text
        self._update_process_button_text()
    
    def _get_processing_mode(self):
        """Get current processing mode"""
        mode = self.processing_mode.get().upper()
        return mode
    
    def _update_process_button_text(self):
        """Update process button text based on selection"""
        if hasattr(self, 'process_button'):
            sections = []
            if self.process_intro.get():
                sections.append("INTRO")
            if self.process_main.get():
                sections.append("MAIN")
            
            button_text = f"🚀 Process {' + '.join(sections)}"
            self.process_button.config(text=button_text)
        
    def check_api_key(self):
        """Check and warn about API Key"""
        try:
            if not validate_api_key():
                warning_text = """⚠️ No API key configured!
                
Update the config.py file with your key from Anthropic.
Get a key at: https://console.anthropic.com/

"""
                
                if hasattr(self, 'results_text') and self.results_text:
                    self.results_text.insert(tk.END, warning_text)
                    self.results_text.configure(foreground='red')
                else:
                    print("DEBUG: Cannot display API warning - results_text doesn't exist")
            else:
                self.add_to_log("✅ API key is properly configured")
        except Exception as e:
            print(f"DEBUG: Error checking API Key: {e}")
            
    def select_file(self):
        """Select invoice file"""
        filetypes = [
            ("All supported files", " ".join([f"*{ext}" for ext in SUPPORTED_FORMATS])),
            ("Images", "*.jpg *.jpeg *.png *.bmp *.tiff"),
            ("PDF files", "*.pdf"),
            ("All files", "*.*")
        ]
        
        filename = filedialog.askopenfilename(
            title=MESSAGES["select_file"],
            filetypes=filetypes
        )
        
        if filename:
            self.selected_file = filename
            # Display filename
            file_path = Path(filename)
            display_name = f"Selected: {file_path.name}"
            self.file_label.config(text=display_name, foreground='black')
            
            # Add to log
            mode_text = self._get_processing_mode()
            sections = []
            if self.process_intro.get():
                sections.append("INTRO")
            if self.process_main.get():
                sections.append("MAIN")
            sections_text = " + ".join(sections)
            
            self.add_to_log(f"📄 Selected file: {file_path.name}")
            self.add_to_log(f"   Full path: {filename}")
            self.add_to_log(f"🎯 Processing mode: {mode_text}")
            self.add_to_log(f"📋 Sections: {sections_text}\n")
            
            # Enable process button
            if validate_api_key():
                self.process_button.config(state='normal')
                self._update_process_button_text()
            
    def process_file(self):
        """Process the selected file"""
        if not hasattr(self, 'selected_file'):
            messagebox.showerror("Error", "No file selected")
            return
            
        if not validate_api_key():
            messagebox.showerror("Error", MESSAGES["error_api_key"])
            return
        
        # Add to log
        mode_text = self._get_processing_mode()
        sections = []
        if self.process_intro.get():
            sections.append("INTRO")
        if self.process_main.get():
            sections.append("MAIN")
        sections_text = " + ".join(sections)
        
        self.add_to_log(f"🚀 Starting invoice processing in {mode_text} mode")
        self.add_to_log(f"📋 Processing sections: {sections_text}")
        
        # Save start time
        import time
        from datetime import datetime, timedelta
        self.start_time = time.time()
        self.start_datetime = datetime.now()
        
        self.add_to_log(f"⏰ Start time: {self.start_datetime.strftime('%H:%M:%S')}\n")
            
        # Start processing in background
        self.start_processing()
        
        # Run in separate thread
        thread = threading.Thread(target=self.process_in_background)
        thread.daemon = True
        thread.start()
        
    def start_processing(self):
        """Start processing mode"""
        self.processing = True
        self.select_button.config(state='disabled')
        self.process_button.config(state='disabled')
        self.progress_bar.start()
        
    def process_in_background(self):
        """Process in background"""
        try:
            # Function to update progress
            def update_progress(message):
                self.root.after(0, lambda: self.progress_var.set(message))
                self.root.after(0, lambda: self.add_to_log(f"🔄 {message}"))
                
            # Select processing mode
            process_intro = self.process_intro.get()
            process_main = self.process_main.get()
            processing_mode = self.processing_mode.get()
            
            # Check which mode is selected
            if processing_mode == "hybrid":
                # Hybrid mode - use hybrid processor for MAIN
                result = {"success": True, "intro": None, "main": None}
                
                if process_main:
                    update_progress("Processing MAIN with Hybrid processor...")
                    hybrid_result = process_invoice_simple_claude(
                        self.selected_file,
                        progress_callback=update_progress
                    )
                    if hybrid_result["success"]:
                        result["main"] = hybrid_result["json_data"]
                        result["extracted_text"] = hybrid_result.get("extracted_text", "")
                        result["method_used"] = hybrid_result.get("method_used", "hybrid")
                    else:
                        result["success"] = False
                        result["message"] = hybrid_result["message"]
                        self.root.after(0, lambda: self.show_results(result))
                        return
                
                if process_intro:
                    update_progress("Processing INTRO...")
                    # For INTRO, still use the regular processor with OCR
                    intro_result = process_full_invoice(
                        file_path=self.selected_file,
                        process_intro=True,
                        process_main=False,
                        use_ocr=True,
                        progress_callback=update_progress
                    )
                    if intro_result["success"] and "intro" in intro_result:
                        result["intro"] = intro_result["intro"]
                
                result["message"] = "Hybrid processing completed successfully!"
                
            else:
                # Regular mode - OCR or Image
                use_ocr = (processing_mode == "ocr")
                
                result = process_full_invoice(
                    file_path=self.selected_file,
                    process_intro=process_intro,
                    process_main=process_main,
                    use_ocr=use_ocr,
                    progress_callback=update_progress
                )
            
            # Update results in main thread
            self.root.after(0, lambda: self.show_results(result))
            
        except Exception as e:
            error_result = {
                "success": False,
                "error": str(e),
                "message": f"Unexpected error: {str(e)}"
            }
            self.root.after(0, lambda: self.show_results(error_result))
            
    def show_results(self, result):
        """Display processing results"""
        self.stop_processing()
        
        # Calculate runtime
        import time
        from datetime import datetime, timedelta
        
        end_time = time.time()
        end_datetime = datetime.now()
        
        # Calculate duration
        duration_seconds = end_time - self.start_time
        duration_timedelta = timedelta(seconds=duration_seconds)
        
        # User-friendly format
        if duration_seconds < 60:
            duration_text = f"{duration_seconds:.1f} seconds"
        elif duration_seconds < 3600:
            minutes = int(duration_seconds // 60)
            seconds = duration_seconds % 60
            duration_text = f"{minutes}:{seconds:04.1f} minutes"
        else:
            hours = int(duration_seconds // 3600)
            minutes = int((duration_seconds % 3600) // 60)
            seconds = duration_seconds % 60
            duration_text = f"{hours}:{minutes:02d}:{seconds:04.1f} hours"
        
        # Add end time and duration
        self.add_to_log(f"⏰ End time: {end_datetime.strftime('%H:%M:%S')}")
        self.add_to_log(f"⏱️ Processing duration: {duration_text}")
        
        if result["success"]:
            # Success
            self.add_to_log("✅ Processing completed successfully!")
            
            if 'output_file' in result:
                self.add_to_log(f"📁 File saved at: {result['output_file']}")
                self.last_output_file = result['output_file']
                self.open_output_button.config(state='normal')
            
            self.add_to_log("=" * 60)
            self.add_to_log("📋 JSON Content:")
            self.add_to_log("=" * 60)
            
            # Display formatted JSON
            json_formatted = json.dumps(result.get('json_data', {
                k: v for k, v in result.items() 
                if k not in ['success', 'message', 'output_file', 'extracted_text', 'processing_info']
            }), ensure_ascii=False, indent=2)
            self.add_to_log(json_formatted)
            
            # Display OCR text if available
            if 'extracted_text' in result:
                self.add_to_log("\n" + "=" * 60)
                self.add_to_log("🔍 Extracted OCR Text:")
                self.add_to_log("=" * 60)
                self.add_to_log(result['extracted_text'][:1000] + "..." if len(result['extracted_text']) > 1000 else result['extracted_text'])
            
            # Add performance statistics
            self.add_to_log("\n" + "=" * 60)
            self.add_to_log("📊 Performance Statistics:")
            self.add_to_log("=" * 60)
            self.add_to_log(f"⏱️ Total processing time: {duration_text}")
            
            # Display method used if available
            if 'method_used' in result:
                self.add_to_log(f"🔧 Method used: {result['method_used']}")
            
            # Display processing mode
            mode_text = self._get_processing_mode()
            self.add_to_log(f"🎯 Processing mode: {mode_text}")
            
            self.results_text.configure(foreground='black')
            
            # Success message with time
            success_message = f"{result['message']}\n\nProcessing time: {duration_text}"
            messagebox.showinfo("Success", success_message)
            
        else:
            # Failure
            self.add_to_log("❌ Processing failed!")
            self.add_to_log(f"💥 Error: {result['message']}")
            
            if 'error' in result:
                self.add_to_log(f"📝 Error details: {result['error']}")
                
            # Statistics even in case of failure
            self.add_to_log(f"\n⏱️ Time until failure: {duration_text}")
                
            self.add_to_log("\n💡 Troubleshooting tips:")
            self.add_to_log("• Try Hybrid mode for automatic method selection")
            self.add_to_log("• Try OCR mode if you used Image mode")
            self.add_to_log("• Make sure the file is a clear invoice")
            self.add_to_log("• Check that API key is valid")
            self.add_to_log("• Ensure internet connection")
            self.add_to_log("• Try a different file")
            
            self.results_text.configure(foreground='red')
            
            # Error message with time
            error_message = f"{result['message']}\n\nTime until failure: {duration_text}"
            messagebox.showerror("Error", error_message)
        
        # Add separator line
        self.add_to_log("\n" + "=" * 80 + "\n")
            
    def stop_processing(self):
        """End processing mode"""
        self.processing = False
        self.progress_bar.stop()
        self.progress_var.set("")
        self.select_button.config(state='normal')
        
        if validate_api_key():
            self.process_button.config(state='normal')
            
    def open_output_folder(self):
        """Open output folder"""
        if hasattr(self, 'last_output_file'):
            output_dir = Path(self.last_output_file).parent
            # Open in file explorer
            import subprocess
            subprocess.run(['explorer', str(output_dir)], shell=True)
            
    def copy_log_to_clipboard(self):
        """Copy log to clipboard"""
        try:
            # Get all text from log
            log_content = self.results_text.get(1.0, tk.END)
            
            # Copy to clipboard
            self.root.clipboard_clear()
            self.root.clipboard_append(log_content)
            self.root.update()  # Ensure clipboard is updated
            
            # Confirmation message
            messagebox.showinfo("Copied", "Log copied to clipboard successfully! 📋")
            
        except Exception as e:
            messagebox.showerror("Error", f"Copy error: {str(e)}")
            
    def clear_results(self):
        """Clear results"""
        self.results_text.delete(1.0, tk.END)
        self.open_output_button.config(state='disabled')
        
        # Add clear message
        self.add_to_log(f"🗑️ Log cleared at {self.get_current_time()}\n")
        
    def add_to_log(self, message):
        """Add message to log"""
        try:
            self.results_text.insert(tk.END, message + "\n")
            self.results_text.see(tk.END)  # Scroll to end
            self.root.update_idletasks()  # Immediate update
        except Exception as e:
            print(f"DEBUG: Error adding to log: {e} - Message: {message}")
        
    def get_current_time(self):
        """Get current time"""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")
        
    def run(self):
        """Run the interface"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.root.quit()


def create_and_run_gui():
    """Create and run the graphical interface"""
    app = InvoiceProcessorGUI()
    app.run()


if __name__ == "__main__":
    create_and_run_gui()