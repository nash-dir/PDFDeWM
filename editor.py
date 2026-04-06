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


import logging
import fitz  # PyMuPDF
import re
from typing import List, Dict, Set, Any
from collections import defaultdict

logger = logging.getLogger("pdfdewm.editor")


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
        logger.warning(f"Could not find names for xrefs: {xrefs_to_find}")

    logger.debug(f"Image name mapping complete: {name_map}")
    return name_map


def _decode_content_stream(stream_bytes: bytes) -> str:
    """Decode a PDF content stream, trying UTF-8 first then falling back to latin-1.

    Args:
        stream_bytes: Raw bytes from the content stream.

    Returns:
        The decoded string.
    """
    try:
        return stream_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return stream_bytes.decode("latin-1")


def _encode_content_stream(stream_str: str) -> bytes:
    """Encode a content stream string back to bytes.

    Uses latin-1 for maximum compatibility with PDF streams.

    Args:
        stream_str: The content stream as a string.

    Returns:
        Encoded bytes.
    """
    return stream_str.encode("latin-1", errors="replace")


def clean_content_streams(doc: fitz.Document, image_names: List[str]):
    """Removes image invocation commands from the page content streams.

    This prevents the watermark image from being drawn on the page. It finds
    and removes the 'Do' operator associated with the watermark image name.

    Uses a non-greedy, minimal regex pattern to avoid accidentally removing
    non-watermark content in nested q/Q blocks.

    Args:
        doc: The PyMuPDF document to modify.
        image_names: A list of image names (e.g., ['/Im1', '/Im2']) to remove.
    """
    if not image_names:
        return

    # Build a pattern that matches only the specific image Do command
    # Using non-greedy .*? and minimal scope to avoid over-matching
    names_pattern = "|".join(re.escape(name) for name in image_names)
    watermark_pattern = re.compile(
        rf"q\s[^Q]*?/({names_pattern})\s+Do\s*?[^q]*?Q",
        flags=re.DOTALL
    )

    logger.info(f"Removing image calls from content streams: {image_names}")
    for page in doc:
        try:
            for content_xref in page.get_contents():
                stream = _decode_content_stream(doc.xref_stream(content_xref))
                cleaned_stream = watermark_pattern.sub("", stream)
                
                if cleaned_stream != stream:
                    logger.debug(f"Cleaned content stream on page {page.number} (xref={content_xref}).")
                    doc.update_stream(content_xref, _encode_content_stream(cleaned_stream))
        except Exception as e:
            logger.error(f"Error cleaning content on page {page.number}: {e}")


def delete_objects_and_smasks(doc: fitz.Document, xrefs: List[int]) -> int:
    """Deletes image objects and their associated soft-mask (SMask) objects.

    Invalidating these objects ensures they are removed from the PDF structure.
    This uses ``doc.update_object(xref, "null")`` which is the official
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
                    logger.debug(f"Deleted SMask object (xref={smask_xref}).")
        except Exception as e:
            logger.error(f"Error searching SMask for image {xref}: {e}")

        try:
            if xref not in deleted_xrefs:
                doc.update_object(xref, "null")
                deleted_xrefs.add(xref)
                logger.debug(f"Deleted image object (xref={xref}).")
        except Exception as e:
            logger.error(f"Failed to delete image object (xref={xref}): {e}")
    
    return len(deleted_xrefs)


def add_text_redactions(doc: fitz.Document, text_candidates: List[Dict[str, Any]]):
    """Adds redaction annotations to cover text watermarks.

    This function does not permanently remove the text. It adds the redaction
    "markings" to the document. A subsequent call to ``doc.scrub(redactions=True)``
    is required to make the removal permanent.

    Args:
        doc: The PyMuPDF document to modify.
        text_candidates: A list of dictionaries, where each dictionary contains
                         the 'page' number and 'bbox' (fitz.Rect) for a text
                         watermark to be removed.
    """
    if not text_candidates:
        return

    logger.info(f"Adding redactions for {len(text_candidates)} text watermarks.")
    
    # Group candidates by page for efficiency
    candidates_by_page = defaultdict(list)
    for candidate in text_candidates:
        candidates_by_page[candidate['page']].append(candidate['bbox'])

    for page_num, bboxes in candidates_by_page.items():
        try:
            page = doc.load_page(page_num)
            for bbox in bboxes:
                page.add_redact_annot(bbox, fill=(1, 1, 1))  # Fill with white
            logger.debug(f"Added {len(bboxes)} redaction(s) on page {page_num + 1}.")
        except Exception as e:
            logger.error(f"Error adding redaction on page {page_num + 1}: {e}")


def remove_watermarks_by_xrefs(doc: fitz.Document, image_xrefs: List[int]):
    """Executes the full image watermark removal process on a document.

    This function orchestrates the three main steps for IMAGE watermarks:
    1. Map image xrefs to their names.
    2. Clean the names from the page content streams.
    3. Delete the image and smask objects from the PDF.

    Args:
        doc: The PyMuPDF document to modify.
        image_xrefs: A list of watermark image xrefs to remove.
    """
    if not image_xrefs:
        logger.debug("No image watermark xrefs provided to remove.")
        return

    logger.info(f"Starting removal of {len(image_xrefs)} image watermark(s).")
    
    name_map = map_xrefs_to_names(doc, image_xrefs)
    
    if name_map:
        clean_content_streams(doc, list(name_map.values()))
    else:
        logger.warning("No image names found; skipping content stream cleaning.")
    
    deleted = delete_objects_and_smasks(doc, image_xrefs)
    logger.info(f"Image watermark removal complete. {deleted} object(s) deleted.")


def clean_metadata(doc: fitz.Document):
    """Remove sensitive metadata fields from a PDF document.

    Clears Author, Creator, Producer, Subject, CreationDate, and ModDate
    from the PDF's Info dictionary. Sets Producer to 'PDFDeWM' to indicate
    the document has been processed.

    This is useful for forensic/privacy applications where document
    provenance information should be stripped.

    Args:
        doc: The PyMuPDF document to modify.
    """
    sensitive_fields = [
        "author", "creator", "producer", "subject",
        "creationDate", "modDate", "keywords",
    ]

    metadata = doc.metadata or {}
    cleaned_count = 0

    for field in sensitive_fields:
        if metadata.get(field):
            cleaned_count += 1

    if cleaned_count == 0:
        logger.info("No sensitive metadata fields found.")
        return

    # Set all sensitive fields to empty
    new_metadata = {
        "author": "",
        "creator": "",
        "producer": "PDFDeWM",
        "subject": "",
        "keywords": "",
        "creationDate": "",
        "modDate": "",
    }

    # Preserve title if present (usually not sensitive)
    if metadata.get("title"):
        new_metadata["title"] = metadata["title"]

    doc.set_metadata(new_metadata)
    logger.info(f"Cleaned {cleaned_count} metadata field(s). Producer set to 'PDFDeWM'.")
