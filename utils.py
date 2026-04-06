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


"""Utility classes for the PDFDeWM application.

This module contains helper classes that separate concerns from the main
GUI logic, such as file dialog interactions, image manipulation, encoding
detection, OS-specific font mapping, and user configuration persistence.
"""

import json
import logging
import platform
import unicodedata
from pathlib import Path
from tkinter import filedialog
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageTk, ImageDraw, ImageFont

logger = logging.getLogger("pdfdewm.utils")

# Default config directory
CONFIG_DIR = Path.home() / ".pdfdewm"
CONFIG_FILE = CONFIG_DIR / "config.json"


# ── Encoding / Script Detection ─────────────────────────────────

# Unicode script → abstract script key mapping.
# We classify each character into a broad script key like "cjk_ko",
# "arabic", "latin", etc. and then map to OS-specific font names.

_SCRIPT_RANGES: List[Tuple[int, int, str]] = [
    # CJK Unified Ideographs
    (0x4E00, 0x9FFF, "cjk"),
    (0x3400, 0x4DBF, "cjk"),          # Extension A
    (0x20000, 0x2A6DF, "cjk"),        # Extension B
    (0xF900, 0xFAFF, "cjk"),          # Compatibility Ideographs
    # Korean
    (0xAC00, 0xD7AF, "korean"),       # Hangul Syllables
    (0x1100, 0x11FF, "korean"),       # Hangul Jamo
    (0x3130, 0x318F, "korean"),       # Hangul Compatibility Jamo
    # Japanese
    (0x3040, 0x309F, "japanese"),     # Hiragana
    (0x30A0, 0x30FF, "japanese"),     # Katakana
    (0x31F0, 0x31FF, "japanese"),     # Katakana Extensions
    # Arabic
    (0x0600, 0x06FF, "arabic"),
    (0x0750, 0x077F, "arabic"),
    (0xFB50, 0xFDFF, "arabic"),
    (0xFE70, 0xFEFF, "arabic"),
    # Hebrew
    (0x0590, 0x05FF, "hebrew"),
    # Thai
    (0x0E00, 0x0E7F, "thai"),
    # Devanagari (Hindi, Sanskrit, etc.)
    (0x0900, 0x097F, "devanagari"),
    # Cyrillic
    (0x0400, 0x04FF, "cyrillic"),
    (0x0500, 0x052F, "cyrillic"),
    # Latin Extended
    (0x0000, 0x024F, "latin"),
    (0x1E00, 0x1EFF, "latin"),
]


def detect_script(text: str) -> str:
    """Detect the dominant Unicode script in a text string.

    Examines each character's codepoint and classifies it into a script
    family. Returns the most frequently occurring non-Latin script,
    falling back to "latin" if no other script dominates.

    Args:
        text: The text to analyze.

    Returns:
        A script key string like "korean", "japanese", "cjk", "arabic",
        "cyrillic", "latin", etc.
    """
    if not text:
        return "latin"

    script_counts: Dict[str, int] = {}

    for ch in text:
        if ch.isspace() or unicodedata.category(ch).startswith("P"):
            continue  # Skip whitespace and punctuation

        cp = ord(ch)
        script = "latin"  # Default fallback

        for lo, hi, s in _SCRIPT_RANGES:
            if lo <= cp <= hi:
                script = s
                break

        script_counts[script] = script_counts.get(script, 0) + 1

    if not script_counts:
        return "latin"

    # Prefer non-Latin scripts if they represent ≥ 20% of characters,
    # since Latin is commonly mixed in (e.g., "기밀 DOCUMENT").
    total = sum(script_counts.values())
    for script, count in sorted(script_counts.items(), key=lambda x: -x[1]):
        if script != "latin" and count / total >= 0.2:
            return script

    return "latin"


# ── OS-Specific Font Mapping ─────────────────────────────────────

# Key: (os_name, script_key)
# Value: ordered list of font filenames to try
# os_name: "Windows", "Darwin" (macOS), "Linux"

_FONT_MAP: Dict[Tuple[str, str], List[str]] = {
    # ── Korean ──
    ("Windows", "korean"):   ["malgun.ttf", "malgunbd.ttf", "gulim.ttc", "batang.ttc"],
    ("Darwin",  "korean"):   ["AppleSDGothicNeo.ttc", "AppleGothic.ttf"],
    ("Linux",   "korean"):   ["NotoSansCJK-Regular.ttc", "NanumGothic.ttf", "UnDotum.ttf"],

    # ── Japanese ──
    ("Windows", "japanese"): ["yugothic.ttf", "msgothic.ttc", "msmincho.ttc"],
    ("Darwin",  "japanese"): ["HiraginoSans-W3.ttc", "HiraKakuProN-W3.otf"],
    ("Linux",   "japanese"): ["NotoSansCJK-Regular.ttc", "TakaoPGothic.ttf"],

    # ── CJK (Chinese default) ──
    ("Windows", "cjk"):      ["msyh.ttc", "simsun.ttc", "simhei.ttf"],
    ("Darwin",  "cjk"):      ["PingFang.ttc", "STHeiti Medium.ttc"],
    ("Linux",   "cjk"):      ["NotoSansCJK-Regular.ttc", "WenQuanYi Micro Hei.ttf"],

    # ── Arabic ──
    ("Windows", "arabic"):   ["segoeui.ttf", "arial.ttf", "tahoma.ttf"],
    ("Darwin",  "arabic"):   ["GeezaPro.ttc", ".SFNSText.ttf"],
    ("Linux",   "arabic"):   ["NotoSansArabic-Regular.ttf", "DejaVuSans.ttf"],

    # ── Hebrew ──
    ("Windows", "hebrew"):   ["segoeui.ttf", "arial.ttf"],
    ("Darwin",  "hebrew"):   [".SFNSText.ttf"],
    ("Linux",   "hebrew"):   ["NotoSansHebrew-Regular.ttf", "DejaVuSans.ttf"],

    # ── Thai ──
    ("Windows", "thai"):     ["leelawui.ttf", "tahoma.ttf"],
    ("Darwin",  "thai"):     ["Thonburi.ttf", "SathuLight.ttf"],
    ("Linux",   "thai"):     ["NotoSansThai-Regular.ttf", "Loma.ttf"],

    # ── Devanagari ──
    ("Windows", "devanagari"): ["mangal.ttf", "nirmala.ttf"],
    ("Darwin",  "devanagari"): ["DevanagariSangamMN.ttc"],
    ("Linux",   "devanagari"): ["NotoSansDevanagari-Regular.ttf"],

    # ── Cyrillic ──
    ("Windows", "cyrillic"):  ["segoeui.ttf", "arial.ttf", "times.ttf"],
    ("Darwin",  "cyrillic"):  [".SFNSText.ttf", "Helvetica.ttc"],
    ("Linux",   "cyrillic"):  ["DejaVuSans.ttf", "NotoSans-Regular.ttf"],

    # ── Latin (default) ──
    ("Windows", "latin"):    ["segoeui.ttf", "arial.ttf", "calibri.ttf"],
    ("Darwin",  "latin"):    [".SFNSText.ttf", "Helvetica.ttc"],
    ("Linux",   "latin"):    ["DejaVuSans.ttf", "NotoSans-Regular.ttf", "LiberationSans-Regular.ttf"],
}

_OS_NAME = platform.system()  # "Windows", "Darwin", "Linux"


def get_font_for_text(text: str, size: int = 15) -> ImageFont.FreeTypeFont:
    """Select the best available font for displaying the given text.

    Detects the dominant Unicode script of the text, maps it to an
    ordered list of OS-specific font candidates, and tries each
    until one loads successfully.

    Args:
        text: The text that will be displayed.
        size: Font size in points.

    Returns:
        A PIL ImageFont suitable for rendering the text.
    """
    script = detect_script(text)
    cache_key = (_OS_NAME, script, size)

    if cache_key in _font_cache:
        return _font_cache[cache_key]

    # Get candidate font list for this OS + script
    candidates = _FONT_MAP.get((_OS_NAME, script), [])

    # Also append generic fallbacks
    fallbacks = _FONT_MAP.get((_OS_NAME, "latin"), [])
    all_candidates = candidates + [f for f in fallbacks if f not in candidates]

    font = None
    for font_name in all_candidates:
        try:
            font = ImageFont.truetype(font_name, size)
            logger.debug(f"Font resolved: script={script}, font={font_name}")
            break
        except (IOError, OSError):
            continue

    if font is None:
        logger.debug(f"No TrueType font found for script={script}, using default.")
        font = ImageFont.load_default()

    _font_cache[cache_key] = font
    return font


# ── Font Cache ──────────────────────────────────────────────────

_font_cache: dict = {}


class FileManager:
    """Handles all interactions with the file system via dialogs."""

    def ask_for_files(self) -> List[str]:
        """Opens a dialog to select multiple PDF files.

        Returns:
            A list of selected absolute file paths.
        """
        files = filedialog.askopenfilenames(
            title="Select PDF files",
            filetypes=[("PDF files", "*.pdf")]
        )
        return list(files)

    def ask_for_folder(self) -> Optional[str]:
        """Opens a dialog to select a single folder.

        Returns:
            The selected folder path, or None if canceled.
        """
        folder = filedialog.askdirectory(
            title="Select a folder containing PDFs"
        )
        return folder if folder else None

    def ask_for_output_dir(self) -> Optional[str]:
        """Opens a dialog to select the output directory.

        Returns:
            The selected output directory path, or None if canceled.
        """
        directory = filedialog.askdirectory(
            title="Select a folder to save the results"
        )
        return directory if directory else None


class ThumbnailManager:
    """Handles creation and manipulation of thumbnail images.

    Uses Unicode script detection to select the correct system font
    for rendering non-Latin text in thumbnails.
    """

    def _get_font(self, font_size: int = 15, text: str = "") -> ImageFont.FreeTypeFont:
        """Load the best font for the given text with caching.

        If text is provided, uses `get_font_for_text()` for script-aware
        selection. Otherwise falls back to OS default Latin font.

        Args:
            font_size: The desired font size in points.
            text: Optional text to determine the best font for.

        Returns:
            A PIL ImageFont. Falls back to the default bitmap font if
            no TrueType fonts are found.
        """
        if text:
            return get_font_for_text(text, font_size)

        # No text provided — use generic Latin font
        return get_font_for_text("A", font_size)

    def create_image_thumbnail(
        self, pil_img: Image.Image, size: Tuple[int, int] = (100, 100)
    ) -> ImageTk.PhotoImage:
        """Creates a Tkinter-compatible thumbnail from a PIL image.

        Args:
            pil_img: The source PIL Image.
            size: The maximum size of the thumbnail.

        Returns:
            A Tkinter PhotoImage object.
        """
        img_copy = pil_img.copy()
        img_copy.thumbnail(size, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(img_copy)

    def create_text_thumbnail(
        self, text: str, size: Tuple[int, int] = (200, 50)
    ) -> ImageTk.PhotoImage:
        """Creates a Tkinter-compatible thumbnail image from a text string.

        Detects the text's dominant Unicode script and selects the
        appropriate OS font to ensure correct rendering of CJK,
        Arabic, Cyrillic, Thai, and other scripts.

        Args:
            text: The text to display on the thumbnail.
            size: The size of the thumbnail image.

        Returns:
            A Tkinter PhotoImage object.
        """
        img = Image.new('RGB', size, color='white')
        draw = ImageDraw.Draw(img)

        # Select font based on text content
        font = get_font_for_text(text, 15)

        # Truncate text if it's too long for the thumbnail
        display_text = (text[:25] + '…') if len(text) > 25 else text
        display_text = display_text.replace('\n', ' ')

        # Draw with detected font
        draw.text((10, 10), display_text, fill='black', font=font)

        # Add script indicator badge (small text in bottom-right)
        script = detect_script(text)
        if script != "latin":
            badge_font = get_font_for_text("A", 9)  # Latin font for badge
            badge_text = script.upper()[:3]
            draw.text((size[0] - 30, size[1] - 15), badge_text,
                      fill='#888888', font=badge_font)

        return ImageTk.PhotoImage(img)


class ConfigManager:
    """Persists user preferences (recent paths, settings) to disk."""

    def __init__(self, config_file: Path = CONFIG_FILE):
        self.config_file = config_file
        self._data: dict = {}
        self._load()

    def _load(self):
        """Load config from disk if it exists."""
        try:
            if self.config_file.exists():
                self._data = json.loads(self.config_file.read_text(encoding="utf-8"))
                logger.debug(f"Loaded config from {self.config_file}")
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not load config: {e}")
            self._data = {}

    def save(self):
        """Write current config to disk."""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            self.config_file.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except IOError as e:
            logger.warning(f"Could not save config: {e}")

    def get(self, key: str, default=None):
        """Get an arbitrary config value."""
        return self._data.get(key, default)

    def set(self, key: str, value):
        """Set an arbitrary config value and persist."""
        self._data[key] = value
        self.save()

    @property
    def recent_input_dir(self) -> Optional[str]:
        return self._data.get("recent_input_dir")

    @recent_input_dir.setter
    def recent_input_dir(self, value: str):
        self._data["recent_input_dir"] = value
        self.save()

    @property
    def recent_output_dir(self) -> Optional[str]:
        return self._data.get("recent_output_dir")

    @recent_output_dir.setter
    def recent_output_dir(self, value: str):
        self._data["recent_output_dir"] = value
        self.save()

    @property
    def last_suffix(self) -> str:
        return self._data.get("last_suffix", "_removed")

    @last_suffix.setter
    def last_suffix(self, value: str):
        self._data["last_suffix"] = value
        self.save()

    @property
    def last_threshold(self) -> int:
        return self._data.get("last_threshold", 80)

    @last_threshold.setter
    def last_threshold(self, value: int):
        self._data["last_threshold"] = value
        self.save()