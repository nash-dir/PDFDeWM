import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import threading
import queue

# 필수 라이브러리: PyMuPDF, Pillow
# pip install PyMuPDF pillow
try:
    from PIL import Image, ImageTk
except ImportError:
    messagebox.showerror(
        "라이브러리 오류",
        "Pillow 라이브러리가 필요합니다.\n'pip install pillow' 명령어로 설치해주세요."
    )
    exit()

# --- 핵심 로직 모듈 임포트 ---
import core 

class App(tk.Tk):
    """PDF 워터마크 제거 GUI 애플리케이션 메인 클래스"""

    def __init__(self):
        super().__init__()
        self.title("PDF Watermark Remover")
        self.geometry("800x700")
        self.minsize(600, 500)

        # --- 데이터 관리 ---
        self.input_files = []
        self.output_dir = ""
        self.watermark_candidates = {}
        self.task_queue = queue.Queue()

        # --- UI 구성 ---
        self._setup_ui()

        # --- 주기적 작업 큐 확인 ---
        self.after(100, self.process_queue)

    def _setup_ui(self):
        """애플리케이션의 UI 위젯들을 설정합니다."""
        # --- 1. 상단 프레임 (경로 지정) ---
        top_frame = ttk.Frame(self, padding="10")
        top_frame.pack(fill="x", side="top")
        top_frame.columnconfigure(1, weight=1)

        ttk.Button(top_frame, text="파일 추가", command=self.add_files).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(top_frame, text="폴더 추가", command=self.add_folder).grid(row=1, column=0, padx=(0, 5))
        
        self.file_listbox = tk.Listbox(top_frame, height=4, selectmode="extended")
        self.file_listbox.grid(row=0, column=1, rowspan=2, sticky="ew")
        list_scroll = ttk.Scrollbar(top_frame, orient="vertical", command=self.file_listbox.yview)
        list_scroll.grid(row=0, column=2, rowspan=2, sticky="ns")
        self.file_listbox.config(yscrollcommand=list_scroll.set)

        ttk.Label(top_frame, text="저장 폴더:").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.output_dir_entry = ttk.Entry(top_frame)
        self.output_dir_entry.grid(row=2, column=1, sticky="ew", pady=(10, 0))
        ttk.Button(top_frame, text="찾아보기", command=self.select_output_dir).grid(row=2, column=2, sticky="e", pady=(10, 0), padx=(5,0))

        action_frame = ttk.Frame(top_frame)
        action_frame.grid(row=3, column=0, columnspan=3, pady=(10, 0))
        self.scan_button = ttk.Button(action_frame, text="선택 파일 스캔", command=self.start_scan)
        self.scan_button.pack(side="left", padx=5)
        self.remove_button = ttk.Button(action_frame, text="워터마크 제거 실행", command=self.start_removal, state="disabled")
        self.remove_button.pack(side="left", padx=5)

        # --- 3. 하단 프레임 (진행 상태) ---
        bottom_frame = ttk.Frame(self, padding="10")
        bottom_frame.pack(fill="x", side="bottom")
        bottom_frame.columnconfigure(0, weight=1)

        self.status_label = ttk.Label(bottom_frame, text="준비 완료.")
        self.status_label.grid(row=0, column=0, columnspan=2, sticky="w")
        self.progress_bar = ttk.Progressbar(bottom_frame, orient="horizontal", mode="determinate")
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        self.percent_label = ttk.Label(bottom_frame, text="0%")
        self.percent_label.grid(row=1, column=1, sticky="w", padx=(5, 0), pady=(5, 0))

        # --- 2. 중단 프레임 (썸네일) ---
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

    # --- UI 이벤트 핸들러 및 헬퍼 ---
    def add_files(self):
        files = filedialog.askopenfilenames(title="PDF 파일 선택", filetypes=[("PDF files", "*.pdf")])
        for file in files:
            if file not in self.input_files:
                self.input_files.append(file)
                self.file_listbox.insert("end", Path(file).name)

    def add_folder(self):
        folder = filedialog.askdirectory(title="PDF가 포함된 폴더 선택")
        if folder:
            for file in sorted(Path(folder).glob("*.pdf")):
                file_str = str(file)
                if file_str not in self.input_files:
                    self.input_files.append(file_str)
                    self.file_listbox.insert("end", file.name)

    def select_output_dir(self):
        directory = filedialog.askdirectory(title="결과를 저장할 폴더 선택")
        if directory:
            self.output_dir = directory
            self.output_dir_entry.delete(0, "end")
            self.output_dir_entry.insert(0, self.output_dir)

    # --- 스레드 및 비동기 작업 관리 ---
    def start_scan(self):
        if not self.input_files:
            messagebox.showwarning("파일 없음", "스캔할 PDF 파일을 먼저 추가해주세요.")
            return

        self.clear_thumbnails()
        self.scan_button.config(state="disabled")
        self.remove_button.config(state="disabled")
        self.status_label.config(text="워터마크 후보 스캔 중...")
        self.progress_bar["value"] = 0
        self.percent_label.config(text="0%")

        threading.Thread(target=self.scan_worker, daemon=True).start()

    def start_removal(self):
        selected_xrefs = [xref for xref, data in self.watermark_candidates.items() if data['var'].get()]
        if not selected_xrefs:
            messagebox.showwarning("선택 없음", "제거할 워터마크 이미지를 하나 이상 선택해주세요.")
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
                    self.status_label.config(text=f"스캔 완료. {task[1]}개의 워터마크 후보 발견.")
                    self.scan_button.config(state="normal")
                    if task[1] > 0: self.remove_button.config(state="normal")
                elif task[0] == 'removal_progress':
                    _, n, m = task
                    msg = f"파일 처리 중... ({n}/{m})"
                    self.status_label.config(text=msg)
                    progress = int((n / m) * 100)
                    self.progress_bar["value"] = progress
                    self.percent_label.config(text=f"{progress}%")
                elif task[0] == 'removal_complete':
                    self.status_label.config(text="워터마크 제거 완료!")
                    self.progress_bar["value"] = 100
                    self.percent_label.config(text="100%")
                    messagebox.showinfo("완료", "선택된 워터마크가 모두 제거되었습니다.")
                    self.scan_button.config(state="normal")
                    self.remove_button.config(state="normal")
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_queue)

    # --- 워커 스레드 로직 (Core 모듈 호출) ---
    def scan_worker(self):
        """[리팩토링됨] core 모듈을 호출하여 워터마크 후보를 스캔합니다."""
        # core.scan_files_for_watermarks는 후보 정보를 담은 딕셔너리를 반환
        candidates = core.scan_files_for_watermarks(self.input_files, min_page_ratio=0.5)
        
        for xref, data in candidates.items():
            self.task_queue.put(('candidate_found', data['pil_img'], data['doc_path'], xref))
        
        self.task_queue.put(('scan_complete', len(candidates)))

    def removal_worker(self, xrefs_to_remove):
        """[리팩토링됨] core 모듈을 호출하여 워터마크를 제거합니다."""
        total_files = len(self.input_files)
        # GUI 업데이트를 위해 진행 상황을 큐에 넣는 로직은 유지
        for i, file_path in enumerate(self.input_files):
            self.task_queue.put(('removal_progress', i + 1, total_files))
            # 실제 파일 처리 로직은 core 모듈에 위임
            core.process_and_remove_watermarks([file_path], self.output_dir, xrefs_to_remove)
        
        self.task_queue.put(('removal_complete',))

    # --- 썸네일 UI 헬퍼 ---
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
