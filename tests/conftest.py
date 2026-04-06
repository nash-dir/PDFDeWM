# PDFDeWM Test Configuration
"""Shared pytest fixtures for the PDFDeWM test suite."""

import pytest
from unittest.mock import MagicMock, PropertyMock

import fitz


class FakeDocument(fitz.Document):
    """A minimal fake of fitz.Document that passes isinstance checks.

    We subclass fitz.Document but override __init__ to skip any real
    file loading, and store mock pages for iteration.
    """

    def __init__(self, pages=None):
        # Do NOT call super().__init__() — it would try to open a file.
        self._pages = pages or []

    def __len__(self):
        return len(self._pages)

    def __iter__(self):
        return iter(self._pages)

    def close(self):
        pass


class FakePage:
    """A minimal fake for a fitz.Page."""

    def __init__(self, images=None, text_blocks=None, page_number=0):
        self._images = images or []
        self._text_blocks = text_blocks or []
        self.number = page_number
        self.xref = 999  # fake page xref

    def get_images(self, full=False):
        return self._images

    def get_text(self, mode="text"):
        if mode == "blocks":
            return self._text_blocks
        return ""

    def get_contents(self):
        return []


@pytest.fixture
def mock_doc():
    """Create a FakeDocument with no pages."""
    return FakeDocument(pages=[])


@pytest.fixture
def sample_pages():
    """Create FakePage list with watermark-like image xrefs.

    - Image xref 100 appears on all 10 pages (watermark).
    - Image xref 200 appears on only 2 pages (not watermark).
    """
    pages = []
    for i in range(10):
        if i < 2:
            images = [
                (100, 0, 0, 0, 0, 0, 0, 'Im1'),
                (200, 0, 0, 0, 0, 0, 0, 'Im2'),
            ]
        else:
            images = [
                (100, 0, 0, 0, 0, 0, 0, 'Im1'),
            ]
        pages.append(FakePage(images=images, page_number=i))
    return pages


@pytest.fixture
def sample_doc(sample_pages):
    """Create a FakeDocument with pre-configured sample pages."""
    return FakeDocument(pages=sample_pages)


@pytest.fixture
def text_doc():
    """Create a FakeDocument with text blocks for keyword testing."""
    pages = []
    for i in range(5):
        blocks = [
            (10.0, 20.0, 100.0, 40.0, "CONFIDENTIAL DOCUMENT\n", 0, 0),
            (10.0, 50.0, 100.0, 70.0, "Normal text content here\n", 0, 0),
        ]
        pages.append(FakePage(text_blocks=blocks, page_number=i))
    return FakeDocument(pages=pages)


@pytest.fixture
def tmp_pdf(tmp_path):
    """Create a minimal real PDF for integration tests."""
    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    for i in range(5):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i+1}")
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


@pytest.fixture
def tmp_output_dir(tmp_path):
    """Create a temporary output directory."""
    out = tmp_path / "output"
    out.mkdir()
    return str(out)
