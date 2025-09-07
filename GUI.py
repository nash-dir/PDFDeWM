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


import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import threading
import queue
from collections import defaultdict
from typing import List, Dict, Any, Tuple
import sys


# Attempt to import Pillow, which is a required dependency.
try:
    from PIL import Image, ImageTk
except ImportError:
    # This is a fallback for when the script is run directly without Pillow.
    # The main App class will handle showing a proper error message.
    Image = None
    ImageTk = None

import core


class QueueLogger:
    """Redirects stdout/stderr to a queue for thread-safe GUI updates.
    
    It buffers text and puts a complete line onto the queue only when a
    newline character is received.
    """
    def __init__(self, q: queue.Queue):
        """Initializes the logger with a queue.

        Args:
            q: The queue to which log messages will be sent.
        """
        self.queue = q
        self.buffer = ""

    def write(self, text: str):
        """Writes text to the buffer and sends complete lines to the queue."""
        self.buffer += text
        if '\n' in self.buffer:
            lines = self.buffer.split('\n')
            for line in lines[:-1]:
                self.queue.put(('log', line + '\n'))
            self.buffer = lines[-1]

    def flush(self):
        """Flushes any remaining text in the buffer to the queue."""
        if self.buffer:
            self.queue.put(('log', self.buffer + '\n'))
            self.buffer = ""


class App(tk.Tk):
    """Main class for the PDF Watermark Remover GUI application."""

    def __init__(self):
        super().__init__()

        if not Image or not ImageTk:
            messagebox.showerror(
                "Library Error",
                "Pillow library is required.\nPlease install it using: 'pip install pillow'"
            )
            self.destroy()
            return

        self.core = core

        self.title("PDF Watermark Remover")
        self.geometry("800x800") 
        self.minsize(600, 600)

        self.input_files: List[str] = []
        self.output_dir: str = ""
        self.watermark_candidates: Dict[Tuple[str, int], Dict[str, Any]] = {}
        self.task_queue: queue.Queue = queue.Queue()

        self.suffix_var = tk.StringVar(value="_removed")
        self.copy_skipped_var = tk.BooleanVar(value=False)
        self.overwrite_var = tk.BooleanVar(value=False)
        self.min_page_ratio_var = tk.DoubleVar(value=0.5)

        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.queue_logger = QueueLogger(self.task_queue)

        self._setup_ui()
        self.redirect_logging()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.after(100, self.process_queue)
        
    def redirect_logging(self):
        """Redirects `sys.stdout` and `sys.stderr` to the GUI logger."""
        sys.stdout = self.queue_logger
        sys.stderr = self.queue_logger

    def restore_logging(self):
        """Restores original `sys.stdout` and `sys.stderr`."""
        if hasattr(sys.stdout, 'flush'):
            sys.stdout.flush()
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr

    def on_closing(self):
        """Handles the window closing event."""
        self.restore_logging()
        self.destroy()

    def _check_overwrite_warning(self, *args):
        """Shows or hides the overwrite warning label based on user settings."""
        # Condition 1: Suffix is empty and overwrite is checked
        is_suffix_empty = not self.suffix_var.get().strip()
        is_overwrite_checked = self.overwrite_var.get()
        is_dangerous_overwrite = is_suffix_empty and is_overwrite_checked

        # Condition 2: Output folder is not set or is same as an input folder
        is_output_dir_unsafe = False
        if not self.output_dir:
            is_output_dir_unsafe = True  # Output is not designated
        else:
            output_path = Path(self.output_dir).resolve()
            for file_str in self.input_files:
                input_path = Path(file_str).parent.resolve()
                if output_path == input_path:
                    is_output_dir_unsafe = True  # Output is same as an input folder
                    break
        
        # Show warning if either condition is met
        if is_dangerous_overwrite and is_output_dir_unsafe:
            self.overwrite_warning_label.pack(side="left", padx=15, pady=(2,0))
        else:
            self.overwrite_warning_label.pack_forget()

    def _setup_ui(self):
        """Initializes and places all the widgets in the main window."""
        top_frame = ttk.Frame(self, padding="10")
        top_frame.pack(fill="x", side="top", pady=(0,5))
        top_frame.columnconfigure(1, weight=1)

        file_button_frame = ttk.Frame(top_frame)
        file_button_frame.grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, 5))

        ttk.Button(file_button_frame, text="Add Files", command=self.add_files).pack(fill="x", pady=2)
        ttk.Button(file_button_frame, text="Add Folder", command=self.add_folder).pack(fill="x", pady=2)
        ttk.Button(file_button_frame, text="Remove Selected", command=self.remove_selected_files).pack(fill="x", pady=2)
        
        self.file_listbox = tk.Listbox(top_frame, height=5, selectmode="extended")
        self.file_listbox.grid(row=0, column=1, rowspan=2, sticky="ew")
        list_scroll = ttk.Scrollbar(top_frame, orient="vertical", command=self.file_listbox.yview)
        list_scroll.grid(row=0, column=2, rowspan=2, sticky="ns")
        self.file_listbox.config(yscrollcommand=list_scroll.set)

        ttk.Label(top_frame, text="Output Folder:").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.output_dir_entry = ttk.Entry(top_frame)
        self.output_dir_entry.grid(row=2, column=1, sticky="ew", pady=(10, 0))
        ttk.Button(top_frame, text="Browse", command=self.select_output_dir).grid(row=2, column=2, sticky="e", pady=(10, 0), padx=(5,0))
        
        ttk.Label(top_frame, text="Output Suffix:").grid(row=3, column=0, sticky="w", pady=(5, 0))
        self.suffix_entry = ttk.Entry(top_frame, textvariable=self.suffix_var)
        self.suffix_entry.grid(row=3, column=1, sticky="ew", pady=(5, 0))

        scan_options_frame = ttk.Frame(top_frame)
        scan_options_frame.grid(row=4, column=0, columnspan=3, pady=(5, 0), sticky="w")
        
        ttk.Label(scan_options_frame, text="Scan Threshold:").pack(side="left", padx=(0, 5))
        self.ratio_scale = ttk.Scale(scan_options_frame, from_=0.1, to=1.0, variable=self.min_page_ratio_var, orient="horizontal")
        self.ratio_scale.pack(side="left", fill="x", expand=True)
        self.ratio_label = ttk.Label(scan_options_frame, text=f"{self.min_page_ratio_var.get():.2f}")
        self.ratio_label.pack(side="left", padx=5)
        self.min_page_ratio_var.trace_add("write", lambda *args: self.ratio_label.config(text=f"{self.min_page_ratio_var.get():.2f}"))

        self.overwrite_warning_label = ttk.Label(
            scan_options_frame,
            text="Original input files will be overwritten irreversibly",
            foreground="red",
            font=("TkDefaultFont", 9, "bold")
        )

        action_frame = ttk.Frame(top_frame)
        action_frame.grid(row=5, column=0, columnspan=3, pady=(10, 0))
        self.scan_button = ttk.Button(action_frame, text="Scan Selected Files", command=self.start_scan)
        self.scan_button.pack(side="left", padx=5)
        self.remove_button = ttk.Button(action_frame, text="Run Watermark Removal", command=self.start_removal, state="disabled")
        self.remove_button.pack(side="left", padx=5)
        
        self.copy_skipped_checkbox = ttk.Checkbutton(action_frame, text="Copy unprocessed files", variable=self.copy_skipped_var)
        self.copy_skipped_checkbox.pack(side="left", padx=15, pady=(2,0))
        
        self.overwrite_checkbox = ttk.Checkbutton(action_frame, text="Overwrite existing files", variable=self.overwrite_var, command=self._check_overwrite_warning)
        self.overwrite_checkbox.pack(side="left", padx=5, pady=(2,0))

        self.suffix_var.trace_add("write", self._check_overwrite_warning)

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


    def add_files(self):
        """Opens a dialog to add multiple PDF files to the input list."""
        files = filedialog.askopenfilenames(title="Select PDF files", filetypes=[("PDF files", "*.pdf")])
        for file in files:
            if file not in self.input_files:
                self.input_files.append(file)
                self.file_listbox.insert("end", Path(file).name)
        self._check_overwrite_warning()

    def add_folder(self):
        """Opens a dialog to add all PDFs from a folder to the input list."""
        folder = filedialog.askdirectory(title="Select a folder containing PDFs")
        if folder:
            for file in sorted(Path(folder).glob("*.pdf")):
                file_str = str(file)
                if file_str not in self.input_files:
                    self.input_files.append(file_str)
                    self.file_listbox.insert("end", file.name)
        self._check_overwrite_warning()

    def remove_selected_files(self):
        """Removes the selected files from the input list."""
        selected_indices = self.file_listbox.curselection()
        if not selected_indices:
            return
        # Iterate backwards to avoid index shifting issues
        for index in reversed(selected_indices):
            self.input_files.pop(index)
            self.file_listbox.delete(index)
        self._check_overwrite_warning()

    def select_output_dir(self):
        """Opens a dialog to select the output directory."""
        directory = filedialog.askdirectory(title="Select a folder to save the results")
        if directory:
            self.output_dir = directory
            self.output_dir_entry.delete(0, "end")
            self.output_dir_entry.insert(0, self.output_dir)
            self._check_overwrite_warning()

    def start_scan(self):
        """Starts the watermark scanning process in a separate thread."""
        if not self.input_files:
            messagebox.showwarning("No Files", "Please add PDF files to scan first.")
            return

        self.clear_thumbnails()
        self.scan_button.config(state="disabled")
        self.remove_button.config(state="disabled")
        self.status_label.config(text="Scanning for watermark candidates...")
        self.progress_bar["value"] = 0
        self.percent_label.config(text="0%")

        min_page_ratio = self.min_page_ratio_var.get()
        threading.Thread(target=self.scan_worker, args=(min_page_ratio,), daemon=True).start()

    def start_removal(self):
        """Starts the watermark removal process in a separate thread."""
        xrefs_to_remove_by_file = defaultdict(list)
        for key, data in self.watermark_candidates.items():
            if data['var'].get():
                doc_path, xref = key
                xrefs_to_remove_by_file[doc_path].append(xref)
        
        if not self.output_dir or not Path(self.output_dir).is_dir():
            self.select_output_dir()
            if not self.output_dir: return
        
        if not xrefs_to_remove_by_file and not self.copy_skipped_var.get():
            messagebox.showwarning("No Action", "No watermarks selected to remove and 'Copy unprocessed files' is disabled.")
            return

        suffix = self.suffix_var.get()
        copy_skipped = self.copy_skipped_var.get()
        overwrite = self.overwrite_var.get()

        self.scan_button.config(state="disabled")
        self.remove_button.config(state="disabled")
        
        args = (
            self.input_files,
            xrefs_to_remove_by_file,
            suffix,
            copy_skipped,
            overwrite
        )
        threading.Thread(target=self.removal_worker, args=args, daemon=True).start()

    def process_queue(self):
        """Processes messages from the task queue to update the GUI."""
        try:
            while True:
                task_type, *payload = self.task_queue.get_nowait()
                
                if task_type == 'candidate_found':
                    self.add_thumbnail(*payload)
                elif task_type == 'scan_complete':
                    count = payload[0]
                    self.status_label.config(text=f"Scan complete. {count} watermark candidates found.")
                    self.scan_button.config(state="normal")
                    if count > 0 or self.copy_skipped_var.get():
                        self.remove_button.config(state="normal")
                elif task_type == 'removal_progress':
                    n, m = payload
                    msg = f"Processing files... ({n}/{m})"
                    self.status_label.config(text=msg)
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

    def scan_worker(self, min_page_ratio: float):
        """Worker function to scan files for watermarks."""
        candidates = self.core.scan_files_for_watermarks(self.input_files, min_page_ratio=min_page_ratio)
        for key, data in candidates.items():
            self.task_queue.put(('candidate_found', data['pil_img'], key))
        self.task_queue.put(('scan_complete', len(candidates)))

    def removal_worker(
        self,
        all_input_files: List[str],
        xrefs_by_file: Dict[str, List[int]],
        suffix: str,
        copy_skipped: bool,
        overwrite: bool
    ):
        """Worker function to remove watermarks and save/copy files."""
        total_files = len(all_input_files)
        for i, file_path in enumerate(all_input_files):
            self.task_queue.put(('removal_progress', i + 1, total_files))
            
            if file_path in xrefs_by_file:
                xrefs = xrefs_by_file[file_path]
                self.core.process_and_remove_watermarks(file_path, self.output_dir, xrefs, suffix, overwrite=overwrite)
            elif copy_skipped:
                self.core.copy_unprocessed_file(file_path, self.output_dir, overwrite=overwrite)

        self.task_queue.put(('removal_complete',))


    def clear_thumbnails(self):
        """Removes all watermark thumbnail widgets from the display."""
        for widget in self.thumbnail_frame.winfo_children():
            widget.destroy()
        self.watermark_candidates.clear()

    def add_thumbnail(self, pil_img: Image.Image, candidate_key: Tuple[str, int]):
        """Creates and displays a thumbnail for a watermark candidate.

        Args:
            pil_img: The PIL Image of the watermark candidate.
            candidate_key: A tuple containing the (doc_path, xref).
        """
        doc_path, xref = candidate_key
        
        thumbnail_size = (100, 100)
        img_copy = pil_img.copy()
        img_copy.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
        photo_img = ImageTk.PhotoImage(img_copy)

        item_frame = ttk.Frame(self.thumbnail_frame, padding=5, relief="groove", borderwidth=1)
        item_frame.pack(pady=5, padx=5, fill="x")

        var = tk.BooleanVar(value=True)
        chk = ttk.Checkbutton(item_frame, variable=var)
        chk.pack(side="left", padx=(0, 10))

        img_label = ttk.Label(item_frame, image=photo_img)
        img_label.pack(side="left")

        info_text = f"XRef: {xref}\nSource: {Path(doc_path).name}"
        info_label = ttk.Label(item_frame, text=info_text, justify="left")
        info_label.pack(side="left", padx=10)

        # Store the image object to prevent garbage collection
        self.watermark_candidates[candidate_key] = {'img_obj': photo_img, 'var': var}

    def log_message(self, text: str):
        """Appends a message to the log text box in a thread-safe way.

        Args:
            text: The message to be logged.
        """
        self.log_text.config(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.config(state="disabled")


if __name__ == "__main__":
    app = App()
    app.mainloop()
