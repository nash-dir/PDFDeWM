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


"""Data models for the PDFDeWM application.

Provides type-safe dataclasses to replace loosely-typed Dict[Tuple, Dict]
patterns used across the codebase.
"""


from dataclasses import dataclass, field
from typing import Optional, Tuple

import fitz
from PIL import Image


@dataclass
class ImageCandidate:
    """Represents an image watermark candidate."""
    type: str = field(default='image', init=False)
    xref: int = 0
    pil_img: Optional[Image.Image] = None
    source: str = ''


@dataclass
class TextCandidate:
    """Represents a text watermark candidate."""
    type: str = field(default='text', init=False)
    text: str = ''
    full_text: str = ''
    page: int = 0
    bbox: Optional[fitz.Rect] = None
    source: str = ''


# Type alias for candidate keys
ImageCandidateKey = Tuple[str, str, int]           # ('image', file_path, xref)
TextCandidateKey = Tuple[str, str, int, Tuple]     # ('text', file_path, page, bbox_tuple)

# Maximum file size in bytes (500 MB default)
MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024
