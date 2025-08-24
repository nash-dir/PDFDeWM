# editor.py
"""
This module contains functions that directly modify a PDF document to remove watermarks.
It takes a fitz.Document object and a list of xrefs of the objects to be removed as input.
"""

import fitz  # PyMuPDF
import re
from typing import List, Dict, Set

# -----------------------------------------------------------------------------
# --- PDF Editing Helper Functions ---
# -----------------------------------------------------------------------------

def map_xrefs_to_names(doc: fitz.Document, xrefs: List[int]) -> Dict[int, str]:
    """
    Maps a list of image xrefs to the names used in page resources (e.g., /Im1).
    This is necessary to find the image invocation commands in the Content Stream.

    Args:
        doc (fitz.Document): The target PyMuPDF document object.
        xrefs (List[int]): A list of xrefs of the image objects to find the names of.

    Returns:
        Dict[int, str]: A dictionary in the format {xref: "image_name"}.
    """
    name_map = {}
    xrefs_to_find = set(xrefs)

    for page in doc:
        # If we have found all the names, we don't need to iterate further
        if not xrefs_to_find:
            break
            
        try:
            # Directly parse the XObject dictionary from the page's /Resources object
            # xref_object returns the raw, uncompressed string
            resources = doc.xref_object(page.xref)
            for xref in list(xrefs_to_find):
                # Search for the pattern /Im... <xref> 0 R
                match = re.search(rf"/(Im\d+)\s+{xref}\s+0\s+R", resources)
                if match:
                    name = match.group(1)
                    name_map[xref] = name
                    xrefs_to_find.remove(xref)
        except Exception as e:
            # If an exception occurs, such as a page with no resources, move to the next page
            print(f"Error parsing resources on page {page.number}: {e}")
            continue
            
    if xrefs_to_find:
        print(f"Warning: Could not find names for the following xrefs: {xrefs_to_find}")

    print(f"Image name mapping complete: {name_map}")
    return name_map

def clean_content_streams(doc: fitz.Document, image_names: List[str]):
    """
    Iterates through the Content Stream of all pages and removes the drawing (Do) command blocks
    that invoke the specified image names.

    Args:
        doc (fitz.Document): The target PyMuPDF document object.
        image_names (List[str]): A list of names of the images to be removed (e.g., ["Im1", "Im2"]).
    """
    if not image_names:
        return

    # Create a regular expression pattern that connects multiple image names with | (e.g., /Im1|/Im2)
    names_pattern = "|".join(re.escape(name) for name in image_names)
    
    # A common block pattern for drawing a watermark: q ... /Im... Do ... Q
    # q/Q are commands that save/restore the graphics state, and they usually wrap the drawing of a single object.
    # The re.DOTALL flag allows '.' to include newline characters.
    watermark_pattern = re.compile(
        rf"q\s*.*?/({names_pattern})\s+Do\s*.*?Q",
        flags=re.DOTALL
    )

    print(f"Attempting to remove the following image calls from the Content Stream: {image_names}")
    for page in doc:
        try:
            for content_xref in page.get_contents():
                # When decoding the stream, use 'latin-1' to guard against unexpected encodings
                stream = doc.xref_stream(content_xref).decode("latin-1")
                
                # Use regular expressions to replace the watermark block with an empty string
                cleaned_stream = watermark_pattern.sub("", stream)

                if cleaned_stream != stream:
                    print(f"Cleaned Content Stream on page {page.number} (xref={content_xref}).")
                    doc.update_stream(content_xref, cleaned_stream.encode("latin-1"))
        except Exception as e:
            print(f"Error cleaning content on page {page.number}: {e}")

def delete_objects_and_smasks(doc: fitz.Document, xrefs: List[int]) -> int:
    """
    Completely deletes the objects corresponding to the given list of xrefs and any associated
    SMask (transparency mask) objects from the PDF.

    Args:
        doc (fitz.Document): The target PyMuPDF document object.
        xrefs (List[int]): A list of xrefs of the image objects to be deleted.

    Returns:
        int: The total number of objects actually deleted.
    """
    deleted_xrefs: Set[int] = set()
    for xref in xrefs:
        # 1. Find and delete the SMask object
        try:
            obj_definition = doc.xref_object(xref)
            # Search for the pattern /SMask <smask_xref> 0 R
            smask_match = re.search(r"/SMask\s+(\d+)\s+0\s+R", obj_definition)
            if smask_match:
                smask_xref = int(smask_match.group(1))
                if smask_xref not in deleted_xrefs:
                    doc._delete_object(smask_xref)
                    deleted_xrefs.add(smask_xref)
                    print(f"Deleted SMask object (xref={smask_xref}).")
        except Exception as e:
            # If an exception occurs, such as being unable to read the object definition, ignore it and proceed
            print(f"Error while searching for SMask (xref={xref}): {e}")
            pass

        # 2. Delete the original image object
        try:
            if xref not in deleted_xrefs:
                doc._delete_object(xref)
                deleted_xrefs.add(xref)
                print(f"Deleted image object (xref={xref}).")
        except Exception as e:
            print(f"Failed to delete image object (xref={xref}): {e}")
    
    return len(deleted_xrefs)

# -----------------------------------------------------------------------------
# --- Main Editing Function (Process Integration) ---
# -----------------------------------------------------------------------------

def remove_watermarks_by_xrefs(doc: fitz.Document, image_xrefs: List[int]):
    """
    This is the main function that executes the entire watermark removal process.
    This function can be called directly from the GUI's background worker.
    
    Args:
        doc (fitz.Document): The PyMuPDF document object to be modified.
        image_xrefs (List[int]): A list of xrefs of the watermark images to be removed, selected by the user.
    """
    if not image_xrefs:
        print("No watermark xrefs to remove.")
        return

    print("-" * 20)
    print(f"Starting removal of {len(image_xrefs)} selected watermark objects.")
    
    # 1. Convert XRefs to image names
    name_map = map_xrefs_to_names(doc, image_xrefs)
    
    # 2. Remove image invocation commands from the Content Stream
    clean_content_streams(doc, list(name_map.values()))
    
    # 3. Completely delete the images and related objects (SMask)
    delete_objects_and_smasks(doc, image_xrefs)
    
    print("Watermark removal process complete.")
    print("-" * 20)