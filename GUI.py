import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import threading
import queue

# Required libraries: PyMuPDF, Pillow
# pip install PyMuPDF pillow
try:
    from PIL import Image, ImageTk
except ImportError:
    messagebox.showerror(
        "Library Error",
        "Pillow library is required.\nPlease install it using the command: 'pip install pillow'"
    )
    exit()

# --- Import Core Logic Module ---
import core 

class App(tk.Tk):
    """Main class for the PDF Watermark Remover GUI application."""

    def __init__(self):
        super().__init__()
        self.title("PDF Watermark Remover")
        self.geometry("800x700")
        self.minsize(600, 500)

        # --- Data Management ---
        self.input_files = []
        self.output_dir = ""
        self.watermark_candidates = {}
        self.task_queue = queue.Queue()

        # --- UI Setup ---
        self._setup_ui()

        # --- Periodically check the task queue ---
        self.after(100, self.process_queue)

    def _setup_ui(self):
        """Sets up the UI widgets for the application."""
        # --- 1. Top Frame (Path Specification) ---
        top_frame = ttk.Frame(self, padding="10")
        top_frame.pack(fill="x", side="top")
        top_frame.columnconfigure(1, weight=1)

        ttk.Button(top_frame, text="Add Files", command=self.add_files).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(top_frame, text="Add Folder", command=self.add_folder).grid(row=1, column=0, padx=(0, 5))
        
        self.file_listbox = tk.Listbox(top_frame, height=4, selectmode="extended")
        self.file_listbox.grid(row=0, column=1, rowspan=2, sticky="ew")
        list_scroll = ttk.Scrollbar(top_frame, orient="vertical", command=self.file_listbox.yview)
        list_scroll.grid(row=0, column=2, rowspan=2, sticky="ns")
        self.file_listbox.config(yscrollcommand=list_scroll.set)

        ttk.Label(top_frame, text="Output Folder:").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.output_dir_entry = ttk.Entry(top_frame)
        self.output_dir_entry.grid(row=2, column=1, sticky="ew", pady=(10, 0))
        ttk.Button(top_frame, text="Browse", command=self.select_output_dir).grid(row=2, column=2, sticky="e", pady=(10, 0), padx=(5,0))

        action_frame = ttk.Frame(top_frame)
        action_frame.grid(row=3, column=0, columnspan=3, pady=(10, 0))
        self.scan_button = ttk.Button(action_frame, text="Scan Selected Files", command=self.start_scan)
        self.scan_button.pack(side="left", padx=5)
        self.remove_button = ttk.Button(action_frame, text="Remove Watermarks", command=self.start_removal, state="disabled")
        self.remove_button.pack(side="left", padx=5)

        # --- 3. Bottom Frame (Progress Status) ---
        bottom_frame = ttk.Frame(self, padding="10")
        bottom_frame.pack(fill="x", side="bottom")
        bottom_frame.columnconfigure(0, weight=1)

        self.status_label = ttk.Label(bottom_frame, text="Ready.")
        self.status_label.grid(row=0, column=0, columnspan=2, sticky="w")
        self.progress_bar = ttk.Progressbar(bottom_frame, orient="horizontal", mode="determinate")
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        self.percent_label = ttk.Label(bottom_frame, text="0%")
        self.percent_label.grid(row=1, column=1, sticky="w", padx=(5, 0), pady=(5, 0))

        # --- 2. Middle Frame (Thumbnails) ---
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

    # --- UI Event Handlers and Helpers ---
    def add_files(self):
        files = filedialog.askopenfilenames(title="Select PDF files", filetypes=[("PDF files", "*.pdf")])
        for file in files:
            if file not in self.input_files:
                self.input_files.append(file)
                self.file_listbox.insert("end", Path(file).name)

    def add_folder(self):
        folder = filedialog.askdirectory(title="Select a folder containing PDFs")
        if folder:
            for file in sorted(Path(folder).glob("*.pdf")):
                file_str = str(file)
                if file_str not in self.input_files:
                    self.input_files.append(file_str)
                    self.file_listbox.insert("end", file.name)

    def select_output_dir(self):
        directory = filedialog.askdirectory(title="Select a folder to save the results")
        if directory:
            self.output_dir = directory
            self.output_dir_entry.delete(0, "end")
            self.output_dir_entry.insert(0, self.output_dir)

    # --- Thread and Asynchronous Task Management ---
    def start_scan(self):
        if not self.input_files:
            messagebox.showwarning("No Files", "Please add PDF files to scan first.")
            return

        self.clear_thumbnails()
        self.scan_button.config(state="disabled")
        self.remove_button.config(state="disabled")
        self.status_label.config(text="Scanning for watermark candidates...")
        self.progress_bar["value"] = 0
        self.percent_label.config(text="0%")

        threading.Thread(target=self.scan_worker, daemon=True).start()

    def start_removal(self):
        selected_xrefs = [xref for xref, data in self.watermark_candidates.items() if data['var'].get()]
        if not selected_xrefs:
            messagebox.showwarning("No Selection", "Please select at least one watermark image to remove.")
            return
        if not self.output_dir or not Path(self.output_dir).is_dir():
            self.select_output_dir()
            if not self.output_dir: return

        self.scan_button.config(state="disabled")
        self.remove_button.config(state="disabled")
        threading.Thread(target=self.removal_worker, args=(selected_xrefs,), daemon=True).start()

    def process_queue(self):
        try:
            while True:
                task = self.task_queue.get_nowait()
                if task[0] == 'candidate_found':
                    self.add_thumbnail(*task[1:])
                elif task[0] == 'scan_complete':
                    self.status_label.config(text=f"Scan complete. {task[1]} watermark candidates found.")
                    self.scan_button.config(state="normal")
                    if task[1] > 0: self.remove_button.config(state="normal")
                elif task[0] == 'removal_progress':
                    _, n, m = task
                    msg = f"Processing files... ({n}/{m})"
                    self.status_label.config(text=msg)
                    progress = int((n / m) * 100)
                    self.progress_bar["value"] = progress
                    self.percent_label.config(text=f"{progress}%")
                elif task[0] == 'removal_complete':
                    self.status_label.config(text="Watermark removal complete!")
                    self.progress_bar["value"] = 100
                    self.percent_label.config(text="100%")
                    messagebox.showinfo("Complete", "All selected watermarks have been removed.")
                    self.scan_button.config(state="normal")
                    self.remove_button.config(state="normal")
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_queue)

    # --- Worker Thread Logic (Calling Core Module) ---
    def scan_worker(self):
        """[Refactored] Calls the core module to scan for watermark candidates."""
        # core.scan_files_for_watermarks returns a dictionary containing candidate information
        candidates = core.scan_files_for_watermarks(self.input_files, min_page_ratio=0.5)
        
        for xref, data in candidates.items():
            self.task_queue.put(('candidate_found', data['pil_img'], data['doc_path'], xref))
        
        self.task_queue.put(('scan_complete', len(candidates)))

    def removal_worker(self, xrefs_to_remove):
        """[Refactored] Calls the core module to remove watermarks."""
        total_files = len(self.input_files)
        # Keep the logic for putting progress updates in the queue for the GUI
        for i, file_path in enumerate(self.input_files):
            self.task_queue.put(('removal_progress', i + 1, total_files))
            # Delegate the actual file processing logic to the core module
            core.process_and_remove_watermarks([file_path], self.output_dir, xrefs_to_remove)
        
        self.task_queue.put(('removal_complete',))

    # --- Thumbnail UI Helper ---
    def clear_thumbnails(self):
        for widget in self.thumbnail_frame.winfo_children():
            widget.destroy()
        self.watermark_candidates.clear()

    def add_thumbnail(self, pil_img, doc_path, xref):
        thumbnail_size = (100, 100)
        pil_img.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
        photo_img = ImageTk.PhotoImage(pil_img)

        item_frame = ttk.Frame(self.thumbnail_frame, padding=5, relief="groove", borderwidth=1)
        item_frame.pack(pady=5, padx=5, fill="x")

        var = tk.BooleanVar(value=True)
        chk = ttk.Checkbutton(item_frame, variable=var)
        chk.pack(side="left", padx=(0, 10))

        img_label = ttk.Label(item_frame, image=photo_img)
        img_label.pack(side="left")

        info_text = f"XRef: {xref}\nSize: {pil_img.width}x{pil_img.height}\nSource: {Path(doc_path).name}"
        info_label = ttk.Label(item_frame, text=info_text, justify="left")
        info_label.pack(side="left", padx=10)

        self.watermark_candidates[xref] = {'img_obj': photo_img, 'var': var}


if __name__ == "__main__":
    app = App()
    app.mainloop()