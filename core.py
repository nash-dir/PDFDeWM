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


"""Core logic for scanning, processing, and saving PDF files.

This module acts as the main controller, orchestrating the identification
and removal process. It bridges the GUI/CLI with the backend modules
(``identifier`` and ``editor``).
"""


import logging
import fitz
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import shutil
from PIL import Image

import identifier
import editor
from models import MAX_FILE_SIZE_BYTES

logger = logging.getLogger("pdfdewm.core")


def _check_file_size(file_path: str, max_bytes: int = MAX_FILE_SIZE_BYTES) -> bool:
    """Check if a file exceeds the maximum allowed size.

    Args:
        file_path: Path to the file to check.
        max_bytes: Maximum allowed size in bytes.

    Returns:
        True if the file is within limits, False if it exceeds.
    """
    size = Path(file_path).stat().st_size
    if size > max_bytes:
        max_mb = max_bytes / (1024 * 1024)
        actual_mb = size / (1024 * 1024)
        logger.warning(
            f"Skipping '{Path(file_path).name}' — "
            f"{actual_mb:.1f}MB exceeds {max_mb:.0f}MB limit."
        )
        return False
    return True


def scan_files_for_watermarks(
    file_paths: List[str],
    min_page_ratio: float,
    text_keywords: Optional[List[str]] = None,
    cancel_flag: Optional[Any] = None,
) -> Dict[Tuple, Dict[str, Any]]:
    """Scans multiple PDF files to find both image and text watermark candidates.

    Args:
        file_paths: List of PDF file paths to scan.
        min_page_ratio: Minimum fraction of pages for commonality detection.
        text_keywords: Optional list of text keywords to search for.
        cancel_flag: Optional threading.Event or similar; if set, aborts early.

    Returns:
        A dictionary mapping candidate keys to candidate data dictionaries.
    """
    all_candidates: Dict[Tuple, Dict[str, Any]] = {}

    if text_keywords is None:
        text_keywords = []

    for file_path in file_paths:
        # Support cancellation
        if cancel_flag is not None and cancel_flag.is_set():
            logger.info("Scan cancelled by user.")
            break

        # File size guard (#10)
        if not _check_file_size(file_path):
            continue

        doc = None
        try:
            doc = fitz.open(file_path)

            # 1. Find image watermarks by commonality
            common_xrefs = identifier.find_by_commonality(doc, min_page_ratio)
            for xref in common_xrefs:
                candidate_key = ('image', file_path, xref)
                if candidate_key not in all_candidates:
                    pix = fitz.Pixmap(doc, xref)
                    mode = "RGBA" if pix.alpha else "RGB"
                    pil_img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
                    all_candidates[candidate_key] = {
                        'type': 'image',
                        'pil_img': pil_img,
                        'xref': xref,
                        'source': Path(file_path).name
                    }

            # 2. Find text watermarks by keywords (delegated to identifier)
            if text_keywords:
                text_matches = identifier.find_text_by_keywords(doc, text_keywords)
                for match in text_matches:
                    candidate_key = ('text', file_path, match['page'], match['bbox_tuple'])
                    if candidate_key not in all_candidates:
                        all_candidates[candidate_key] = {
                            'type': 'text',
                            'text': match['text'],
                            'full_text': match['full_text'],
                            'page': match['page'],
                            'bbox': match['bbox'],
                            'source': Path(file_path).name
                        }

        except Exception as e:
            logger.error(f"Error scanning '{Path(file_path).name}': {e}")
            continue
        finally:
            # Guarantee document is always closed (#4)
            if doc:
                doc.close()

    return all_candidates


def process_and_remove_watermarks(
    file_path: str, 
    output_dir: str, 
    candidates_to_remove: Dict[str, List[Any]],
    suffix: str,
    overwrite: bool = False,
    sanitize_hidden_text: bool = False,
    clean_metadata: bool = False,
    input_dir_root: Optional[str] = None,
):
    """Removes selected watermarks and optionally sanitizes the file.

    Args:
        file_path: Path to the source PDF.
        output_dir: Directory to write the output file.
        candidates_to_remove: Dict with 'image' and/or 'text' keys.
        suffix: Filename suffix for the output file.
        overwrite: If True, overwrite existing output files.
        sanitize_hidden_text: If True, scrub invisible text.
        clean_metadata: If True, strip sensitive PDF metadata.
        input_dir_root: Optional common root for preserving directory structure.
    """
    output_path = Path(output_dir)
    source_path = Path(file_path)
    if not output_path.is_dir():
        logger.error(f"Output directory '{output_dir}' not found.")
        return

    # Build output filename
    output_filename = output_path / f"{source_path.stem}{suffix}.pdf"

    if input_dir_root:
        try:
            relative_path = source_path.relative_to(input_dir_root)
            output_filename = output_path / relative_path.parent / f"{source_path.stem}{suffix}.pdf"
            output_filename.parent.mkdir(parents=True, exist_ok=True)
        except ValueError:
            pass

    doc = None
    try:
        doc = fitz.open(file_path)

        image_xrefs = candidates_to_remove.get('image', [])
        if image_xrefs:
            editor.remove_watermarks_by_xrefs(doc, image_xrefs)

        text_candidates = candidates_to_remove.get('text', [])
        if text_candidates:
            editor.add_text_redactions(doc, text_candidates)

        if text_candidates or sanitize_hidden_text:
            if sanitize_hidden_text:
                logger.info("Applying redactions and sanitizing hidden texts...")
            else:
                logger.info("Applying text redactions...")
            
            doc.scrub(
                redactions=True,
                hidden_text=sanitize_hidden_text
            )

        if clean_metadata:
            editor.clean_metadata(doc)

        if output_filename.exists() and not overwrite:
            logger.info(f"Skipping save: '{output_filename.name}' already exists.")
            return

        doc.save(str(output_filename), garbage=4, deflate=True)
        logger.info(f"Saved processed file to '{output_filename}'.")

    except Exception as e:
        logger.error(f"Error processing '{source_path.name}': {e}")
        raise  # Re-raise so callers can handle error isolation
    finally:
        if doc:
            doc.close()


def copy_unprocessed_file(
    file_path: str, 
    output_dir: str, 
    overwrite: bool = False,
    input_dir_root: Optional[str] = None, 
):
    """Copies a file to the output directory, preserving subfolder structure.

    Args:
        file_path: Path to the source file.
        output_dir: Destination directory.
        overwrite: If True, overwrite existing files.
        input_dir_root: Optional common root for preserving directory structure.
    """
    try:
        source = Path(file_path)
        destination_base = Path(output_dir)
        destination = destination_base / source.name

        if input_dir_root:
            try:
                relative_path = source.relative_to(input_dir_root)
                destination = destination_base / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
            except ValueError:
                pass

        if destination.exists() and not overwrite:
            logger.info(f"Skipping copy: '{destination.name}' already exists.")
            return

        if source.resolve() == destination.resolve():
            logger.info(f"Skipping copy: source and destination are the same for '{source.name}'.")
            return
            
        shutil.copy2(source, destination)
        logger.info(f"Copied unprocessed file '{source.name}' to output directory.")
    except (IOError, shutil.Error) as e:
        logger.error(f"Error copying '{Path(file_path).name}': {e}")
