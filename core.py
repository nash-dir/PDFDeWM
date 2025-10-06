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


import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Dict, Any, Tuple
import shutil

from PIL import Image, ImageDraw, ImageFont

import identifier
import editor


def scan_files_for_watermarks(
    file_paths: List[str],
    min_page_ratio: float,
    text_keywords: List[str] = None
) -> Dict[Tuple, Dict[str, Any]]:
    """Scans multiple PDF files to find both image and text watermark candidates.

    This function finds common images and searches for text blocks containing
    specified keywords. It extracts/generates thumbnails for all candidates.
    """
    all_candidates: Dict[Tuple, Dict[str, Any]] = {}

    if text_keywords is None:
        text_keywords = []

    for file_path in file_paths:
        try:
            doc = fitz.open(file_path)

            # 1. Find image watermarks (unchanged)
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
                    # Get all text blocks from the page
                    # A block is a tuple: (x0, y0, x1, y1, "text...", block_no, type)
                    text_blocks = page.get_text("blocks")
                    
                    for block in text_blocks:
                        block_text = block[4] # The full text content of the block
                        block_rect = fitz.Rect(block[:4]) # The bounding box of the block

                        for keyword in text_keywords:
                            if keyword in block_text:
                                # Create a unique key for the entire block
                                bbox_tuple = tuple(round(c, 2) for c in block_rect)
                                candidate_key = ('text', file_path, page_num, bbox_tuple)

                                if candidate_key not in all_candidates:
                                    # Generate a thumbnail showing the full block text (truncated)
                                    text_img = Image.new('RGB', (200, 50), color='white')
                                    draw = ImageDraw.Draw(text_img)
                                    try:
                                        font = ImageFont.truetype("arial.ttf", 15)
                                    except IOError:
                                        font = ImageFont.load_default()
                                    
                                    # Show the beginning of the block text in the thumbnail
                                    display_text = (block_text[:25] + '...') if len(block_text) > 25 else block_text
                                    draw.text((10, 10), display_text.replace('\n', ' '), fill='black', font=font)
                                    
                                    all_candidates[candidate_key] = {
                                        'type': 'text',
                                        'pil_img': text_img,
                                        'text': keyword, # The keyword that was found
                                        'full_text': block_text, # The full text of the block
                                        'page': page_num,
                                        'bbox': block_rect,
                                        'source': Path(file_path).name
                                    }
                                # Once a keyword matches a block, move to the next block
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
    overwrite: bool = False
):
    """Removes selected image and text watermarks from a file and saves it.

    Args:
        file_path: The absolute path to the PDF file to process.
        output_dir: The directory where the modified file will be saved.
        candidates_to_remove: A dictionary with 'image' and 'text' keys,
                              containing lists of xrefs and text info to remove.
        suffix: The string to append to the output filename.
        overwrite: If True, overwrite the output file if it already exists.
    """
    output_path = Path(output_dir)
    if not output_path.is_dir():
        print(f"Error: Output directory '{output_dir}' not found.")
        return

    doc = None
    try:
        doc = fitz.open(file_path)
        
        # 1. Remove image watermarks
        image_xrefs = candidates_to_remove.get('image', [])
        if image_xrefs:
            editor.remove_watermarks_by_xrefs(doc, image_xrefs)

        # 2. Add redactions for text watermarks and apply them per page
        text_candidates = candidates_to_remove.get('text', [])
        if text_candidates:
            # First, add all redaction annotations to the document
            editor.add_text_redactions(doc, text_candidates)
            
            # Then, find which pages were affected
            affected_pages = sorted(list({cand['page'] for cand in text_candidates}))
            
            # Finally, apply redactions on each affected page
            for page_num in affected_pages:
                doc[page_num].apply_redactions()
            print(f"Permanently applied text redactions on {len(affected_pages)} page(s).")

        output_filename = output_path / f"{Path(file_path).stem}{suffix}.pdf"
        
        if output_filename.exists() and not overwrite:
            print(f"Skipping save: '{output_filename.name}' already exists.")
            return
            
        doc.save(str(output_filename), garbage=4, deflate=True)
        print(f"Saved processed file to '{output_filename}'.")

    except (FileNotFoundError, RuntimeError, Exception) as e:
        print(f"Error while processing file ({Path(file_path).name}): {e}")
    finally:
        if doc:
            doc.close()


def copy_unprocessed_file(file_path: str, output_dir: str, overwrite: bool = False):
    """Copies a file to the output directory without modification.

    Used for files that were part of the input but had no watermarks selected
    for removal.

    Args:
        file_path: The absolute path to the source file.
        output_dir: The directory where the file will be copied.
        overwrite: If True, overwrite the destination file if it exists.
    """

    try:
        source = Path(file_path)
        destination = Path(output_dir) / source.name
        
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