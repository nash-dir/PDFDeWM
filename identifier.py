# identifier.py
"""
This module contains functions for identifying objects suspected of being watermarks in a PDF document.
Each function takes a fitz.Document object as input and returns a list of xrefs of watermark candidates.
"""

import fitz  # PyMuPDF
from collections import defaultdict
from typing import List, Dict, Any

# -----------------------------------------------------------------------------
# --- Basic Watermark Identification Strategy: Commonality-Based Detection ---
# -----------------------------------------------------------------------------

def find_by_commonality(doc: fitz.Document, min_page_ratio: float = 0.8) -> List[int]:
    """
    Identifies images that appear on multiple pages of a document as watermarks.
    This is the most stable and common method for detecting watermarks.

    Args:
        doc (fitz.Document): The PyMuPDF document object to be analyzed.
        min_page_ratio (float): The minimum page ratio an image must appear on
                                to be considered a watermark. (Default: 0.8)

    Returns:
        List[int]: A list of xrefs of image objects suspected of being watermarks.
    """
    if not isinstance(doc, fitz.Document):
        raise TypeError("The doc argument must be a fitz.Document object.")
    
    total_pages = len(doc)
    if total_pages == 0:
        return []

    image_counts = defaultdict(int)

    # 1. Iterate through each page and count the occurrences of image xrefs.
    for page in doc:
        # Use a set to count an image only once per page, even if it appears multiple times
        xrefs_on_page = {img[0] for img in page.get_images(full=True)}
        for xref in xrefs_on_page:
            image_counts[xref] += 1
            
    # 2. Calculate the minimum number of pages an image must appear on.
    #    (e.g., for a 10-page document with a 0.8 ratio, it must appear on at least 8 pages)
    min_pages = max(1, int(total_pages * min_page_ratio))

    # 3. Filter and return only the image xrefs that have appeared on at least the minimum number of pages.
    common_xrefs = [xref for xref, count in image_counts.items() if count >= min_pages]
    
    print(f"Searching for images that appear on at least {min_pages} of {total_pages} pages...")
    print(f"Found common image xrefs: {common_xrefs}")
    
    return common_xrefs


# -----------------------------------------------------------------------------
# --- Extended/Alternative Identification Strategies (Examples for future implementation) ---
# -----------------------------------------------------------------------------

def find_by_transparency(doc: fitz.Document) -> List[int]:
    """
    (Future implementation) Identifies images with transparency (alpha) values as watermark candidates.
    This can be an effective strategy as watermarks are often semi-transparent.
    """
    print("Note: Transparency-based identification is not yet implemented.")
    # Example logic:
    # 1. Iterate through all ExtGState objects
    # 2. Find ExtGState with /ca or /CA values less than 1.0
    # 3. Collect the xrefs of the image objects that use that ExtGState
    return []

def find_text_watermarks(doc: fitz.Document, min_page_ratio: float = 0.8) -> List[Dict[str, Any]]:
    """
    (Future implementation) Identifies text that appears repeatedly in the same position
    on multiple pages as a watermark.
    """
    print("Note: Text-based watermark identification is not yet implemented.")
    # Example logic:
    # 1. Extract text blocks and their positions (bbox) from all pages
    # 2. Count how many pages have text blocks with almost identical content and position
    # 3. Return information about the text blocks that meet the min_page_ratio
    return []


# -----------------------------------------------------------------------------
# --- Main Identification Function (Strategy Selection) ---
# -----------------------------------------------------------------------------

def find_watermark_candidates(
    doc: fitz.Document,
    strategy: str = 'commonality',
    **kwargs
) -> List[int]:
    """
    This is the main function that identifies watermark candidates using a specified strategy.

    Args:
        doc (fitz.Document): The PyMuPDF document object to be analyzed.
        strategy (str): The identification strategy to use.
                        'commonality' (default), 'transparency', etc.
        **kwargs: Additional arguments required for each strategy.
                  (e.g., min_page_ratio for the commonality strategy)

    Returns:
        List[int]: A list of xrefs of the identified watermark candidates.
    
    Raises:
        ValueError: If an unsupported strategy name is given.
    """
    if strategy == 'commonality':
        min_page_ratio = kwargs.get('min_page_ratio', 0.8)
        return find_by_commonality(doc, min_page_ratio)
    
    elif strategy == 'transparency':
        return find_by_transparency(doc)
    
    # You can add other strategies later.
    # elif strategy == 'text':
    #     return find_text_watermarks(doc, **kwargs)
    
    else:
        raise ValueError(f"Unknown identification strategy: {strategy}")