# PDFDeWM - PDF Watermark Remover

## Overview

PDF Watermark Remover is a desktop GUI and CLI tool designed to easily remove image-based and text-based watermarks from PDF files.

This program intelligently identifies images that appear commonly across multiple pages as watermarks. It then presents these candidates to the user as thumbnails for visual confirmation.

## Key Features

* **Intuitive GUI**: Built with Tkinter for a simple and effective user experience.
* **CLI Batch Mode**: Process multiple PDFs from the command line without a GUI.
* **Intelligent Watermark Detection**: Multiple strategies — commonality, transparency (SMask), text keyword, and text position.
* **Visual Confirmation**: Allows users to visually inspect and select which candidates to remove.
* **Flexible File Handling**: Supports processing single files, multiple files, or all PDFs in a folder.
* **Safe Operation**: Creates new files with watermarks removed, leaving the original files untouched.
* **Drag & Drop**: Drop PDF files directly onto the application (requires `tkinterdnd2`).
* **Cancellable Operations**: Abort long-running scans or removals at any time.
* **Persistent Settings**: Remembers your output folder, suffix, and threshold between sessions.
* **OOM Defense**: Automatically skips files exceeding the size limit (default: 500MB).
* **Extensive Keyboard Shortcuts**.

---

## Distribution

PDFDeWM is distributed as a **portable zip** that contains:

| Component | Description |
|-----------|-------------|
| `PDFDeWM.exe` | Tiny C launcher (10KB) — compiled from `launcher/launcher.c` in GitHub Actions |
| `python/` | Official Python Embeddable from [python.org](https://www.python.org/) (Microsoft-signed binary) |
| `app/` | Application source code (`.py` files — fully inspectable) |

**No installer, no temp unpacking, no AV false positives.**

Every release zip is built by [GitHub Actions](../../actions) from the tagged source code — the build log is publicly verifiable.

---

## Requirements & Installation

### Option A: Download Pre-built (Recommended)

1. Download the latest `PDFDeWM-v*-win-amd64.zip` from [Releases](../../releases)
2. Extract anywhere
3. Double-click `PDFDeWM.exe`

No Python installation needed. No admin privileges required.

### Option B: Run from Source

Requires **Python 3.10+**.

1.  **Clone & Install**
    ```
    git clone https://github.com/nash-dir/PDFDeWM.git
    cd PDFDeWM
    pip install .
    ```

2.  **Run**
    ```
    python GUI.py
    ```

### Option C: Build Release Locally

```bash
# Requires Python 3.10+ and gcc (MinGW)
python scripts/build_release.py --output-dir dist
```

3.  **(Optional) Install Development Dependencies**
    ```
    pip install ".[dev]"
    ```

4.  **(Optional) Install Drag & Drop Support**
    ```
    pip install ".[dnd]"
    ```

## How to Use

### GUI Mode

* Simplest way is just downloading **pre-built latest release**

1.  **Launch the Application**
    ```
    python GUI.py
    ```

2.  **Add Files & Set Options**
    * Click **"Add Files"** (`Ctrl+A`) or **"Add Folder"** (`Ctrl+Shift+A`) to select input files.
    * **Drag & Drop** PDF files or folders directly onto the file list.
    * Click **"Browse"** (`Ctrl+S`) to select an Output folder.
    * Designate **"Output Suffix"** (`Ctrl+Q`) to concatenate after the original filename.
    * Check **"Copy unprocessed files"** to copy unprocessed files in the batch to the Output directory.
    * Check **"Overwrite existing files"** to overwrite existing files.
    * **⚠️ Be careful if "Output Suffix" is blank and "Overwrite existing files" is checked.**

3.  **Scan for Watermarks**
    * Click **"Scan Selected Files"** (`Ctrl+D`).
    * Adjust **"Scan Threshold"** to set the detection sensitivity.

4.  **Select and Remove**
    * Uncheck any images you do not want to remove.
    * Click **"Run Watermark Removal"** (`Ctrl+F`).
    * Use **"Cancel"** to abort if needed.
    * Click **"Open Output Folder"** to view results.

### CLI Mode

```bash
# Basic usage
python cli.py --input ./pdfs/ --output ./cleaned/

# With text keywords and custom threshold
python cli.py -i file.pdf -o ./out/ -k "CONFIDENTIAL;DRAFT" -t 60

# Preview without modifying (dry-run)
python cli.py -i ./pdfs/ -o ./out/ -k "DRAFT" --dry-run

# Export JSON report
python cli.py -i ./pdfs/ -o ./out/ --report audit.json

# Top-level only (no subdirectory recursion)
python cli.py -i ./pdfs/ -o ./out/ --no-recursive

# Full options
python cli.py --input ./pdfs/ --output ./out/ \
  --keywords "WATERMARK" --threshold 80 \
  --suffix "_clean" --overwrite --sanitize \
  --max-size-mb 200 --verbose

# Dry-run + report combo
python cli.py -i ./batch/ -o ./tmp/ --dry-run --report scan_results.json

# Show all options
python cli.py --help
```

---

## ⌨️ Keyboard Shortcuts

| Action | Shortcut | Description |
| :--- | :--- | :--- |
| **Add Files** | `Ctrl+A` | Open file selection dialog. |
| **Add Folder** | `Ctrl+Shift+A` | Open folder selection dialog. |
| **Browse Output Folder** | `Ctrl+S` / `Ctrl+Shift+S` | Open the output folder selection dialog. |
| **Scan Selected Files** | `Ctrl+D` / `Ctrl+Shift+D` | Start the watermark identification scan. |
| **Run Watermark Removal** | `Ctrl+F` / `Ctrl+Shift+F` | Start the removal process. |
| **Close Application** | `Ctrl+T` / `Ctrl+Shift+T` | Exit the program. |
| **Focus Output Suffix** | `Ctrl+Q` / `Ctrl+Shift+Q` | Move cursor to the Output Suffix field. |
| **Focus Text Keywords** | `Ctrl+W` / `Ctrl+Shift+W` | Move cursor to the Text Keywords field. |
| **Remove Selected File** | `Delete` / `Backspace` | Remove the selected file(s) from the queue. |
| **Open Selected File** | `Double-Click` / `Enter` | Open the selected file in the default viewer. |

---

## Project Structure

```
PDFDeWM/
├── GUI.py              # Main GUI application
├── cli.py              # CLI batch processing interface
├── core.py             # Orchestrates scanning and removal workflow
├── identifier.py       # Watermark detection strategies
├── editor.py           # Low-level PDF modification
├── utils.py            # File dialogs, thumbnails, config persistence
├── models.py           # Data models (dataclasses)
├── launcher/
│   └── launcher.c      # C source for PDFDeWM.exe launcher
├── scripts/
│   └── build_release.py  # Automated portable bundle builder
├── tests/              # pytest test suite (55 tests)
│   ├── conftest.py
│   ├── test_identifier.py
│   ├── test_editor.py
│   ├── test_core.py
│   └── test_cli.py
├── pyproject.toml      # Project metadata & dependencies
├── CHANGELOG.md        # Version history
└── .github/workflows/
    ├── ci.yml          # Lint + test on push/PR
    └── release.yml     # Build + release on v* tag
```

## License

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**.

This is a "copyleft" license, chosen because this project depends on libraries like **PyMuPDF (AGPL)**. This means that if you use or modify this project's source code and distribute your modified version, you are required to make your source code available under the same GPLv3 license.

> **Note**: A [browser-based version](https://github.com/nash-dir/PDFDeWM) using **pdfium (BSD-3-Clause)** is being developed to offer a more permissive licensing option. See [CHANGELOG.md](CHANGELOG.md) for details.

For commercial use cases where GPL compliance is not feasible, a commercial license for the underlying **MuPDF** library can be purchased from [Artifex Software, Inc.](https://artifex.com/licensing/).