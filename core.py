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

from PIL import Image

import identifier
import editor


def scan_files_for_watermarks(
    file_paths: List[str], 
    min_page_ratio: float = 0.5
) -> Dict[Tuple[str, int], Dict[str, Any]]:
    """Scans multiple PDF files to find and extract watermark candidates.

    This function iterates through a list of file paths, uses the `identifier`
    module to find potential watermarks, and extracts them as PIL Images.

    Args:
        file_paths: A list of absolute paths to the PDF files to scan.
        min_page_ratio: The minimum fraction of pages an image must appear on
                        to be considered a watermark.

    Returns:
        A dictionary where keys are (file_path, xref) tuples and values are
        dictionaries containing the extracted 'pil_img'.
    """
    all_candidates: Dict[Tuple[str, int], Dict[str, Any]] = {}
    
    for file_path in file_paths:
        try:
            doc = fitz.open(file_path)
            
            common_xrefs = identifier.find_by_commonality(doc, min_page_ratio)
            
            for xref in common_xrefs:
                candidate_key = (file_path, xref)
                if candidate_key not in all_candidates:
                    pix = fitz.Pixmap(doc, xref)
                    mode = "RGBA" if pix.alpha else "RGB"
                    pil_img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
                    
                    all_candidates[candidate_key] = {'pil_img': pil_img}
            doc.close()
        except (FileNotFoundError, RuntimeError) as e:
            print(f"Error while scanning file ({Path(file_path).name}): {e}")
            continue
            
    return all_candidates


def process_and_remove_watermarks(
    file_path: str, 
    output_dir: str, 
    xrefs_to_remove: List[int],
    suffix: str,
    overwrite: bool = False
):
    """Removes selected watermarks from a file and saves the result.

    Opens a PDF, invokes the `editor` module to remove the specified
    watermark cross-references, and saves the modified PDF to the
    output directory.

    Args:
        file_path: The absolute path to the PDF file to process.
        output_dir: The directory where the modified file will be saved.
        xrefs_to_remove: A list of integer xrefs of the watermarks to remove.
        suffix: The string to append to the output filename (before extension).
        overwrite: If True, overwrite the output file if it already exists.
    """
    output_path = Path(output_dir)
    if not output_path.is_dir():
        print(f"Error: Output directory '{output_dir}' not found.")
        return

    doc = None
    try:
        doc = fitz.open(file_path)
        editor.remove_watermarks_by_xrefs(doc, xrefs_to_remove)
        
        output_filename = output_path / f"{Path(file_path).stem}{suffix}.pdf"
        
        if output_filename.exists() and not overwrite:
            print(f"Skipping save: '{output_filename.name}' already exists.")
            return
            
        doc.save(str(output_filename), garbage=4, deflate=True)
        print(f"Saved processed file to '{output_filename}'.")

    except (FileNotFoundError, RuntimeError) as e:
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
