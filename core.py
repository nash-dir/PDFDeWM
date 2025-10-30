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
and removal process. It bridges the GUI with the backend modules (`identifier`
and `editor`).
"""


import fitz
from pathlib import Path
from typing import List, Dict, Any, Tuple
import shutil
from PIL import Image

import identifier
import editor


def scan_files_for_watermarks(
    file_paths: List[str],
    min_page_ratio: float,
    text_keywords: List[str] = None
) -> Dict[Tuple, Dict[str, Any]]:
    """Scans multiple PDF files to find both image and text watermark candidates."""
    all_candidates: Dict[Tuple, Dict[str, Any]] = {}

    if text_keywords is None:
        text_keywords = []

    for file_path in file_paths:
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

            # 2. Find text watermarks by checking entire text blocks
            if text_keywords:
                for page_num, page in enumerate(doc):
                    text_blocks = page.get_text("blocks")
                    
                    for block in text_blocks:
                        block_text = block[4]
                        block_rect = fitz.Rect(block[:4])

                        for keyword in text_keywords:
                            if keyword in block_text:
                                bbox_tuple = tuple(round(c, 2) for c in block_rect)
                                candidate_key = ('text', file_path, page_num, bbox_tuple)

                                if candidate_key not in all_candidates:
                                    all_candidates[candidate_key] = {
                                        'type': 'text',
                                        'text': keyword,
                                        'full_text': block_text,
                                        'page': page_num,
                                        'bbox': block_rect,
                                        'source': Path(file_path).name
                                    }
                                break 
            doc.close()
        except Exception as e:
            print(f"Error while scanning file ({Path(file_path).name}): {e}")
            continue

    return all_candidates


def process_and_remove_watermarks(
    file_path: str, 
    output_dir: str, 
    candidates_to_remove: Dict[str, List[Any]],
    suffix: str,
    overwrite: bool = False,
    sanitize_hidden_text: bool = False,
    input_dir_root: str = None  #  Set default input path
):
    """Removes selected watermarks and optionally sanitizes the file."""
    output_path = Path(output_dir)
    source_path = Path(file_path)
    if not output_path.is_dir():
        print(f"Error: Output directory '{output_dir}' not found.")
        return

    # Set default output path
    output_filename = output_path / f"{source_path.stem}{suffix}.pdf"

    if input_dir_root:
        try:
            relative_path = source_path.relative_to(input_dir_root)
            output_filename = output_path / relative_path.parent / f"{source_path.stem}{suffix}.pdf"
            # In case there is no child directory, create one.
            output_filename.parent.mkdir(parents=True, exist_ok=True)
        except ValueError:
            # In case file is not included in default path, use default path.

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
                print("Applying redactions and sanitizing hidden texts...")
            else:
                print("Applying text redactions...")
            
            doc.scrub(
                redactions=True,
                hidden_text=sanitize_hidden_text
            )

        if output_filename.exists() and not overwrite:
            print(f"Skipping save: '{output_filename.name}' already exists.")
            return

        doc.save(str(output_filename), garbage=4, deflate=True)
        print(f"Saved processed file to '{output_filename}'.")

    except (FileNotFoundError, RuntimeError, Exception) as e:
        print(f"Error while processing file ({source_path.name}): {e}")
    finally:
        if doc:
            doc.close()


def copy_unprocessed_file(
    file_path: str, 
    output_dir: str, 
    overwrite: bool = False,
    input_dir_root: str = None 
):
    """Copies a file to the output directory, preserving subfolder structure."""
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
            print(f"Skipping copy: '{destination.name}' already exists.")
            return

        if source.resolve() == destination.resolve():
            print(f"Skipping copy: Source and destination are the same for '{source.name}'.")
            return
            
        shutil.copy2(source, destination)
        print(f"Copied unprocessed file '{source.name}' to output directory.")
    except (IOError, shutil.Error) as e:
        print(f"Error copying file '{Path(file_path).name}': {e}")

