# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.0] - 2026-04-06

### Added
- **Global Typography Upgrade**: All tkinter elements now forcefully inherit "Malgun Gothic" (맑은 고딕) to fix Korean character rendering issues under the `sv_ttk` theme engine.
- **Embedded Tkinter Runtime**: Python embeddable distribution now includes a fully functional `tkinter` and `tkinterdnd2` environment so drag-and-drop E2E works perfectly without external dependencies.
- **Automated Dependency Harvesting**: `scripts/build_release.py` now statically links system Tcl/Tk binaries.

## [1.3.1] - 2026-03-27

### Added
- **CLI `--dry-run` / `-n`**: Scan and preview watermark candidates without modifying any files.
- **CLI `--report` / `-r`**: Export scan/processing results as a structured JSON report.
- **CLI `--no-recursive`**: Limit directory scanning to the top level only.
- **CLI argument groups**: Help output organized into logical sections (required, detection, output, advanced, execution mode).
- **CLI test suite**: 20 new tests in `tests/test_cli.py` (arg parsing, dry-run, report JSON, E2E).
- **C Launcher** (`launcher/launcher.c`): Tiny WinMain launcher that invokes `pythonw.exe` — no console window, graceful error dialogs.
- **Build Script** (`scripts/build_release.py`): Automated portable bundle creation with Python Embeddable.
- **Release Workflow** (`.github/workflows/release.yml`): Builds and uploads release zip on `v*` tag push.
- **Modern Theme**: `sv_ttk` (Sun Valley) theme with light/dark mode toggle (🌙 button).
- **Text Watermark Grouping**: Identical text watermarks across pages are grouped into a single checkbox (e.g., "DRAFT on 500 pages" → 1 click).
- **Empty State**: Placeholder guidance text shown when no files are loaded.
- **Select All / Deselect All / Invert**: Bulk selection buttons for watermark candidates.
- **Completion Summary**: Detailed post-processing dialog showing processed/copied/skipped counts and elapsed time.
- **DPI Awareness**: Per-monitor DPI awareness on Windows 10+.
- **Window Persistence**: Window size/position saved and restored between sessions.
- **File Count Label**: Shows the number of loaded files above the file list.
- **Tooltips**: Hover hints for key controls explaining their purpose.
- **Korean UI Labels**: All interface labels translated to Korean.

### Changed
- **Distribution**: Migrated from PyInstaller to **Embeddable Python bundle** — eliminates AV false positives.
- `collect_pdf_files()` now accepts a `recursive` parameter (default: `True`).
- Processing loop refactored to accumulate per-file results for JSON reporting.
- Total test count: 55 (previously 35).

### Removed
- `PDFDeWM.spec` (PyInstaller spec file) — no longer needed.

## [1.3.0] - 2026-03-27

### Added
- **CLI Mode** (`cli.py`): Batch watermark removal via command line with `--input`, `--output`, `--keywords`, `--threshold`, `--max-size-mb`, `--sanitize`, and `--verbose` options.
- **Cancel Button**: Abort running scan/removal operations via UI or `Ctrl+C` in CLI.
- **Drag & Drop**: Drop PDF files or folders onto the file list (requires `tkinterdnd2`).
- **Open Output Folder**: One-click button to open the output directory after processing.
- **Persistent Settings**: Output folder, suffix, and threshold are saved between sessions in `~/.pdfdewm/config.json`.
- **Scan Progress Bar**: Visual progress during the scanning phase.
- **Transparency Detection**: `identifier.find_by_transparency()` now detects images with SMask (soft mask) objects.
- **Text Position Detection**: `identifier.find_text_by_position()` finds repeating text at identical coordinates across pages.
- **Data Models** (`models.py`): Type-safe `ImageCandidate` and `TextCandidate` dataclasses.
- **Test Suite**: `tests/` directory with `pytest` tests for `identifier`, `editor`, and `core` modules.
- **CI Pipeline**: GitHub Actions workflow for automated linting (ruff) and testing on Python 3.10/3.12.
- **CHANGELOG.md**: This file.

### Changed
- **Logging**: All `print()` calls replaced with Python `logging` module across all modules.
- **Thread Safety**: `QueueLogger` now uses `threading.Lock` for thread-safe stdout buffering.
- **Text Scan Separation**: Text keyword scanning moved from `core.py` to `identifier.find_text_by_keywords()` (SRP).
- **Regex Safety**: Content stream regex in `editor.py` changed from greedy `.*` to non-greedy `[^Q]*?` to prevent over-matching.
- **Encoding**: Content stream decoding tries UTF-8 first, falls back to latin-1.
- **Font Caching**: `ThumbnailManager` caches loaded fonts to avoid per-call disk access and log spam.
- **Strategy Dispatcher**: `identifier.find_watermark_candidates()` refactored to use a strategy dictionary.
- **Python Version**: Minimum Python version updated from 3.8 to 3.10.
- **Dependencies**: Version ranges specified for `PyMuPDF` and `Pillow`.
- **GUI Structure**: Extracted `_rebuild_thumbnails()` and `_build_info_lines()` methods to reduce code duplication.
- **Environment Check**: Moved from module-level to `if __name__ == "__main__"` block.

### Fixed
- **Document Leak**: `doc.close()` moved to `finally` blocks in `core.py` to prevent resource leaks on exceptions.
- **Worker Crash Recovery**: Both `scan_worker` and `removal_worker` wrapped in try/except with proper UI state recovery.
- **OOM Defense**: Files exceeding 500MB (configurable) are automatically skipped.
- **Duplicate Imports**: Removed duplicate `import sys` and `import fitz` in `GUI.py`.
- **Indentation**: Fixed inconsistent indentation in `remove_selected_files`.
- **Exception Types**: Cleaned up redundant exception class hierarchy in `core.py`.

## [1.2.0] - 2025-XX-XX

### Added
- Extensive keyboard shortcuts.
- Text watermark detection and removal via keywords.
- Enhanced list management with auto-cursor and file opening.
- `Scrub invisible text` option.
- Overwrite warning for dangerous configurations.

### Changed
- Improved queue stability.

## [1.1.0] - 2025-XX-XX

### Added
- Folder scanning with subfolder support.
- Copy unprocessed files option.
- Output suffix configuration.

## [1.0.0] - 2025-XX-XX

### Added
- Initial release.
- Image watermark detection by commonality.
- GUI application with Tkinter.
- PyInstaller build support.
