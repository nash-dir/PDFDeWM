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
GUI logic, such as file dialog interactions and image manipulation.
"""

from tkinter import filedialog
from typing import List, Optional, Tuple

from PIL import Image, ImageTk, ImageDraw, ImageFont


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
    """Handles creation and manipulation of thumbnail images."""

    def create_image_thumbnail(self, pil_img: Image.Image, size: Tuple[int, int] = (100, 100)) -> ImageTk.PhotoImage:
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

    def create_text_thumbnail(self, text: str, size: Tuple[int, int] = (200, 50)) -> ImageTk.PhotoImage:
        """Creates a Tkinter-compatible thumbnail image from a text string.

        Args:
            text: The text to display on the thumbnail.
            size: The size of the thumbnail image.

        Returns:
            A Tkinter PhotoImage object.
        """
        img = Image.new('RGB', size, color='white')
        draw = ImageDraw.Draw(img)
        font_size = 15

        try:
            # 1. Prioritize Malgun Gothic (for Korean & English)
            font = ImageFont.truetype("malgun.ttf", font_size)
            print("Using font: malgun.ttf")
        except IOError:
            try:
                # 2. Fallback to Arial for general Unicode support
                font = ImageFont.truetype("arial.ttf", font_size)
                print("Using font: arial.ttf (Malgun Gothic not found)")
            except IOError:
                # 3. Final fallback to the basic default font
                print("Warning: Neither Malgun Gothic nor Arial found. Using default font.")
                font = ImageFont.load_default()

        # Truncate text if it's too long for the thumbnail
        display_text = (text[:25] + '...') if len(text) > 25 else text
        draw.text((10, 10), display_text.replace('\n', ' '), fill='black', font=font)

        return ImageTk.PhotoImage(img)