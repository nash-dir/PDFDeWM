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


"""Main GUI application for PDFDeWM.

Provides a Tkinter-based interface for scanning and removing
watermarks from PDF files, with support for drag-and-drop,
cancellable operations, text watermark grouping, and persistent
user preferences.
"""


import json
import logging
import os
import sys
import threading
import time
import tkinter as tk
from collections import defaultdict
from pathlib import Path
from tkinter import ttk, messagebox
from typing import List, Dict, Any, Tuple

import queue

import fitz

try:
    from PIL import Image, ImageTk, ImageDraw
except ImportError:
    Image = None
    ImageTk = None
    ImageDraw = None

# Optional modern theme
try:
    import sv_ttk
    HAS_SV_TTK = True
except ImportError:
    HAS_SV_TTK = False

from utils import FileManager, ThumbnailManager, ConfigManager
import core

logger = logging.getLogger("pdfdewm.gui")


# ── DPI Awareness (Windows) ────────────────────────────────────

def _enable_dpi_awareness():
    """Enable per-monitor DPI awareness on Windows 10+."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass


# ── Tooltip ─────────────────────────────────────────────────────

class ToolTip:
    """Simple tooltip for Tkinter widgets."""

    def __init__(self, widget, text: str, delay: int = 500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._tip_window = None
        self._after_id = None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)

    def _schedule(self, event=None):
        self._after_id = self.widget.after(self.delay, self._show)

    def _show(self):
        if self._tip_window:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self._tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw, text=self.text, justify="left",
            background="#ffffe0", relief="solid", borderwidth=1,
            font=("TkDefaultFont", 9)
        )
        label.pack()

    def _hide(self, event=None):
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None
        if self._tip_window:
            self._tip_window.destroy()
            self._tip_window = None


# ── Queue Logger ────────────────────────────────────────────────

class QueueLogger:
    """Thread-safe logger that redirects stdout/stderr to a queue."""

    def __init__(self, q: queue.Queue):
        self.queue = q
        self.buffer = ""
        self._lock = threading.Lock()

    def write(self, text: str):
        with self._lock:
            self.buffer += text
            if '\n' in self.buffer:
                lines = self.buffer.split('\n')
                for line in lines[:-1]:
                    self.queue.put(('log', line + '\n'))
                self.buffer = lines[-1]

    def flush(self):
        with self._lock:
            if self.buffer:
                self.queue.put(('log', self.buffer + '\n'))
                self.buffer = ""


# ── Main Application ───────────────────────────────────────────

class App(tk.Tk):
    """Main application window for PDFDeWM."""

    def __init__(self):
        super().__init__()

        self.core = core
        self.file_manager = FileManager()
        self.thumbnail_manager = ThumbnailManager()
        self.config = ConfigManager()

        self.title("PDF Watermark Remover")
        self.minsize(600, 600)

        # Restore window geometry
        saved_geo = self.config.get("window_geometry")
        if saved_geo:
            self.geometry(saved_geo)
        else:
            self.geometry("850x900")

        self.input_files: List[str] = []
        self.output_dir: str = self.config.recent_output_dir or ""

        # Candidate storage:
        #   raw_candidates: original per-page/per-xref candidates from scan
        #   display_groups: grouped entries shown in the UI
        self.raw_candidates: Dict[Tuple, Dict[str, Any]] = {}
        self.display_groups: List[Dict[str, Any]] = []

        self.task_queue: queue.Queue = queue.Queue()
        self._cancel_event = threading.Event()
        self._scan_start_time: float = 0

        self.suffix_var = tk.StringVar(value=self.config.last_suffix)
        self.copy_skipped_var = tk.BooleanVar(value=False)
        self.overwrite_var = tk.BooleanVar(value=False)
        self.text_keywords_var = tk.StringVar()
        self.scan_threshold_var = tk.IntVar(value=self.config.last_threshold)
        self.sanitize_var = tk.BooleanVar(value=False)
        self.clean_metadata_var = tk.BooleanVar(value=False)

        self._preview_photo = None  # Keep reference to prevent GC

        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.queue_logger = QueueLogger(self.task_queue)

        self._setup_ui()
        self._apply_theme()
        self.redirect_logging()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.after(100, self.process_queue)
        self._bind_hotkeys()
        self._setup_drag_and_drop()
        self._update_empty_state()

        if self.output_dir:
            self.output_dir_entry.delete(0, "end")
            self.output_dir_entry.insert(0, self.output_dir)
            self.open_folder_button.config(state="normal")

    # ─── Theme ───────────────────────────────────────────────────

    def _apply_theme(self):
        """Apply sv_ttk theme if available."""
        if HAS_SV_TTK:
            saved_theme = self.config.get("theme", "light")
            sv_ttk.set_theme(saved_theme)
            
            # Explicitly force Malgun Gothic on ALL fonts to fix Korean character rendering
            import tkinter.font as tkfont
            for font_name in tkfont.names():
                try:
                    f = tkfont.nametofont(font_name)
                    # Consolas for fixed width, Malgun Gothic for everything else
                    if "fixed" in font_name.lower():
                        f.configure(family="Consolas")
                    else:
                        f.configure(family="Malgun Gothic")
                except Exception:
                    pass
            
            style = ttk.Style()
            style.configure('.', font=("Malgun Gothic", 10))
            style.configure('Treeview', font=("Malgun Gothic", 10))
        else:
            try:
                self.tk.call("source", "")
            except tk.TclError:
                pass

    def _toggle_theme(self):
        """Toggle between light and dark theme."""
        if HAS_SV_TTK:
            current = sv_ttk.get_theme()
            new_theme = "dark" if current == "light" else "light"
            sv_ttk.set_theme(new_theme)
            self.config.set("theme", new_theme)

    # ─── Hotkeys ─────────────────────────────────────────────────

    def _bind_hotkeys(self):
        """Bind keyboard shortcuts for all main actions."""
        self.bind_all("<Control-a>", self.add_files)
        self.bind_all("<Control-Shift-A>", self.add_folder)
        self.bind_all("<Control-s>", self.select_output_dir)
        self.bind_all("<Control-d>", self.start_scan)
        self.bind_all("<Control-f>", self.start_removal)
        self.bind_all("<Control-t>", self.on_closing)
        self.bind_all("<Control-q>", lambda e: self._focus_and_select(self.suffix_entry))
        self.bind_all("<Control-w>", lambda e: self._focus_and_select(self.text_keyword_entry))
        self.bind_all("<Control-Shift-S>", self.select_output_dir)
        self.bind_all("<Control-Shift-D>", self.start_scan)
        self.bind_all("<Control-Shift-F>", self.start_removal)
        self.bind_all("<Control-Shift-T>", self.on_closing)
        self.bind_all("<Control-Shift-Q>", lambda e: self._focus_and_select(self.suffix_entry))
        self.bind_all("<Control-Shift-W>", lambda e: self._focus_and_select(self.text_keyword_entry))

    def _focus_and_select(self, entry_widget):
        entry_widget.focus_set()
        entry_widget.selection_range(0, tk.END)

    # ─── Drag & Drop ────────────────────────────────────────────

    def _setup_drag_and_drop(self):
        """Configure drag-and-drop support."""
        try:
            from tkinterdnd2 import DND_FILES
            self.file_listbox.drop_target_register(DND_FILES)
            self.file_listbox.dnd_bind('<<Drop>>', self._on_drop)
        except (ImportError, Exception):
            pass

    def _on_drop(self, event):
        raw = event.data
        files = []
        if raw.startswith('{'):
            import re
            files = re.findall(r'\{(.+?)\}', raw)
        else:
            files = raw.split()

        for f in files:
            f = f.strip()
            p = Path(f)
            if p.is_file() and p.suffix.lower() == '.pdf':
                fstr = str(p)
                if fstr not in self.input_files:
                    self.input_files.append(fstr)
                    self.file_listbox.insert("end", p.name)
            elif p.is_dir():
                for pdf in sorted(p.rglob("*.pdf")):
                    fstr = str(pdf)
                    if fstr not in self.input_files:
                        self.input_files.append(fstr)
                        self.file_listbox.insert("end", pdf.name)
        self._update_file_count()
        self._update_empty_state()
        self._check_overwrite_warning()

    # ─── Logging / Lifecycle ────────────────────────────────────

    def redirect_logging(self):
        sys.stdout = self.queue_logger
        sys.stderr = self.queue_logger

    def restore_logging(self):
        if hasattr(sys.stdout, 'flush'):
            sys.stdout.flush()
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr

    def on_closing(self, event=None):
        self.config.last_suffix = self.suffix_var.get()
        self.config.last_threshold = self.scan_threshold_var.get()
        if self.output_dir:
            self.config.recent_output_dir = self.output_dir
        self.config.set("window_geometry", self.geometry())
        self._cancel_event.set()
        self.restore_logging()
        self.destroy()

    # ─── Empty State ────────────────────────────────────────────

    def _update_empty_state(self):
        """Show/hide the empty state placeholder in the file listbox."""
        if not self.input_files:
            self.file_listbox.config(foreground="gray")
            if self.file_listbox.size() == 0:
                self.file_listbox.insert("end", "  PDF 파일을 여기에 드래그하거나")
                self.file_listbox.insert("end", "  [파일 추가(Ctrl+A)]를 클릭하세요")
        else:
            self.file_listbox.config(foreground="")

    def _clear_empty_state(self):
        """Remove the empty state placeholder if present."""
        if not self.input_files and self.file_listbox.size() > 0:
            self.file_listbox.delete(0, "end")

    # ─── UI Setup ───────────────────────────────────────────────

    def _setup_ui(self):
        """Build the complete application UI."""
        # === Top Frame: File selection, output settings ===
        top_frame = ttk.Frame(self, padding="10")
        top_frame.pack(fill="x", side="top", pady=(0, 5))
        top_frame.columnconfigure(1, weight=1)

        file_button_frame = ttk.Frame(top_frame)
        file_button_frame.grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, 5))

        btn_add_files = ttk.Button(file_button_frame, text="파일 추가(Ctrl+A)", command=self.add_files)
        btn_add_files.pack(fill="x", pady=2)
        ToolTip(btn_add_files, "PDF 파일을 선택하여 추가합니다")

        btn_add_folder = ttk.Button(file_button_frame, text="폴더 추가(Ctrl+⇧A)", command=self.add_folder)
        btn_add_folder.pack(fill="x", pady=2)
        ToolTip(btn_add_folder, "폴더 내 모든 PDF를 재귀적으로 추가합니다")

        btn_remove = ttk.Button(file_button_frame, text="선택 제거(Del)", command=self.remove_selected_files)
        btn_remove.pack(fill="x", pady=2)

        # Theme toggle (only if sv_ttk available)
        if HAS_SV_TTK:
            btn_theme = ttk.Button(file_button_frame, text="🌙 테마", command=self._toggle_theme)
            btn_theme.pack(fill="x", pady=(10, 2))
            ToolTip(btn_theme, "라이트/다크 모드를 전환합니다")

        self.file_listbox = tk.Listbox(top_frame, height=5, selectmode="extended", font=("Malgun Gothic", 10))
        self.file_listbox.grid(row=0, column=1, rowspan=2, sticky="ew")
        list_scroll = ttk.Scrollbar(top_frame, orient="vertical", command=self.file_listbox.yview)
        list_scroll.grid(row=0, column=2, rowspan=2, sticky="ns")
        self.file_listbox.config(yscrollcommand=list_scroll.set)

        self.file_listbox.bind("<Double-1>", self.open_selected_file)
        self.file_listbox.bind("<Return>", self.open_selected_file)
        self.file_listbox.bind("<Delete>", self.remove_selected_files)
        self.file_listbox.bind("<BackSpace>", self.remove_selected_files)

        # File count label
        self.file_count_label = ttk.Label(top_frame, text="", foreground="gray")
        self.file_count_label.grid(row=2, column=1, sticky="w", pady=(2, 0))

        ttk.Label(top_frame, text="출력 폴더:").grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.output_dir_entry = ttk.Entry(top_frame)
        self.output_dir_entry.grid(row=3, column=1, sticky="ew", pady=(10, 0))
        btn_browse = ttk.Button(top_frame, text="찾아보기(Ctrl+S)", command=self.select_output_dir)
        btn_browse.grid(row=3, column=2, sticky="e", pady=(10, 0), padx=(5, 0))

        ttk.Label(top_frame, text="출력 접미사(Ctrl+Q):").grid(row=4, column=0, sticky="w", pady=(5, 0))
        self.suffix_entry = ttk.Entry(top_frame, textvariable=self.suffix_var)
        self.suffix_entry.grid(row=4, column=1, sticky="ew", pady=(5, 0))

        # === Options ===
        options_container = ttk.Frame(top_frame)
        options_container.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        options_container.columnconfigure(1, weight=1)

        scan_options_frame = ttk.Frame(options_container)
        scan_options_frame.grid(row=0, column=0, columnspan=2, pady=(0, 5), sticky="ew")

        ttk.Label(scan_options_frame, text="이미지 스캔 임계값(%):").pack(side="left", padx=(0, 5))
        self.threshold_spinbox = ttk.Spinbox(
            scan_options_frame, from_=1, to=100, increment=1,
            textvariable=self.scan_threshold_var, width=5
        )
        self.threshold_spinbox.pack(side="left")
        ToolTip(self.threshold_spinbox, "이미지가 전체 페이지의 N% 이상에 나타나면 워터마크로 판별합니다")

        ttk.Label(options_container, text="텍스트 키워드(Ctrl+W, ';'로 구분):").grid(
            row=1, column=0, sticky="w", pady=(5, 0)
        )
        self.text_keyword_entry = ttk.Entry(options_container, textvariable=self.text_keywords_var)
        self.text_keyword_entry.grid(row=1, column=1, sticky="ew", pady=(5, 0))
        ToolTip(self.text_keyword_entry, "세미콜론으로 구분된 키워드를 입력하세요. 예: DRAFT;대외비;CONFIDENTIAL")

        self.overwrite_warning_label = ttk.Label(
            options_container, text="⚠️ 원본 입력 파일이 비가역적으로 덮어쓰기됩니다",
            foreground="red", font=("TkDefaultFont", 9, "bold")
        )
        self.overwrite_warning_label.grid(row=2, column=1, sticky="w", padx=0, pady=(2, 0))
        self.overwrite_warning_label.grid_remove()

        # === Action buttons ===
        action_frame = ttk.Frame(top_frame)
        action_frame.grid(row=6, column=0, columnspan=3, pady=(10, 0), sticky="ew")

        left_action_frame = ttk.Frame(action_frame)
        left_action_frame.pack(side="left")

        self.scan_button = ttk.Button(
            left_action_frame, text="스캔(Ctrl+D)", command=self.start_scan
        )
        self.scan_button.pack(side="left", padx=(0, 2))

        self.remove_button = ttk.Button(
            left_action_frame, text="워터마크 제거(Ctrl+F)",
            command=self.start_removal, state="disabled"
        )
        self.remove_button.pack(side="left", padx=2)

        self.cancel_button = ttk.Button(
            left_action_frame, text="취소", command=self._cancel_task, state="disabled"
        )
        self.cancel_button.pack(side="left", padx=2)

        self.copy_skipped_checkbox = ttk.Checkbutton(
            left_action_frame, text="미처리 파일 복사", variable=self.copy_skipped_var
        )
        self.copy_skipped_checkbox.pack(side="left", padx=7)

        self.overwrite_checkbox = ttk.Checkbutton(
            left_action_frame, text="기존 파일 덮어쓰기",
            variable=self.overwrite_var, command=self._check_overwrite_warning
        )
        self.overwrite_checkbox.pack(side="left", padx=7)

        right_action_frame = ttk.Frame(action_frame)
        right_action_frame.pack(side="right")

        self.metadata_checkbox = ttk.Checkbutton(
            right_action_frame, text="메타데이터 정리", variable=self.clean_metadata_var
        )
        self.metadata_checkbox.pack(side="right", padx=(0, 5))
        ToolTip(self.metadata_checkbox, "Author, Creator, Producer 등 민감한 메타데이터를 제거합니다")

        self.sanitize_checkbox = ttk.Checkbutton(
            right_action_frame, text="숨은 텍스트 제거", variable=self.sanitize_var
        )
        self.sanitize_checkbox.pack(side="right")
        ToolTip(self.sanitize_checkbox, "PDF에 포함된 보이지 않는 텍스트를 제거합니다 (포렌식/보안용)")

        self.suffix_var.trace_add("write", self._check_overwrite_warning)

        # === Bottom Frame: Progress and Logs ===
        bottom_frame = ttk.Frame(self, padding="10")
        bottom_frame.pack(fill="x", side="bottom")
        bottom_frame.columnconfigure(0, weight=1)

        open_folder_frame = ttk.Frame(bottom_frame)
        open_folder_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.open_folder_button = ttk.Button(
            open_folder_frame, text="출력 폴더 열기",
            command=self._open_output_folder, state="disabled"
        )
        self.open_folder_button.pack(side="right")

        progress_frame = ttk.Frame(bottom_frame)
        progress_frame.grid(row=1, column=0, sticky="ew")
        progress_frame.columnconfigure(0, weight=1)

        self.status_label = ttk.Label(progress_frame, text="준비됨.")
        self.status_label.grid(row=0, column=0, columnspan=2, sticky="w")
        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate")
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        self.percent_label = ttk.Label(progress_frame, text="0%")
        self.percent_label.grid(row=1, column=1, sticky="w", padx=(5, 0), pady=(5, 0))

        log_frame = ttk.Labelframe(bottom_frame, text="로그", padding=5)
        log_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, height=6, state="disabled", wrap="word", background="#f0f0f0", font=("Malgun Gothic", 9))
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.config(yscrollcommand=log_scroll.set)

        # === Middle Frame: PanedWindow — Candidates (left) + Preview (right) ===
        mid_frame = ttk.Frame(self, padding=(10, 0, 10, 10))
        mid_frame.pack(fill="both", expand=True)

        # Select All / Deselect All bar
        select_bar = ttk.Frame(mid_frame)
        select_bar.pack(fill="x", pady=(0, 5))

        self.candidate_count_label = ttk.Label(select_bar, text="", foreground="gray")
        self.candidate_count_label.pack(side="left")

        btn_invert = ttk.Button(select_bar, text="선택 반전", command=self._invert_selection)
        btn_invert.pack(side="right", padx=2)
        btn_deselect = ttk.Button(select_bar, text="전체 해제", command=self._deselect_all)
        btn_deselect.pack(side="right", padx=2)
        btn_select = ttk.Button(select_bar, text="전체 선택", command=self._select_all)
        btn_select.pack(side="right", padx=2)

        paned = ttk.PanedWindow(mid_frame, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # Left: Candidate list (scrollable canvas)
        left_pane = ttk.Frame(paned)
        paned.add(left_pane, weight=3)

        self.canvas = tk.Canvas(left_pane, borderwidth=0, background="#ffffff")
        self.thumbnail_frame = ttk.Frame(self.canvas, padding=5)
        self.scrollbar = ttk.Scrollbar(left_pane, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas_window = self.canvas.create_window((4, 4), window=self.thumbnail_frame, anchor="nw")
        self.thumbnail_frame.bind(
            "<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind(
            "<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width - 8)
        )

        # Right: Preview panel
        right_pane = ttk.Labelframe(paned, text="미리보기", padding=5)
        paned.add(right_pane, weight=2)

        self.preview_label = ttk.Label(
            right_pane, text="후보를 클릭하면\n해당 페이지를 표시합니다",
            anchor="center", justify="center", foreground="gray"
        )
        self.preview_label.pack(fill="both", expand=True)
        self.preview_canvas = tk.Canvas(right_pane, background="#f8f8f8")
        # preview_canvas is shown only when a preview is active

    # ─── Overwrite Warning ──────────────────────────────────────

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

    # ─── File Management ────────────────────────────────────────

    def _update_file_count(self):
        """Update the file count label."""
        count = len(self.input_files)
        self.file_count_label.config(
            text=f"{count}개 파일 로드됨" if count > 0 else ""
        )

    def add_files(self, event=None):
        self._clear_empty_state()
        new_files = self.file_manager.ask_for_files()
        for file in new_files:
            if file not in self.input_files:
                self.input_files.append(file)
                self.file_listbox.insert("end", Path(file).name)
        if new_files:
            self.config.recent_input_dir = str(Path(new_files[0]).parent)
        self._update_file_count()
        self._update_empty_state()
        self._check_overwrite_warning()

    def add_folder(self, event=None):
        self._clear_empty_state()
        folder = self.file_manager.ask_for_folder()
        if folder:
            for file in sorted(Path(folder).rglob("*.pdf")):
                file_str = str(file)
                if file_str not in self.input_files:
                    self.input_files.append(file_str)
                    display_name = file.relative_to(folder)
                    self.file_listbox.insert("end", display_name)
            self.config.recent_input_dir = folder
        self._update_file_count()
        self._update_empty_state()
        self._check_overwrite_warning()

    def remove_selected_files(self, event=None):
        selected_indices = self.file_listbox.curselection()
        if not selected_indices:
            return

        files_to_remove = [self.input_files[i] for i in selected_indices]
        target_index = selected_indices[0]

        for index in reversed(selected_indices):
            self.input_files.pop(index)
            self.file_listbox.delete(index)

        # Remove matching candidates
        keys_to_delete = [
            key for key in self.raw_candidates
            if key[1] in files_to_remove
        ]
        for key in keys_to_delete:
            del self.raw_candidates[key]

        self._rebuild_display_groups()

        current_list_size = self.file_listbox.size()
        if current_list_size > 0:
            final_index = min(target_index, current_list_size - 1)
            self.file_listbox.selection_clear(0, tk.END)
            self.file_listbox.selection_set(final_index)
            self.file_listbox.activate(final_index)
            self.file_listbox.see(final_index)

        self._update_file_count()
        self._update_empty_state()
        self._check_overwrite_warning()

    def open_selected_file(self, event=None):
        selected_indices = self.file_listbox.curselection()
        if not selected_indices:
            return
        index = selected_indices[0]
        if index >= len(self.input_files):
            return  # Empty state placeholder
        file_path = self.input_files[index]
        try:
            if sys.platform == "win32":
                os.startfile(file_path)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.call(('open', file_path))
            else:
                import subprocess
                subprocess.call(('xdg-open', file_path))
        except Exception as e:
            messagebox.showerror("오류", f"파일을 열 수 없습니다:\n{file_path}\n{e}")

    def select_output_dir(self, event=None):
        directory = self.file_manager.ask_for_output_dir()
        if directory:
            self.output_dir = directory
            self.output_dir_entry.delete(0, "end")
            self.output_dir_entry.insert(0, self.output_dir)
            self.config.recent_output_dir = directory
            self.open_folder_button.config(state="normal")
            self._check_overwrite_warning()

    def _open_output_folder(self):
        if not self.output_dir or not Path(self.output_dir).is_dir():
            messagebox.showwarning("없음", "출력 폴더가 설정되지 않았거나 존재하지 않습니다.")
            return
        try:
            if sys.platform == "win32":
                os.startfile(self.output_dir)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.call(('open', self.output_dir))
            else:
                import subprocess
                subprocess.call(('xdg-open', self.output_dir))
        except Exception as e:
            messagebox.showerror("오류", f"폴더를 열 수 없습니다:\n{e}")

    # ─── Select All / Deselect All / Invert ─────────────────────

    def _select_all(self):
        for group in self.display_groups:
            group['var'].set(True)

    def _deselect_all(self):
        for group in self.display_groups:
            group['var'].set(False)

    def _invert_selection(self):
        for group in self.display_groups:
            group['var'].set(not group['var'].get())

    # ─── Cancel ─────────────────────────────────────────────────

    def _cancel_task(self):
        self._cancel_event.set()
        self.status_label.config(text="취소 중...")
        self.cancel_button.config(state="disabled")

    def _set_buttons_running(self):
        self.scan_button.config(state="disabled")
        self.remove_button.config(state="disabled")
        self.cancel_button.config(state="normal")

    def _set_buttons_idle(self):
        self.scan_button.config(state="normal")
        self.remove_button.config(state="normal")
        self.cancel_button.config(state="disabled")

    # ─── Scan ───────────────────────────────────────────────────

    def start_scan(self, event=None):
        if self.scan_button['state'] == 'disabled' and event is not None:
            return
        if not self.input_files:
            messagebox.showwarning("파일 없음", "먼저 PDF 파일을 추가해 주세요.")
            return

        self.clear_thumbnails()
        self._cancel_event.clear()
        self._set_buttons_running()
        self._scan_start_time = time.time()
        self.status_label.config(text="워터마크 후보 스캔 중...")
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

        # Build removal dict from display groups
        candidates_to_remove = defaultdict(lambda: defaultdict(list))
        selected_count = 0

        for group in self.display_groups:
            if not group['var'].get():
                continue
            selected_count += 1
            for member_key in group['member_keys']:
                ctype, fpath = member_key[0], member_key[1]
                member_data = self.raw_candidates[member_key]
                if ctype == 'image':
                    xref = member_data['xref']
                    if xref not in candidates_to_remove[fpath]['image']:
                        candidates_to_remove[fpath]['image'].append(xref)
                elif ctype == 'text':
                    page_num = member_data['page']
                    bbox = member_data['bbox']
                    text_info = {'page': page_num, 'bbox': bbox}
                    candidates_to_remove[fpath]['text'].append(text_info)

        if not self.output_dir or not Path(self.output_dir).is_dir():
            self.select_output_dir()
            if not self.output_dir:
                return

        sanitize = self.sanitize_var.get()
        clean_metadata = self.clean_metadata_var.get()
        if not candidates_to_remove and not self.copy_skipped_var.get() and not sanitize and not clean_metadata:
            messagebox.showwarning(
                "조치 없음",
                "제거할 워터마크가 선택되지 않았고, '미처리 파일 복사'가 비활성이며, "
                "'숨은 텍스트 제거'와 '메타데이터 정리'도 꺼져 있습니다."
            )
            return

        suffix = self.suffix_var.get()
        copy_skipped = self.copy_skipped_var.get()
        overwrite = self.overwrite_var.get()

        self._cancel_event.clear()
        self._set_buttons_running()
        self._scan_start_time = time.time()

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
            copy_skipped, overwrite, sanitize, clean_metadata,
            input_root, selected_count
        )
        threading.Thread(target=self.removal_worker, args=args, daemon=True).start()

    # ─── Queue Processing ───────────────────────────────────────

    def process_queue(self):
        try:
            while True:
                task_type, *payload = self.task_queue.get_nowait()

                if task_type == 'scan_complete':
                    candidates = payload[0]
                    self.raw_candidates = candidates
                    self._rebuild_display_groups()
                    elapsed = time.time() - self._scan_start_time
                    count = len(self.display_groups)
                    self.status_label.config(
                        text=f"스캔 완료. {count}개 후보 발견. ({elapsed:.1f}초)"
                    )
                    self.progress_bar["value"] = 100
                    self.percent_label.config(text="100%")
                    self._set_buttons_idle()
                elif task_type == 'scan_progress':
                    current, total = payload
                    progress = int((current / total) * 100) if total > 0 else 0
                    self.progress_bar["value"] = progress
                    self.percent_label.config(text=f"{progress}%")
                    self.status_label.config(text=f"스캔 중... ({current}/{total} 파일)")
                elif task_type == 'scan_cancelled':
                    self.status_label.config(text="스캔이 취소되었습니다.")
                    self._set_buttons_idle()
                elif task_type == 'scan_error':
                    self.status_label.config(text=f"스캔 실패: {payload[0]}")
                    self._set_buttons_idle()
                elif task_type == 'removal_progress':
                    n, m = payload
                    self.status_label.config(text=f"파일 처리 중... ({n}/{m})")
                    progress = int((n / m) * 100)
                    self.progress_bar["value"] = progress
                    self.percent_label.config(text=f"{progress}%")
                elif task_type == 'removal_complete':
                    processed, copied, skipped, failed, selected_count = payload
                    elapsed = time.time() - self._scan_start_time
                    self.status_label.config(text="워터마크 제거 완료!")
                    self.progress_bar["value"] = 100
                    self.percent_label.config(text="100%")
                    self.open_folder_button.config(state="normal")
                    self._show_completion_summary(processed, copied, skipped, failed, selected_count, elapsed)
                    self._set_buttons_idle()
                    self.remove_button.config(state="disabled")
                elif task_type == 'removal_cancelled':
                    self.status_label.config(text="제거가 취소되었습니다.")
                    self._set_buttons_idle()
                elif task_type == 'removal_error':
                    self.status_label.config(text=f"제거 실패: {payload[0]}")
                    self._set_buttons_idle()
                elif task_type == 'log':
                    self.log_message(payload[0])
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_queue)

    # ─── Completion Summary ─────────────────────────────────────

    def _show_completion_summary(
        self, processed: int, copied: int, skipped: int,
        failed: int, selected_count: int, elapsed: float
    ):
        """Show a detailed completion summary dialog."""
        lines = []
        lines.append(f"처리 완료")
        lines.append(f"")
        lines.append(f"제거 대상:  {selected_count}개 워터마크 그룹")
        lines.append(f"처리됨:     {processed}개 파일")
        if copied > 0:
            lines.append(f"복사됨:     {copied}개 파일 (워터마크 없음)")
        if skipped > 0:
            lines.append(f"건너뜀:     {skipped}개 파일")
        if failed > 0:
            lines.append(f"⚠️ 실패:    {failed}개 파일 (로그 참조)")
        lines.append(f"소요 시간:  {elapsed:.1f}초")
        if failed > 0:
            messagebox.showwarning("처리 완료 (일부 실패)", "\n".join(lines))
        else:
            messagebox.showinfo("처리 완료", "\n".join(lines))

    # ─── Worker Threads ─────────────────────────────────────────

    def scan_worker(self, min_page_ratio: float, text_keywords: List[str]):
        try:
            candidates = self.core.scan_files_for_watermarks(
                self.input_files,
                min_page_ratio=min_page_ratio,
                text_keywords=text_keywords,
                cancel_flag=self._cancel_event,
            )

            if self._cancel_event.is_set():
                self.task_queue.put(('scan_cancelled',))
                return

            self.task_queue.put(('scan_complete', candidates))

        except Exception as e:
            logger.error(f"Scan worker error: {e}")
            self.task_queue.put(('scan_error', str(e)))

    def removal_worker(
        self, all_input_files: List[str],
        candidates_by_file: Dict[str, Dict[str, List]],
        suffix: str, copy_skipped: bool, overwrite: bool,
        sanitize: bool, clean_metadata: bool,
        input_root: str, selected_count: int
    ):
        total_files = len(all_input_files)
        processed = 0
        copied = 0
        skipped = 0
        failed = 0

        for i, file_path in enumerate(all_input_files):
            if self._cancel_event.is_set():
                self.task_queue.put(('removal_cancelled',))
                return

            self.task_queue.put(('removal_progress', i + 1, total_files))

            try:
                should_process = (
                    file_path in candidates_by_file
                    or sanitize
                    or clean_metadata
                )

                if should_process:
                    to_remove = candidates_by_file.get(file_path, {})
                    self.core.process_and_remove_watermarks(
                        file_path, self.output_dir, to_remove, suffix,
                        overwrite=overwrite,
                        sanitize_hidden_text=sanitize,
                        clean_metadata=clean_metadata,
                        input_dir_root=input_root,
                    )
                    processed += 1
                elif copy_skipped:
                    self.core.copy_unprocessed_file(
                        file_path, self.output_dir,
                        overwrite=overwrite, input_dir_root=input_root
                    )
                    copied += 1
                else:
                    skipped += 1

            except Exception as e:
                failed += 1
                fname = Path(file_path).name
                logger.error(f"Failed to process {fname}: {e}")
                print(f"[ERROR] {fname}: {e}")

        self.task_queue.put(('removal_complete', processed, copied, skipped, failed, selected_count))

    # ─── Candidate Grouping & Display ───────────────────────────

    def clear_thumbnails(self):
        for widget in self.thumbnail_frame.winfo_children():
            widget.destroy()
        self.raw_candidates.clear()
        self.display_groups.clear()
        self.candidate_count_label.config(text="")

    def _rebuild_display_groups(self):
        """Group raw candidates into display groups and rebuild the UI.

        Image candidates: one group per unique xref (already unique).
        Text candidates:  grouped by (file_path, text_content) so that
                          "DRAFT" appearing on 500 pages = 1 checkbox.
        """
        for widget in self.thumbnail_frame.winfo_children():
            widget.destroy()
        self.display_groups.clear()

        # Separate image and text candidates
        image_candidates = {}
        text_groups: Dict[Tuple[str, str], List[Tuple]] = defaultdict(list)

        for key, data in self.raw_candidates.items():
            ctype = key[0]
            if ctype == 'image':
                # Image: group by (file, xref)
                group_key = ('image', key[1], data['xref'])
                if group_key not in image_candidates:
                    image_candidates[group_key] = {
                        'member_keys': [key],
                        'data': data,
                    }
                else:
                    image_candidates[group_key]['member_keys'].append(key)
            elif ctype == 'text':
                text_content = data.get('text', '')
                file_path = key[1]
                group_key = (file_path, text_content)
                text_groups[group_key].append(key)

        # Build image display groups
        for gk, gdata in image_candidates.items():
            data = gdata['data']
            var = tk.BooleanVar(value=True)
            group = {
                'type': 'image',
                'var': var,
                'member_keys': gdata['member_keys'],
                'pil_img': data.get('pil_img'),
                'xref': data.get('xref'),
                'source': data.get('source', ''),
            }
            self.display_groups.append(group)

        # Build text display groups (GROUPED)
        for (file_path, text_content), member_keys in text_groups.items():
            var = tk.BooleanVar(value=True)
            pages = sorted(set(
                self.raw_candidates[k].get('page', 0) for k in member_keys
            ))
            group = {
                'type': 'text',
                'var': var,
                'member_keys': list(member_keys),
                'text': text_content,
                'pages': pages,
                'page_count': len(pages),
                'source': Path(file_path).name,
            }
            self.display_groups.append(group)

        # Render
        for group in self.display_groups:
            self._render_group(group)

        # Update count label
        total = len(self.display_groups)
        text_total = sum(1 for g in self.display_groups if g['type'] == 'text')
        image_total = total - text_total
        parts = []
        if image_total:
            parts.append(f"이미지 {image_total}개")
        if text_total:
            parts.append(f"텍스트 {text_total}개")
        self.candidate_count_label.config(
            text=f"후보 {total}개 ({', '.join(parts)})" if total > 0 else ""
        )

    def _render_group(self, group: Dict[str, Any]):
        """Render a single display group as a frame with checkbox + info."""
        item_frame = ttk.Frame(self.thumbnail_frame, padding=5, relief="groove", borderwidth=1)
        item_frame.pack(pady=4, padx=5, fill="x")

        # Make the entire row clickable for preview
        item_frame.bind("<Button-1>", lambda e, g=group: self._show_preview(g))

        chk = ttk.Checkbutton(item_frame, variable=group['var'])
        chk.pack(side="left", padx=(0, 10))

        if group['type'] == 'image' and group.get('pil_img'):
            photo = self.thumbnail_manager.create_image_thumbnail(group['pil_img'])
            group['img_obj'] = photo
            img_label = ttk.Label(item_frame, image=photo, cursor="hand2")
            img_label.pack(side="left")
            img_label.bind("<Button-1>", lambda e, g=group: self._show_preview(g))
        elif group['type'] == 'text':
            display_text = group['text'][:25] + ('...' if len(group['text']) > 25 else '')
            photo = self.thumbnail_manager.create_text_thumbnail(display_text)
            group['img_obj'] = photo
            img_label = ttk.Label(item_frame, image=photo, cursor="hand2")
            img_label.pack(side="left")
            img_label.bind("<Button-1>", lambda e, g=group: self._show_preview(g))

        info_lines = self._build_group_info(group)
        info_label = ttk.Label(item_frame, text="\n".join(info_lines), justify="left", cursor="hand2")
        info_label.pack(side="left", padx=10)
        info_label.bind("<Button-1>", lambda e, g=group: self._show_preview(g))

    def _build_group_info(self, group: Dict[str, Any]) -> List[str]:
        """Build display info lines for a group."""
        lines = []
        if group['type'] == 'image':
            lines.append("유형: 이미지")
            lines.append(f"XRef: {group['xref']}")
        elif group['type'] == 'text':
            lines.append("유형: 텍스트")
            lines.append(f'키워드: "{group["text"]}"')
            pc = group['page_count']
            if pc <= 5:
                page_nums = ", ".join(str(p + 1) for p in group['pages'])
                lines.append(f"페이지: {page_nums}")
            else:
                first_pages = ", ".join(str(p + 1) for p in group['pages'][:3])
                lines.append(f"페이지: {first_pages}, ... 외 {pc - 3}개 ({pc}페이지)")
        lines.append(f"파일: {group['source']}")
        return lines

    # ─── Preview Panel ──────────────────────────────────────────

    def _show_preview(self, group: Dict[str, Any]):
        """Render a page preview with the watermark location highlighted."""
        # Determine file and page
        if not group.get('member_keys'):
            return

        first_key = group['member_keys'][0]
        file_path = first_key[1]

        if group['type'] == 'text':
            page_num = group.get('pages', [0])[0]
            # Get bbox from raw candidate — may be fitz.Rect or tuple
            raw_bbox = self.raw_candidates.get(first_key, {}).get('bbox')
            if raw_bbox is not None:
                if hasattr(raw_bbox, 'x0'):
                    bbox = (raw_bbox.x0, raw_bbox.y0, raw_bbox.x1, raw_bbox.y1)
                elif isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) == 4:
                    bbox = tuple(raw_bbox)
                else:
                    bbox = None
            else:
                bbox = None
        elif group['type'] == 'image':
            page_num = 0  # Images appear on many pages; show first page
            bbox = None
        else:
            return

        try:
            doc = fitz.open(file_path)
            try:
                page = doc.load_page(page_num)
                # Render at 1.5x zoom for clarity
                zoom = 1.5
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)

                # Draw red rectangle on bbox if available
                if bbox and ImageDraw:
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    draw = ImageDraw.Draw(img)
                    # Scale bbox coordinates by zoom factor
                    r = (bbox[0] * zoom, bbox[1] * zoom, bbox[2] * zoom, bbox[3] * zoom)
                    draw.rectangle(r, outline="red", width=3)
                    # Semi-transparent fill via overlay
                    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
                    overlay_draw = ImageDraw.Draw(overlay)
                    overlay_draw.rectangle(r, fill=(255, 0, 0, 40))
                    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
                else:
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                # Fit to preview panel size
                preview_w = max(self.preview_canvas.winfo_width(), 200)
                preview_h = max(self.preview_canvas.winfo_height(), 200)
                img.thumbnail((preview_w - 10, preview_h - 10), Image.Resampling.LANCZOS)

                self._preview_photo = ImageTk.PhotoImage(img)

                # Show preview canvas, hide placeholder
                self.preview_label.pack_forget()
                self.preview_canvas.pack(fill="both", expand=True)
                self.preview_canvas.delete("all")

                # Center image using actual image dimensions
                img_w, img_h = img.size
                cx = max(preview_w // 2, img_w // 2)
                cy = max(preview_h // 2, img_h // 2)
                self.preview_canvas.create_image(
                    cx, cy + 10,  # +10 for page info text offset
                    image=self._preview_photo, anchor="center"
                )

                # Add page info text
                page_info = f"{Path(file_path).name}  —  페이지 {page_num + 1}"
                self.preview_canvas.create_text(
                    5, 5, text=page_info, anchor="nw",
                    fill="#666666", font=("TkDefaultFont", 9)
                )
            finally:
                doc.close()

        except Exception as e:
            logger.error(f"Preview error: {e}")
            # Re-show placeholder label with error message
            self.preview_canvas.pack_forget()
            self.preview_label.config(text=f"미리보기 실패:\n{e}")
            self.preview_label.pack(fill="both", expand=True)

    # ─── Log Panel ──────────────────────────────────────────────

    def log_message(self, text: str):
        self.log_text.config(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.config(state="disabled")


if __name__ == "__main__":
    _enable_dpi_awareness()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    logger.info("--- Environment Check ---")
    logger.info(f"Python Executable: {sys.executable}")
    logger.info(f"Fitz (PyMuPDF) Version: {fitz.__version__}")
    logger.info(f"sv_ttk: {'available' if HAS_SV_TTK else 'not installed'}")
    logger.info("-------------------------")

    app = App()
    app.mainloop()
