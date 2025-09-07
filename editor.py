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

"""Contains functions that directly modify a PDF to remove watermarks."""


import fitz  # PyMuPDF
import re
from typing import List, Dict, Set


def map_xrefs_to_names(doc: fitz.Document, xrefs: List[int]) -> Dict[int, str]:
    """Maps image cross-reference numbers (xrefs) to their internal names.

    These names (e.g., '/Im1') are required to find and remove the image
    references from the page's content stream.

    Args:
        doc: The PyMuPDF document to be analyzed.
        xrefs: A list of image xrefs to map.

    Returns:
        A dictionary mapping each xref to its corresponding name.
    """
    name_map: Dict[int, str] = {}
    xrefs_to_find = set(xrefs)

    for page in doc:
        if not xrefs_to_find:
            break
        
        img_list = page.get_images(full=True)
        for img_info in img_list:
            xref = img_info[0]
            name = img_info[7]
            if xref in xrefs_to_find:
                name_map[xref] = name
                xrefs_to_find.remove(xref)

    if xrefs_to_find:
        print(f"Warning: Could not find names for the following xrefs: {xrefs_to_find}")

    print(f"Image name mapping complete: {name_map}")
    return name_map


def clean_content_streams(doc: fitz.Document, image_names: List[str]):
    """Removes image invocation commands from the page content streams.

    This prevents the watermark image from being drawn on the page. It finds
    and removes the 'Do' operator associated with the watermark image name.

    Args:
        doc: The PyMuPDF document to modify.
        image_names: A list of image names (e.g., ['/Im1', '/Im2']) to remove.
    """
    if not image_names:
        return

    names_pattern = "|".join(re.escape(name) for name in image_names)
    watermark_pattern = re.compile(
        rf"q\s*.*?/({names_pattern})\s+Do\s*.*?Q",
        flags=re.DOTALL
    )

    print(f"Attempting to remove image calls from content streams: {image_names}")
    for page in doc:
        try:
            for content_xref in page.get_contents():
                stream = doc.xref_stream(content_xref).decode("latin-1")
                cleaned_stream = watermark_pattern.sub("", stream)
                
                if cleaned_stream != stream:
                    print(f"Cleaned content stream on page {page.number} (xref={content_xref}).")
                    doc.update_stream(content_xref, cleaned_stream.encode("latin-1"))
        except Exception as e:
            # PyMuPDF can raise various internal errors. Catching a broad
            # exception is safer here without more specific documentation.
            print(f"Error cleaning content on page {page.number}: {e}")


def delete_objects_and_smasks(doc: fitz.Document, xrefs: List[int]) -> int:
    """Deletes image objects and their associated soft-mask (SMask) objects.

    Invalidating these objects ensures they are removed from the PDF structure.
    This uses `doc.update_object(xref, "null")` which is the official
    PyMuPDF method for object deletion.

    Args:
        doc: The PyMuPDF document to modify.
        xrefs: A list of image xrefs to delete.

    Returns:
        The total number of objects (images and smasks) that were deleted.
    """
    deleted_xrefs: Set[int] = set()
    for xref in xrefs:
        try:
            obj_definition = doc.xref_object(xref)
            smask_match = re.search(r"/SMask\s+(\d+)\s+0\s+R", obj_definition)
            if smask_match:
                smask_xref = int(smask_match.group(1))
                if smask_xref not in deleted_xrefs:
                    doc.update_object(smask_xref, "null")
                    deleted_xrefs.add(smask_xref)
                    print(f"Deleted SMask object (xref={smask_xref}).")
        except Exception as e:
            # Catching broad exception as PyMuPDF can raise various errors.
            print(f"Error while searching for SMask for image {xref}: {e}")

        try:
            if xref not in deleted_xrefs:
                doc.update_object(xref, "null")
                deleted_xrefs.add(xref)
                print(f"Deleted image object (xref={xref}).")
        except Exception as e:
            # Catching broad exception as PyMuPDF can raise various errors.
            print(f"Failed to delete image object (xref={xref}): {e}")
    
    return len(deleted_xrefs)


def remove_watermarks_by_xrefs(doc: fitz.Document, image_xrefs: List[int]):
    """Executes the full watermark removal process on a document.

    This function orchestrates the three main steps:
    1. Map image xrefs to their names.
    2. Clean the names from the page content streams.
    3. Delete the image and smask objects from the PDF.

    Args:
        doc: The PyMuPDF document to modify.
        image_xrefs: A list of watermark image xrefs to remove.
    """
    if not image_xrefs:
        print("No watermark xrefs provided to remove.")
        return

    print("-" * 20)
    print(f"Starting removal of {len(image_xrefs)} selected watermark objects.")
    
    name_map = map_xrefs_to_names(doc, image_xrefs)
    
    if name_map:
        clean_content_streams(doc, list(name_map.values()))
    else:
        print("No image names found; skipping content stream cleaning.")
    
    delete_objects_and_smasks(doc, image_xrefs)
    
    print("Watermark removal process complete.")
    print("-" * 20)
