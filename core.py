# core.py
"""
This is the core module that connects the GUI with the backend logic (identifier, editor).
It contains functions that control the overall flow of PDF processing.
"""

import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Dict, Any

# Import other modules of the application
import identifier
import editor

# -----------------------------------------------------------------------------
# --- Core Process Functions ---
# -----------------------------------------------------------------------------

def scan_files_for_watermarks(
    file_paths: List[str], 
    min_page_ratio: float = 0.5
) -> Dict[int, Dict[str, Any]]:
    """
    Scans multiple PDF files to find common watermark candidates.
    Returns the information necessary to display thumbnails in the GUI.

    Args:
        file_paths (List[str]): A list of PDF file paths to scan.
        min_page_ratio (float): The minimum page ratio for an image to be considered a watermark.

    Returns:
        Dict[int, Dict[str, Any]]: 
        A dictionary in the format:
        {
            xref: {
                'pil_img': Pillow Image Object, 
                'doc_path': Original document path, 
                'xref': xref number
            }
        }
    """
    all_candidates = {}
    
    for file_path in file_paths:
        try:
            doc = fitz.open(file_path)
            
            # Use the identifier module to find watermark candidate xrefs
            common_xrefs = identifier.find_by_commonality(doc, min_page_ratio)
            
            for xref in common_xrefs:
                # Extract image data only if the candidate has not been found before
                if xref not in all_candidates:
                    pix = fitz.Pixmap(doc, xref)
                    # Convert to a Pillow Image object (for use in the GUI)
                    # Requires the Pillow library
                    from PIL import Image
                    mode = "RGBA" if pix.alpha else "RGB"
                    pil_img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
                    
                    all_candidates[xref] = {
                        'pil_img': pil_img,
                        'doc_path': file_path,
                        'xref': xref
                    }
            doc.close()
        except Exception as e:
            print(f"Error while scanning file ({Path(file_path).name}): {e}")
            continue
            
    return all_candidates


def process_and_remove_watermarks(
    file_paths: List[str], 
    output_dir: str, 
    xrefs_to_remove: List[int]
):
    """
    Removes the user-selected watermarks from the specified files and saves the results.

    Args:
        file_paths (List[str]): A list of original PDF file paths to process.
        output_dir (str): The folder path to save the resulting files.
        xrefs_to_remove (List[int]): A list of xrefs of the images to be removed, selected by the user in the GUI.
    """
    output_path = Path(output_dir)
    if not output_path.is_dir():
        print(f"Error: Output directory '{output_dir}' not found.")
        return

    for file_path in file_paths:
        try:
            doc = fitz.open(file_path)
            
            # Use the editor module to perform the actual watermark removal
            editor.remove_watermarks_by_xrefs(doc, xrefs_to_remove)
            
            # Save the result
            output_filename = output_path / f"{Path(file_path).stem}_removed.pdf"
            # garbage=4: Cleans up all unused objects (most aggressive option)
            # deflate=True: Compresses to optimize file size
            doc.save(str(output_filename), garbage=4, deflate=True)
            doc.close()
            print(f"Saved '{output_filename}'.")

        except Exception as e:
            print(f"Error while processing file ({Path(file_path).name}): {e}")
            if 'doc' in locals() and doc.is_open:
                doc.close()
            continue