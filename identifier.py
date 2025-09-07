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


"""Contains functions to identify potential watermarks in a PDF document."""


import fitz  # PyMuPDF
from collections import defaultdict
from typing import List, Dict, Any


def find_by_commonality(doc: fitz.Document, min_page_ratio: float = 0.8) -> List[int]:
    """Identifies images that appear on a high percentage of pages.

    This is the most common and reliable method for detecting watermarks,
    as they are typically repeated throughout a document.

    Args:
        doc: The PyMuPDF document to be analyzed.
        min_page_ratio: The minimum fraction of pages an image must appear on
                        to be considered a watermark (e.g., 0.8 for 80%).

    Returns:
        A list of cross-reference numbers (xrefs) for image objects suspected
        of being watermarks.

    Raises:
        TypeError: If the provided doc object is not a fitz.Document.
    """
    if not isinstance(doc, fitz.Document):
        raise TypeError("The doc argument must be a fitz.Document object.")
    
    total_pages = len(doc)
    if total_pages == 0:
        return []

    image_counts = defaultdict(int)

    for page in doc:
        xrefs_on_page = {img[0] for img in page.get_images(full=True)}
        for xref in xrefs_on_page:
            image_counts[xref] += 1
            
    min_pages = max(1, int(total_pages * min_page_ratio))

    common_xrefs = [xref for xref, count in image_counts.items() if count >= min_pages]
    
    print(f"Searching for images that appear on at least {min_pages} of {total_pages} pages...")
    print(f"Found common image xrefs: {common_xrefs}")
    
    return common_xrefs


def find_by_transparency(doc: fitz.Document) -> List[int]:
    """(Future Implementation) Identifies images with transparency.

    This method can be effective as watermarks are often semi-transparent.

    Args:
        doc: The PyMuPDF document to be analyzed.

    Returns:
        An empty list, as this feature is not yet implemented.
    """
    print("Note: Transparency-based identification is not yet implemented.")
    # Example logic:
    # 1. Iterate through all ExtGState objects.
    # 2. Find ExtGState with /ca or /CA values less than 1.0.
    # 3. Collect the xrefs of image objects that use that ExtGState.
    return []


def find_text_watermarks(doc: fitz.Document, min_page_ratio: float = 0.8) -> List[Dict[str, Any]]:
    """(Future Implementation) Identifies repeating text as watermarks.

    This method would identify text that appears in the same position
    on multiple pages.

    Args:
        doc: The PyMuPDF document to be analyzed.
        min_page_ratio: The minimum fraction of pages the text must appear on.

    Returns:
        An empty list, as this feature is not yet implemented.
    """
    print("Note: Text-based watermark identification is not yet implemented.")
    # Example logic:
    # 1. Extract text blocks and their positions (bbox) from all pages.
    # 2. Count pages with text blocks of identical content and position.
    # 3. Return info on text blocks that meet the min_page_ratio.
    return []


def find_watermark_candidates(
    doc: fitz.Document,
    strategy: str = 'commonality',
    **kwargs: Any
) -> List[int]:
    """Identifies watermark candidates using a specified strategy.

    This is the main dispatcher function that calls the appropriate
    identification strategy.

    Args:
        doc: The PyMuPDF document to be analyzed.
        strategy: The identification strategy to use ('commonality', 
                  'transparency', etc.). Defaults to 'commonality'.
        **kwargs: Additional arguments for the chosen strategy, such as
                  `min_page_ratio` for the 'commonality' strategy.

    Returns:
        A list of xrefs of the identified watermark candidates.
    
    Raises:
        ValueError: If an unsupported strategy name is provided.
    """
    if strategy == 'commonality':
        min_page_ratio = kwargs.get('min_page_ratio', 0.8)
        return find_by_commonality(doc, min_page_ratio)
    
    elif strategy == 'transparency':
        return find_by_transparency(doc)
    
    else:
        raise ValueError(f"Unknown identification strategy: {strategy}")
