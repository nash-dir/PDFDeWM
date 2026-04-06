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


"""Command-line interface for PDFDeWM batch processing.

Usage:
    python cli.py --input ./pdfs/ --output ./cleaned/ --keywords "CONFIDENTIAL;DRAFT"
    python cli.py --input file.pdf --output ./out/ --threshold 60
    python cli.py -i ./pdfs/ -o ./out/ -k "DRAFT" --dry-run
    python cli.py -i ./pdfs/ -o ./out/ --report results.json
"""


import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import core
from models import MAX_FILE_SIZE_BYTES

logger = logging.getLogger("pdfdewm")


def setup_logging(verbose: bool = False):
    """Configure logging for CLI mode."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def collect_pdf_files(input_path: str, recursive: bool = True) -> List[str]:
    """Collect PDF files from a file path or directory.

    Args:
        input_path: Path to a PDF file or a directory.
        recursive: If True, search subdirectories recursively (rglob).
                   If False, only search the top-level directory (glob).

    Returns:
        Sorted list of absolute PDF file paths.
    """
    p = Path(input_path)
    if p.is_file() and p.suffix.lower() == '.pdf':
        return [str(p.resolve())]
    elif p.is_dir():
        glob_fn = p.rglob if recursive else p.glob
        return sorted(str(f.resolve()) for f in glob_fn("*.pdf"))
    else:
        logger.error(f"Invalid input: '{input_path}' is not a PDF file or directory.")
        return []


def _print_dry_run_report(
    candidates: Dict[Tuple, Dict[str, Any]],
    valid_files: List[str],
):
    """Print a human-readable summary of detected watermarks without modifying files.

    Groups candidates by source file and prints type, location, and details
    for each candidate. Files with no candidates are labeled [CLEAN].

    Args:
        candidates: The full candidate dictionary from core.scan_files_for_watermarks.
        valid_files: List of all files that were scanned.
    """
    # Group candidates by file
    by_file: Dict[str, List[Tuple[Tuple, Dict]]] = defaultdict(list)
    for key, data in candidates.items():
        fpath = key[1]
        by_file[fpath].append((key, data))

    print()
    print(f"[DRY-RUN] Found {len(candidates)} watermark candidate(s) across {len(by_file)} file(s):")
    print("-" * 72)

    for fpath in valid_files:
        fname = Path(fpath).name
        entries = by_file.get(fpath, [])

        if not entries:
            print(f"  [CLEAN]  {fname}")
            continue

        print(f"  📄 {fname}  ({len(entries)} candidate(s))")
        for key, data in entries:
            ctype = data.get('type', key[0])
            if ctype == 'image':
                xref = data.get('xref', key[2] if len(key) > 2 else '?')
                print(f"    [IMAGE] xref={xref}")
            elif ctype == 'text':
                keyword = data.get('text', '?')
                page = data.get('page', key[2] if len(key) > 2 else '?')
                bbox = data.get('bbox', None)
                bbox_str = f" at ({bbox})" if bbox else ""
                print(f'    [TEXT]  "{keyword}" on page {page + 1}{bbox_str}')

    print("-" * 72)
    print("[DRY-RUN] No files were modified.")
    print()


def _build_report(
    args: argparse.Namespace,
    candidates: Dict[Tuple, Dict[str, Any]],
    valid_files: List[str],
    file_results: List[Dict[str, Any]],
    skipped_size: int,
) -> Dict[str, Any]:
    """Build a structured JSON report of the scan/processing results.

    Args:
        args: Parsed CLI arguments.
        candidates: Full candidate dictionary from scanning.
        valid_files: Files that passed size filtering.
        file_results: Per-file processing result records.
        skipped_size: Number of files skipped due to size limit.

    Returns:
        A dictionary ready for JSON serialization.
    """
    processed = sum(1 for r in file_results if r["status"] == "processed")
    skipped_clean = sum(1 for r in file_results if r["status"] == "skipped_no_watermark")
    copied = sum(1 for r in file_results if r["status"] == "copied")

    return {
        "version": "1.3.0",
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
        "input": args.input,
        "output": args.output,
        "dry_run": getattr(args, 'dry_run', False),
        "options": {
            "threshold": args.threshold,
            "keywords": [k.strip() for k in args.keywords.split(';') if k.strip()] if args.keywords else [],
            "suffix": args.suffix,
            "recursive": not getattr(args, 'no_recursive', False),
            "sanitize": args.sanitize,
            "max_size_mb": args.max_size_mb,
        },
        "summary": {
            "total_files_found": len(valid_files) + skipped_size,
            "total_files_scanned": len(valid_files),
            "skipped_size_limit": skipped_size,
            "candidates_found": len(candidates),
            "processed": processed,
            "skipped_no_watermark": skipped_clean,
            "copied_unprocessed": copied,
        },
        "files": file_results,
    }


def _build_file_candidates(
    fpath: str,
    candidates: Dict[Tuple, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Extract per-file candidate info for the JSON report.

    Args:
        fpath: Absolute path to the file.
        candidates: Full candidate dictionary.

    Returns:
        A list of simplified candidate records for the report.
    """
    result = []
    for key, data in candidates.items():
        if key[1] != fpath:
            continue
        ctype = key[0]
        if ctype == 'image':
            result.append({
                "type": "image",
                "xref": data.get('xref', key[2] if len(key) > 2 else None),
            })
        elif ctype == 'text':
            bbox = data.get('bbox', None)
            result.append({
                "type": "text",
                "keyword": data.get('text', ''),
                "page": data.get('page', 0) + 1,
                "bbox": list(bbox) if bbox else None,
            })
    return result


def main(argv=None):
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="pdfdewm",
        description="PDFDeWM — Batch PDF watermark removal tool.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  %(prog)s -i ./pdfs/ -o ./out/                    Basic batch processing
  %(prog)s -i file.pdf -o ./out/ -k "DRAFT" -t 60  Text keyword + threshold
  %(prog)s -i ./pdfs/ -o ./out/ --dry-run           Preview without modifying
  %(prog)s -i ./pdfs/ -o ./out/ --report audit.json Export JSON report
  %(prog)s -i ./pdfs/ -o ./out/ --no-recursive      Top-level only""",
    )

    # ── Required ──
    required = parser.add_argument_group("required arguments")
    required.add_argument(
        "--input", "-i", required=True,
        help="Input PDF file or directory.",
    )
    required.add_argument(
        "--output", "-o", required=True,
        help="Output directory for processed files.",
    )

    # ── Detection ──
    detect = parser.add_argument_group("detection options")
    detect.add_argument(
        "--keywords", "-k", default="",
        help="Semicolon-separated text keywords for text watermark detection.",
    )
    detect.add_argument(
        "--threshold", "-t", type=int, default=80,
        help="Image scan threshold percentage (default: 80).",
    )

    # ── Output ──
    output = parser.add_argument_group("output options")
    output.add_argument(
        "--suffix", "-s", default="_removed",
        help="Suffix appended to output filenames (default: '_removed').",
    )
    output.add_argument(
        "--overwrite", action="store_true",
        help="Overwrite existing output files.",
    )
    output.add_argument(
        "--copy-unprocessed", action="store_true",
        help="Copy files with no watermarks to the output directory.",
    )

    # ── Advanced ──
    advanced = parser.add_argument_group("advanced processing")
    advanced.add_argument(
        "--sanitize", action="store_true",
        help="Scrub invisible/hidden text from the PDF.",
    )
    advanced.add_argument(
        "--clean-metadata", action="store_true",
        help="Strip sensitive metadata (Author, Creator, Producer, etc.) from PDFs.",
    )
    advanced.add_argument(
        "--max-size-mb", type=int, default=500,
        help="Maximum file size in MB (default: 500). Files exceeding this are skipped.",
    )

    # ── Execution mode ──
    mode = parser.add_argument_group("execution mode")
    mode.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Scan only — print detected watermarks without modifying any files.",
    )
    mode.add_argument(
        "--report", "-r", metavar="PATH",
        help="Save scan/processing results as a JSON report to PATH.",
    )
    mode.add_argument(
        "--no-recursive", action="store_true",
        help="Do not recurse into subdirectories when input is a directory.",
    )

    # ── Logging ──
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose (DEBUG) logging.",
    )

    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    # ── Validate output directory ──
    output_dir = Path(args.output)
    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    # ── Collect input files ──
    recursive = not args.no_recursive
    files = collect_pdf_files(args.input, recursive=recursive)
    if not files:
        logger.error("No PDF files found. Exiting.")
        sys.exit(1)

    logger.info(f"Found {len(files)} PDF file(s) (recursive={recursive}).")

    # ── Parse keywords ──
    keywords = [k.strip() for k in args.keywords.split(';') if k.strip()] if args.keywords else []

    # ── File size filter ──
    max_size = args.max_size_mb * 1024 * 1024
    valid_files = []
    skipped_size = 0
    for f in files:
        size = Path(f).stat().st_size
        if size > max_size:
            logger.warning(
                f"Skipping '{Path(f).name}' — exceeds {args.max_size_mb}MB limit "
                f"({size / 1024 / 1024:.1f}MB)."
            )
            skipped_size += 1
        else:
            valid_files.append(f)

    if not valid_files:
        logger.error("No valid files to process after size filtering.")
        sys.exit(1)

    # ══════════════════════════════════════════════════════════════
    # Phase 1: Scan
    # ══════════════════════════════════════════════════════════════
    logger.info("Scanning for watermarks...")
    min_ratio = args.threshold / 100.0
    candidates = core.scan_files_for_watermarks(valid_files, min_ratio, keywords)
    logger.info(f"Found {len(candidates)} watermark candidate(s).")

    # ── Dry-run exit point ──
    if args.dry_run:
        _print_dry_run_report(candidates, valid_files)
        # Optionally write JSON report even in dry-run mode
        if args.report:
            file_results = []
            for fpath in valid_files:
                cands = _build_file_candidates(fpath, candidates)
                file_results.append({
                    "input": Path(fpath).name,
                    "output": None,
                    "status": "dry_run",
                    "candidates": cands,
                })
            report = _build_report(args, candidates, valid_files, file_results, skipped_size)
            Path(args.report).write_text(
                json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            logger.info(f"Report saved to '{args.report}'.")
        sys.exit(0)

    # ══════════════════════════════════════════════════════════════
    # Phase 2: Remove
    # ══════════════════════════════════════════════════════════════
    candidates_by_file: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for key, data in candidates.items():
        ctype, fpath = key[0], key[1]
        if ctype == 'image':
            candidates_by_file[fpath]['image'].append(data['xref'])
        elif ctype == 'text':
            page_num = key[2]
            candidates_by_file[fpath]['text'].append({'page': page_num, 'bbox': data['bbox']})

    input_root = None
    input_path = Path(args.input)
    if input_path.is_dir():
        input_root = str(input_path.resolve())

    file_results: List[Dict[str, Any]] = []
    total = len(valid_files)
    failed_count = 0

    for i, fpath in enumerate(valid_files, 1):
        fname = Path(fpath).name
        logger.info(f"Processing ({i}/{total}): {fname}")

        try:
            should_process = (
                fpath in candidates_by_file
                or args.sanitize
                or args.clean_metadata
            )
            cands_for_report = _build_file_candidates(fpath, candidates)

            if should_process:
                to_remove = candidates_by_file.get(fpath, {})
                core.process_and_remove_watermarks(
                    fpath, str(output_dir), to_remove, args.suffix,
                    overwrite=args.overwrite,
                    sanitize_hidden_text=args.sanitize,
                    clean_metadata=args.clean_metadata,
                    input_dir_root=input_root,
                )
                file_results.append({
                    "input": fname,
                    "output": f"{Path(fpath).stem}{args.suffix}.pdf",
                    "status": "processed",
                    "candidates": cands_for_report,
                })
            elif args.copy_unprocessed:
                core.copy_unprocessed_file(
                    fpath, str(output_dir),
                    overwrite=args.overwrite,
                    input_dir_root=input_root,
                )
                file_results.append({
                    "input": fname,
                    "output": fname,
                    "status": "copied",
                    "candidates": [],
                })
            else:
                file_results.append({
                    "input": fname,
                    "output": None,
                    "status": "skipped_no_watermark",
                    "candidates": cands_for_report,
                })

        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to process '{fname}': {e}")
            file_results.append({
                "input": fname,
                "output": None,
                "status": "error",
                "error": str(e),
                "candidates": [],
            })

    # ── Write JSON report ──
    if args.report:
        report = _build_report(args, candidates, valid_files, file_results, skipped_size)
        Path(args.report).write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(f"Report saved to '{args.report}'.")

    if failed_count:
        logger.warning(f"{failed_count} file(s) failed during processing.")
    logger.info("Done.")


if __name__ == "__main__":
    main()
