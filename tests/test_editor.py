# Tests for editor.py
"""Unit tests for PDF editing and watermark removal functions."""

import re
import pytest
from unittest.mock import MagicMock

import fitz
import editor
from tests.conftest import FakeDocument, FakePage


class TestDecodeContentStream:
    """Tests for stream encoding/decoding helpers."""

    def test_utf8_decode(self):
        """Should decode valid UTF-8 bytes."""
        result = editor._decode_content_stream(b"Hello World")
        assert result == "Hello World"

    def test_latin1_fallback(self):
        """Should fall back to latin-1 for non-UTF-8 bytes."""
        result = editor._decode_content_stream(b"\xff\xfe")
        assert isinstance(result, str)

    def test_encode_roundtrip(self):
        """Should encode back to bytes."""
        original = "q /Im1 Do Q"
        encoded = editor._encode_content_stream(original)
        assert isinstance(encoded, bytes)
        assert b"/Im1" in encoded


class TestCleanContentStreams:
    """Tests for the regex-based content stream cleaning."""

    def test_no_names_does_nothing(self):
        """Should return early when no image names provided."""
        doc = FakeDocument(pages=[])
        editor.clean_content_streams(doc, [])
        # No error raised

    def test_regex_non_greedy(self):
        """Validate the regex pattern does not over-match nested q/Q blocks."""
        content = "q /Im1 Do Q other_content q /Im1 Do Q"
        names = ["/Im1"]
        names_pattern = "|".join(re.escape(n) for n in names)
        pattern = re.compile(
            rf"q\s[^Q]*?/({names_pattern})\s+Do\s*?[^q]*?Q",
            flags=re.DOTALL
        )
        result = pattern.sub("", content)
        assert "other_content" in result.strip()

    def test_non_watermark_preserved(self):
        """Non-watermark image commands should not be removed."""
        content = "q /Im1 Do Q q /Im2 Do Q"
        names = ["/Im1"]
        names_pattern = "|".join(re.escape(n) for n in names)
        pattern = re.compile(
            rf"q\s[^Q]*?/({names_pattern})\s+Do\s*?[^q]*?Q",
            flags=re.DOTALL
        )
        result = pattern.sub("", content)
        assert "/Im2" in result


class TestAddTextRedactions:
    """Tests for text redaction annotation."""

    def test_empty_candidates_does_nothing(self):
        """Should return early for empty candidates list."""
        doc = MagicMock(spec=fitz.Document)
        editor.add_text_redactions(doc, [])
        doc.load_page.assert_not_called()

    def test_groups_by_page(self):
        """Should group redactions by page number."""
        doc = MagicMock(spec=fitz.Document)
        mock_page = MagicMock()
        doc.load_page.return_value = mock_page

        candidates = [
            {'page': 0, 'bbox': fitz.Rect(10, 10, 100, 30)},
            {'page': 0, 'bbox': fitz.Rect(10, 40, 100, 60)},
            {'page': 1, 'bbox': fitz.Rect(10, 10, 100, 30)},
        ]
        editor.add_text_redactions(doc, candidates)
        assert doc.load_page.call_count == 2


class TestDeleteObjectsAndSmasks:
    """Tests for object deletion."""

    def test_deletes_image_xref(self):
        """Should delete the specified xref."""
        doc = MagicMock(spec=fitz.Document)
        doc.xref_object.return_value = "/Subtype /Image"
        result = editor.delete_objects_and_smasks(doc, [42])
        assert result == 1
        doc.update_object.assert_called_with(42, "null")

    def test_deletes_smask_too(self):
        """Should also delete SMask if present."""
        doc = MagicMock(spec=fitz.Document)
        doc.xref_object.return_value = "/Subtype /Image /SMask 99 0 R"
        result = editor.delete_objects_and_smasks(doc, [42])
        assert result == 2
