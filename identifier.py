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


"""Contains functions to identify potential watermarks in a PDF document.

Provides multiple detection strategies:
- Commonality-based: images repeated across many pages.
- Transparency-based: images using semi-transparent ExtGState.
- Text keyword-based: text blocks containing specific keywords.
- Text position-based: repeating text at the same position across pages.
"""


import logging
import fitz  # PyMuPDF
from collections import defaultdict
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger("pdfdewm.identifier")


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
    
    logger.info(f"Searching for images on at least {min_pages}/{total_pages} pages...")
    logger.info(f"Found common image xrefs: {common_xrefs}")
    
    return common_xrefs


def find_by_transparency(doc: fitz.Document) -> List[int]:
    """Identifies images associated with semi-transparent graphics states.

    Watermarks are often rendered with reduced opacity via ExtGState objects
    with /ca or /CA values less than 1.0.

    Args:
        doc: The PyMuPDF document to be analyzed.

    Returns:
        A list of xrefs for image objects that use transparent ExtGState.
    """
    transparent_xrefs: List[int] = []

    try:
        # Collect ExtGState objects with transparency
        transparent_gs_names: Dict[int, set] = {}  # page_num -> set of gs names

        for page_num, page in enumerate(doc):
            page_resources = page.xref
            try:
                # Attempt to read ExtGState from the page resources
                res_str = doc.xref_object(page_resources)
            except Exception:
                continue

            # Find all image xrefs on this page
            img_list = page.get_images(full=True)
            if not img_list:
                continue

            # Check each image's rendering for transparency
            # via the page's content stream analysis
            for img_info in img_list:
                xref = img_info[0]
                try:
                    obj_str = doc.xref_object(xref)
                    # Check if the image itself has an SMask (soft mask = transparency)
                    if "/SMask" in obj_str:
                        if xref not in transparent_xrefs:
                            transparent_xrefs.append(xref)
                            logger.debug(f"Found transparent image (SMask) xref={xref}")
                except Exception:
                    continue

    except Exception as e:
        logger.warning(f"Error during transparency scan: {e}")

    logger.info(f"Transparency scan found {len(transparent_xrefs)} candidate(s).")
    return transparent_xrefs


def find_text_by_keywords(
    doc: fitz.Document,
    keywords: List[str],
) -> List[Dict[str, Any]]:
    """Identifies text blocks containing any of the specified keywords.

    Moved from core.py to identifier.py for proper separation of concerns.

    Args:
        doc: The PyMuPDF document to be analyzed.
        keywords: A list of keyword strings to search for.

    Returns:
        A list of dictionaries containing match information with keys:
        'text', 'full_text', 'page', 'bbox', 'bbox_tuple'.
    """
    if not keywords:
        return []

    results: List[Dict[str, Any]] = []
    seen_keys = set()

    for page_num, page in enumerate(doc):
        text_blocks = page.get_text("blocks")

        for block in text_blocks:
            block_text = block[4]
            block_rect = fitz.Rect(block[:4])

            for keyword in keywords:
                if keyword in block_text:
                    bbox_tuple = tuple(round(c, 2) for c in block_rect)
                    dedup_key = (page_num, bbox_tuple)

                    if dedup_key not in seen_keys:
                        seen_keys.add(dedup_key)
                        results.append({
                            'text': keyword,
                            'full_text': block_text,
                            'page': page_num,
                            'bbox': block_rect,
                            'bbox_tuple': bbox_tuple,
                        })
                    break  # One keyword match per block is enough

    logger.info(f"Text keyword scan found {len(results)} match(es).")
    return results


def find_text_by_position(
    doc: fitz.Document,
    min_page_ratio: float = 0.8,
    tolerance: float = 2.0,
) -> List[Dict[str, Any]]:
    """Identifies repeating text at similar positions across pages.

    Text blocks that appear at roughly the same coordinates on a high
    percentage of pages are likely watermarks or headers/footers.

    Args:
        doc: The PyMuPDF document to be analyzed.
        min_page_ratio: Minimum fraction of pages the text must appear on.
        tolerance: Coordinate tolerance in points for position matching.

    Returns:
        A list of dictionaries with repeating text watermark info.
    """
    total_pages = len(doc)
    if total_pages < 2:
        return []

    # Collect text blocks with their rounded positions
    position_map: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {'count': 0, 'pages': [], 'text': '', 'bbox': None}
    )

    for page_num, page in enumerate(doc):
        text_blocks = page.get_text("blocks")
        for block in text_blocks:
            block_text = block[4].strip()
            if not block_text or len(block_text) < 2:
                continue

            # Create a position key with tolerance rounding
            rx = round(block[0] / tolerance) * tolerance
            ry = round(block[1] / tolerance) * tolerance
            key = f"{block_text}@{rx:.0f},{ry:.0f}"

            entry = position_map[key]
            entry['count'] += 1
            entry['pages'].append(page_num)
            entry['text'] = block_text
            if entry['bbox'] is None:
                entry['bbox'] = fitz.Rect(block[:4])

    min_pages = max(2, int(total_pages * min_page_ratio))
    results: List[Dict[str, Any]] = []

    for key, data in position_map.items():
        if data['count'] >= min_pages:
            results.append({
                'text': data['text'],
                'full_text': data['text'],
                'page': data['pages'][0],  # Representative page
                'pages': data['pages'],
                'bbox': data['bbox'],
                'count': data['count'],
            })

    logger.info(f"Position-based scan found {len(results)} repeating text pattern(s).")
    return results


def find_by_vector_pattern(
    doc: fitz.Document,
    min_page_ratio: float = 0.8,
) -> List[Dict[str, Any]]:
    """Identifies repeated vector graphics (path operations) across pages.

    Many watermarks are drawn as vector shapes — diagonal lines, outlined
    text via font paths, or repeated geometric patterns. This function
    extracts graphics state blocks (q...Q) from each page's content stream,
    hashes them, and finds blocks that appear on a high fraction of pages.

    Args:
        doc: The PyMuPDF document to analyze.
        min_page_ratio: Minimum fraction of pages a block must appear on.

    Returns:
        A list of dictionaries with vector watermark candidate info.
    """
    import hashlib
    import re as _re

    total_pages = len(doc)
    if total_pages < 2:
        return []

    # Pattern to extract q...Q blocks (graphics state push/pop).
    # In PDF content streams, q and Q are standalone operators
    # (preceded by newline/start-of-string, followed by whitespace).
    qQ_pattern = _re.compile(
        r"(?:^|\n)\s*(q\n.*?\nQ)\s*(?:\n|$)",
        flags=_re.DOTALL
    )

    # Track block hashes → pages they appear on
    block_pages: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {'count': 0, 'pages': [], 'sample': '', 'size': 0}
    )

    for page_num, page in enumerate(doc):
        try:
            for content_xref in page.get_contents():
                try:
                    stream = doc.xref_stream(content_xref)
                except Exception:
                    continue

                try:
                    text = stream.decode("utf-8")
                except UnicodeDecodeError:
                    text = stream.decode("latin-1")

                # Find all q...Q blocks
                for match in qQ_pattern.finditer(text):
                    block = match.group(1).strip()

                    # Skip trivially small blocks (< 50 chars likely just images)
                    if len(block) < 50:
                        continue

                    # Skip blocks that are just image Do commands (already handled)
                    if block.count("\n") < 3 and " Do" in block:
                        continue

                    # Hash the block for dedup
                    block_hash = hashlib.md5(block.encode("utf-8")).hexdigest()

                    entry = block_pages[block_hash]
                    if page_num not in entry['pages']:
                        entry['count'] += 1
                        entry['pages'].append(page_num)
                    if not entry['sample']:
                        entry['sample'] = block[:200]
                        entry['size'] = len(block)

        except Exception as e:
            logger.debug(f"Error reading content stream on page {page_num}: {e}")
            continue

    min_pages = max(2, int(total_pages * min_page_ratio))
    results: List[Dict[str, Any]] = []

    # PDF path operators (must appear as standalone tokens)
    path_ops = _re.compile(r'(?:^|\s)([mlchvSsfFBWn]|re|cm)\s', _re.MULTILINE)

    for block_hash, data in block_pages.items():
        if data['count'] >= min_pages:
            # Detect path operators in the block
            if path_ops.search(data['sample']):
                results.append({
                    'type': 'vector',
                    'hash': block_hash,
                    'page': data['pages'][0],
                    'pages': data['pages'],
                    'count': data['count'],
                    'sample': data['sample'],
                    'size': data['size'],
                })

    logger.info(f"Vector pattern scan found {len(results)} repeating block(s).")
    return results


def find_watermark_candidates(
    doc: fitz.Document,
    strategy: str = 'commonality',
    **kwargs: Any
) -> List[Any]:
    """Identifies watermark candidates using a specified strategy.

    This is the main dispatcher function that calls the appropriate
    identification strategy.

    Args:
        doc: The PyMuPDF document to be analyzed.
        strategy: The identification strategy to use. Supported:
                  'commonality', 'transparency', 'text_keywords',
                  'text_position', 'vector'. Defaults to 'commonality'.
        **kwargs: Additional arguments for the chosen strategy.

    Returns:
        A list of results from the chosen strategy.

    Raises:
        ValueError: If an unsupported strategy name is provided.
    """
    strategies = {
        'commonality': lambda: find_by_commonality(
            doc, kwargs.get('min_page_ratio', 0.8)
        ),
        'transparency': lambda: find_by_transparency(doc),
        'text_keywords': lambda: find_text_by_keywords(
            doc, kwargs.get('keywords', [])
        ),
        'text_position': lambda: find_text_by_position(
            doc,
            kwargs.get('min_page_ratio', 0.8),
            kwargs.get('tolerance', 2.0),
        ),
        'vector': lambda: find_by_vector_pattern(
            doc,
            kwargs.get('min_page_ratio', 0.8),
        ),
    }

    if strategy not in strategies:
        raise ValueError(
            f"Unknown strategy: '{strategy}'. "
            f"Supported: {list(strategies.keys())}"
        )

    return strategies[strategy]()

