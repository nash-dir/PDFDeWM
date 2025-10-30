# PDFDeWM - A tool to remove watermarks from PDF files.
# Copyright (C) 2025  nash-dir
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


import os
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import threading
import queue
from collections import defaultdict
from typing import List, Dict, Any, Tuple
import sys
import fitz


# Attempt to import Pillow, which is a required dependency.
try:
    from PIL import Image, ImageTk, ImageDraw
except ImportError:
    Image = None
    ImageTk = None
    ImageDraw = None

from utils import FileManager, ThumbnailManager
import core

import sys
import fitz
print("--- Environment Check ---")
print("Python Executable:", sys.executable)
print("Fitz (PyMuPDF) Version:", fitz.__version__)
print("-------------------------")

class QueueLogger:
    def __init__(self, q: queue.Queue):
        self.queue = q
        self.buffer = ""

    def write(self, text: str):
        self.buffer += text
        if '\n' in self.buffer:
            lines = self.buffer.split('\n')
            for line in lines[:-1]:
                self.queue.put(('log', line + '\n'))
            self.buffer = lines[-1]

    def flush(self):
        if self.buffer:
            self.queue.put(('log', self.buffer + '\n'))
            self.buffer = ""


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.core = core
        self.file_manager = FileManager()
        self.thumbnail_manager = ThumbnailManager()

        self.title("PDF Watermark Remover")
        self.geometry("800x800") 
        self.minsize(600, 600)

        self.input_files: List[str] = []
        self.output_dir: str = ""
        self.watermark_candidates: Dict[Tuple, Dict[str, Any]] = {}
        self.task_queue: queue.Queue = queue.Queue()

        self.suffix_var = tk.StringVar(value="_removed")
        self.copy_skipped_var = tk.BooleanVar(value=False)
        self.overwrite_var = tk.BooleanVar(value=False)
        self.text_keywords_var = tk.StringVar()
        self.scan_threshold_var = tk.IntVar(value=80)
        self.sanitize_var = tk.BooleanVar(value=False)

        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.queue_logger = QueueLogger(self.task_queue)

        self._setup_ui()
        self.redirect_logging()
        self.protocol("WM_DELETE_WINDOW", self.on_closing) 
        self.after(100, self.process_queue)
        self._bind_hotkeys()

    def _bind_hotkeys(self):
        self.bind_all("<Control-a>", self.add_files) # Add Files (Ctrl+A)
        self.bind_all("<Control-Shift-A>", self.add_folder) # Add Folder (Ctrl+Shift+A)

        self.bind_all("<Control-s>", self.select_output_dir) # Select Output Dir (Ctrl+S)
        self.bind_all("<Control-d>", self.start_scan) # Scan (Ctrl+D)
        self.bind_all("<Control-f>", self.start_removal) # Run Removal (Ctrl+F)

        # ADDED: Ctrl+Q - Move focus to Output Suffix Entry and select all
        self.bind_all("<Control-q>", lambda e: self._focus_and_select(self.suffix_entry)) 
        # ADDED: Ctrl+W - Move focus to Text Keyword Entry and select all
        self.bind_all("<Control-w>", lambda e: self._focus_and_select(self.text_keyword_entry))

        # intentional ctrl+shift key binding duplication for lesser hassle
        self.bind_all("<Control-Shift-S>", self.select_output_dir) # Select Output Dir (Ctrl+Shift+S)
        self.bind_all("<Control-Shift-D>", self.start_scan) # Scan (Ctrl+Shift+D)
        self.bind_all("<Control-Shift-F>", self.start_removal) # Run Removal (Ctrl+Shift+F)
        self.bind_all("<Control-Shift-Q>", lambda e: self._focus_and_select(self.suffix_entry))
        self.bind_all("<Control-Shift-W>", lambda e: self._focus_and_select(self.text_keyword_entry))

        self.bind_all("<Control-t>", self.on_closing)
        self.bind_all("<Control-Shift-T>", self.on_closing)

    def _focus_and_select(self, entry_widget):
        """Set focus to the entry widget and select all text."""
        entry_widget.focus_set()
        entry_widget.selection_range(0, tk.END)

    def redirect_logging(self):
        sys.stdout = self.queue_logger
        sys.stderr = self.queue_logger

    def restore_logging(self):
        if hasattr(sys.stdout, 'flush'):
            sys.stdout.flush()
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr

    def on_closing(self, event=None):
        self.restore_logging()
        self.destroy()

    def _setup_ui(self):
        top_frame = ttk.Frame(self, padding="10")
        top_frame.pack(fill="x", side="top", pady=(0,5))
        top_frame.columnconfigure(1, weight=1)

        file_button_frame = ttk.Frame(top_frame)
        file_button_frame.grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, 5))

        ttk.Button(file_button_frame, text="Add Files(ctrl+a)", command=self.add_files).pack(fill="x", pady=2)
        ttk.Button(file_button_frame, text="Add Folder(ctrl+A)", command=self.add_folder).pack(fill="x", pady=2)
        ttk.Button(file_button_frame, text="Remove Selected(del)", command=self.remove_selected_files).pack(fill="x", pady=2)
        
        self.file_listbox = tk.Listbox(top_frame, height=5, selectmode="extended")
        self.file_listbox.grid(row=0, column=1, rowspan=2, sticky="ew")
        list_scroll = ttk.Scrollbar(top_frame, orient="vertical", command=self.file_listbox.yview)
        list_scroll.grid(row=0, column=2, rowspan=2, sticky="ns")
        self.file_listbox.config(yscrollcommand=list_scroll.set)

        # when focused on Listbox, binding delete / backspace key to remove_selected_files 
        self.file_listbox.bind("<Delete>", self.remove_selected_files)
        self.file_listbox.bind("<BackSpace>", self.remove_selected_files)

        ttk.Label(top_frame, text="Output Folder:").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.output_dir_entry = ttk.Entry(top_frame)
        self.output_dir_entry.grid(row=2, column=1, sticky="ew", pady=(10, 0))
        ttk.Button(top_frame, text="Browse(ctrl+s)", command=self.select_output_dir).grid(row=2, column=2, sticky="e", pady=(10, 0), padx=(5,0))
        
        ttk.Label(top_frame, text="Output Suffix(ctrl+q):").grid(row=3, column=0, sticky="w", pady=(5, 0))
        self.suffix_entry = ttk.Entry(top_frame, textvariable=self.suffix_var)
        self.suffix_entry.grid(row=3, column=1, sticky="ew", pady=(5, 0))

        options_container = ttk.Frame(top_frame)
        options_container.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(5,0))
        options_container.columnconfigure(1, weight=1)

        scan_options_frame = ttk.Frame(options_container)
        scan_options_frame.grid(row=0, column=0, columnspan=2, pady=(0, 5), sticky="ew")
        
        ttk.Label(scan_options_frame, text="Image Scan Threshold (%):").pack(side="left", padx=(0, 5))
        
        self.threshold_spinbox = ttk.Spinbox(
            scan_options_frame, from_=1, to=100, increment=1,
            textvariable=self.scan_threshold_var, width=5
        )
        self.threshold_spinbox.pack(side="left")

        ttk.Label(options_container, text="Text Keywords(ctrl+w, use ';' to separate):").grid(row=1, column=0, sticky="w", pady=(5, 0))
        self.text_keyword_entry = ttk.Entry(options_container, textvariable=self.text_keywords_var)
        self.text_keyword_entry.grid(row=1, column=1, sticky="ew", pady=(5, 0))

        self.overwrite_warning_label = ttk.Label(
            options_container, text="Original input files will be overwritten irreversibly",
            foreground="red", font=("TkDefaultFont", 9, "bold")
        )
        self.overwrite_warning_label.grid(row=2, column=1, sticky="w", padx=0, pady=(2,0))
        self.overwrite_warning_label.grid_remove()
        
        # Create a container for the action buttons and checkboxes
        action_frame = ttk.Frame(top_frame)
        action_frame.grid(row=5, column=0, columnspan=3, pady=(10, 0), sticky="ew")

        # Left-aligned items
        left_action_frame = ttk.Frame(action_frame)
        left_action_frame.pack(side="left")
        
        self.scan_button = ttk.Button(left_action_frame, text="Scan Selected Files(ctrl+d)", command=self.start_scan)
        self.scan_button.pack(side="left", padx=(0, 2))
        self.remove_button = ttk.Button(left_action_frame, text="Run Watermark Removal(ctrl+f)", command=self.start_removal, state="disabled")
        self.remove_button.pack(side="left", padx=2)
        
        self.copy_skipped_checkbox = ttk.Checkbutton(left_action_frame, text="Copy unprocessed files", variable=self.copy_skipped_var)
        self.copy_skipped_checkbox.pack(side="left", padx=7)
        
        self.overwrite_checkbox = ttk.Checkbutton(left_action_frame, text="Overwrite existing files", variable=self.overwrite_var, command=self._check_overwrite_warning)
        self.overwrite_checkbox.pack(side="left", padx=7)

        # Right-aligned item
        right_action_frame = ttk.Frame(action_frame)
        right_action_frame.pack(side="right")

        self.sanitize_checkbox = ttk.Checkbutton(
            right_action_frame, text="Scrub invisible text",
            variable=self.sanitize_var
        )
        self.sanitize_checkbox.pack(side="right")

        self.suffix_var.trace_add("write", self._check_overwrite_warning)
        # ... (rest of the UI setup is unchanged)
        bottom_frame = ttk.Frame(self, padding="10")
        bottom_frame.pack(fill="x", side="bottom")
        bottom_frame.columnconfigure(0, weight=1)

        progress_frame = ttk.Frame(bottom_frame)
        progress_frame.grid(row=0, column=0, sticky="ew")
        progress_frame.columnconfigure(0, weight=1)

        self.status_label = ttk.Label(progress_frame, text="Ready.")
        self.status_label.grid(row=0, column=0, columnspan=2, sticky="w")
        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate")
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        self.percent_label = ttk.Label(progress_frame, text="0%")
        self.percent_label.grid(row=1, column=1, sticky="w", padx=(5, 0), pady=(5, 0))

        log_frame = ttk.Labelframe(bottom_frame, text="Logs", padding=5)
        log_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = tk.Text(log_frame, height=8, state="disabled", wrap="word", background="#f0f0f0")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.config(yscrollcommand=log_scroll.set)

        mid_frame = ttk.Frame(self, padding=(10, 0, 10, 10))
        mid_frame.pack(fill="both", expand=True)
        
        self.canvas = tk.Canvas(mid_frame, borderwidth=0, background="#ffffff")
        self.thumbnail_frame = ttk.Frame(self.canvas, padding=5)
        self.scrollbar = ttk.Scrollbar(mid_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas_window = self.canvas.create_window((4, 4), window=self.thumbnail_frame, anchor="nw")
        self.thumbnail_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width - 8))


    def _check_overwrite_warning(self, *args):
        is_suffix_empty = not self.suffix_var.get().strip()
        is_overwrite_checked = self.overwrite_var.get()
        is_dangerous_overwrite = is_suffix_empty and is_overwrite_checked

        is_output_dir_unsafe = False
        if not self.output_dir:
            is_output_dir_unsafe = True
        else:
            output_path = Path(self.output_dir).resolve()
            for file_str in self.input_files:
                input_path = Path(file_str).parent.resolve()
                if output_path == input_path:
                    is_output_dir_unsafe = True
                    break
        
        if is_dangerous_overwrite and is_output_dir_unsafe:
            self.overwrite_warning_label.grid()
        else:
            self.overwrite_warning_label.grid_remove()


    def add_files(self, event=None):
        new_files = self.file_manager.ask_for_files()
        for file in new_files:
            if file not in self.input_files:
                self.input_files.append(file)
                self.file_listbox.insert("end", Path(file).name)
        self._check_overwrite_warning()


    def add_folder(self, event=None):
        folder = self.file_manager.ask_for_folder()
        if folder:
            for file in sorted(Path(folder).rglob("*.pdf")):
                file_str = str(file)
                if file_str not in self.input_files:
                    self.input_files.append(file_str)
                    display_name = file.relative_to(folder)
                    self.file_listbox.insert("end", display_name)
        self._check_overwrite_warning()


    def remove_selected_files(self, event=None):
            selected_indices = self.file_listbox.curselection()
            if not selected_indices: 
                return
            target_index = selected_indices[0] 

            for index in reversed(selected_indices):
                self.input_files.pop(index)
                self.file_listbox.delete(index)
            
            current_list_size = self.file_listbox.size()

            if current_list_size > 0:
                final_selection_index = min(target_index, current_list_size - 1)
                
                self.file_listbox.selection_clear(0, tk.END)
                self.file_listbox.selection_set(final_selection_index)
                self.file_listbox.activate(final_selection_index)
                self.file_listbox.see(final_selection_index)
            else:
                self.file_listbox.selection_clear(0, tk.END)

            self._check_overwrite_warning()


    def select_output_dir(self, event=None): 
        directory = self.file_manager.ask_for_output_dir()
        if directory:
            self.output_dir = directory
            self.output_dir_entry.delete(0, "end")
            self.output_dir_entry.insert(0, self.output_dir)
            self._check_overwrite_warning()


    def start_scan(self, event=None): 
        if self.scan_button['state'] == 'disabled' and event is not None:
            return

        if not self.input_files:
            messagebox.showwarning("No Files", "Please add PDF files to scan first.")
            return

        self.clear_thumbnails()
        self.scan_button.config(state="disabled")
        self.remove_button.config(state="disabled")
        self.status_label.config(text="Scanning for watermark candidates...")
        self.progress_bar["value"] = 0
        self.percent_label.config(text="0%")

        scan_threshold_percent = self.scan_threshold_var.get()
        min_page_ratio = scan_threshold_percent / 100.0
        
        raw_text = self.text_keywords_var.get()
        text_keywords = [k.strip() for k in raw_text.strip().split(';') if k.strip()]

        threading.Thread(
            target=self.scan_worker, 
            args=(min_page_ratio, text_keywords), 
            daemon=True
        ).start()


    def start_removal(self, event=None): 
        if self.remove_button['state'] == 'disabled' and event is not None:
            return

        candidates_to_remove = defaultdict(lambda: defaultdict(list))
        
        for key, data in self.watermark_candidates.items():
            if data['var'].get():
                candidate_type, file_path, *rest = key
                if candidate_type == 'image':
                    xref = rest[0]
                    candidates_to_remove[file_path]['image'].append(xref)
                elif candidate_type == 'text':
                    page_num, bbox = rest
                    text_info = {'page': page_num, 'bbox': bbox}
                    candidates_to_remove[file_path]['text'].append(text_info)

        if not self.output_dir or not Path(self.output_dir).is_dir():
            self.select_output_dir()
            if not self.output_dir: return
        
        sanitize = self.sanitize_var.get()
        if not candidates_to_remove and not self.copy_skipped_var.get() and not sanitize:
            messagebox.showwarning(
                "No Action", 
                "No watermarks selected to remove, 'Copy unprocessed files' is disabled, "
                "and 'Sanitize' option is off."
            )
            return

        suffix = self.suffix_var.get()
        copy_skipped = self.copy_skipped_var.get()
        overwrite = self.overwrite_var.get()

        self.scan_button.config(state="disabled")
        self.remove_button.config(state="disabled")
        
        input_root = None
        if self.input_files:
            try:
                common_path = os.path.commonpath(self.input_files)
                if os.path.isdir(common_path):
                    input_root = common_path
            except ValueError:
                pass

        args = (
            self.input_files, candidates_to_remove, suffix,
            copy_skipped, overwrite, sanitize, input_root 
        )
        threading.Thread(target=self.removal_worker, args=args, daemon=True).start()


    def process_queue(self):
        try:
            while True:
                task_type, *payload = self.task_queue.get_nowait()
                
                if task_type == 'candidate_found':
                    self.add_thumbnail(*payload)
                elif task_type == 'scan_complete':
                    count = payload[0]
                    self.status_label.config(text=f"Scan complete. {count} watermark candidates found.")
                    self.scan_button.config(state="normal")
                    self.remove_button.config(state="normal") # Always enable after scan
                elif task_type == 'removal_progress':
                    n, m = payload
                    self.status_label.config(text=f"Processing files... ({n}/{m})")
                    progress = int((n / m) * 100)
                    self.progress_bar["value"] = progress
                    self.percent_label.config(text=f"{progress}%")
                elif task_type == 'removal_complete':
                    self.status_label.config(text="Watermark removal complete!")
                    self.progress_bar["value"] = 100
                    self.percent_label.config(text="100%")
                    messagebox.showinfo("Complete", "Processing is complete.")
                    self.scan_button.config(state="normal")
                    self.remove_button.config(state="disabled")
                elif task_type == 'log':
                    self.log_message(payload[0])
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_queue)


    def scan_worker(self, min_page_ratio: float, text_keywords: List[str]):
        candidates = self.core.scan_files_for_watermarks(
            self.input_files, 
            min_page_ratio=min_page_ratio,
            text_keywords=text_keywords 
        )
        for key, data in candidates.items():
            self.task_queue.put(('candidate_found', data, key))
        self.task_queue.put(('scan_complete', len(candidates)))


    def removal_worker(
        self, all_input_files: List[str],
        candidates_by_file: Dict[str, Dict[str, List]],
        suffix: str, copy_skipped: bool, overwrite: bool,
        sanitize: bool, input_root: str  
    ):
        total_files = len(all_input_files)
        for i, file_path in enumerate(all_input_files):
            self.task_queue.put(('removal_progress', i + 1, total_files))
            
            should_process = (file_path in candidates_by_file) or sanitize

            if should_process:
                to_remove = candidates_by_file.get(file_path, {})
                self.core.process_and_remove_watermarks(
                    file_path, self.output_dir, to_remove, suffix, 
                    overwrite=overwrite, sanitize_hidden_text=sanitize,
                    input_dir_root=input_root 
                )
            elif copy_skipped:
                self.core.copy_unprocessed_file(
                    file_path, self.output_dir, 
                    overwrite=overwrite,
                    input_dir_root=input_root  
                )

        self.task_queue.put(('removal_complete',))


    def clear_thumbnails(self):
        for widget in self.thumbnail_frame.winfo_children():
            widget.destroy()
        self.watermark_candidates.clear()

    def add_thumbnail(self, candidate_data: Dict[str, Any], candidate_key: Tuple):
        item_frame = ttk.Frame(self.thumbnail_frame, padding=5, relief="groove", borderwidth=1)
        item_frame.pack(pady=5, padx=5, fill="x")

        var = tk.BooleanVar(value=True)
        chk = ttk.Checkbutton(item_frame, variable=var)
        chk.pack(side="left", padx=(0, 10))

        if candidate_data['type'] == 'image':
            photo_img = self.thumbnail_manager.create_image_thumbnail(candidate_data['pil_img'])
        else:
            full_text = candidate_data.get('full_text', candidate_data['text'])
            photo_img = self.thumbnail_manager.create_text_thumbnail(full_text)

        img_label = ttk.Label(item_frame, image=photo_img)
        img_label.pack(side="left")

        info_lines = []
        if candidate_data['type'] == 'image':
            info_lines.append(f"Type: Image")
            info_lines.append(f"XRef: {candidate_data['xref']}")
        elif candidate_data['type'] == 'text':
            info_lines.append(f"Type: Text")
            info_lines.append(f"Keyword: \"{candidate_data['text']}\"")
            info_lines.append(f"Page: {candidate_data['page'] + 1}")

        info_lines.append(f"Source: {candidate_data['source']}")
        info_text = "\n".join(info_lines)

        info_label = ttk.Label(item_frame, text=info_text, justify="left")
        info_label.pack(side="left", padx=10)

        self.watermark_candidates[candidate_key] = candidate_data
        self.watermark_candidates[candidate_key]['img_obj'] = photo_img
        self.watermark_candidates[candidate_key]['var'] = var


    def log_message(self, text: str):
        self.log_text.config(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.config(state="disabled")


if __name__ == "__main__":
    app = App()
    app.mainloop()

