# Tests for identifier.py
"""Unit tests for watermark identification strategies."""

import pytest
from unittest.mock import MagicMock

import fitz
import identifier
from tests.conftest import FakeDocument, FakePage


class TestFindByCommonality:
    """Tests for the commonality-based image detection."""

    def test_raises_on_invalid_doc_type(self):
        """Should raise TypeError if doc is not fitz.Document."""
        with pytest.raises(TypeError):
            identifier.find_by_commonality("not_a_document")

    def test_empty_document_returns_empty(self):
        """Should return empty list for zero-page document."""
        doc = FakeDocument(pages=[])
        result = identifier.find_by_commonality(doc)
        assert result == []

    def test_common_xrefs_detected(self, sample_doc):
        """Should detect images appearing on 80%+ of pages."""
        result = identifier.find_by_commonality(sample_doc, min_page_ratio=0.8)
        assert 100 in result
        assert 200 not in result

    def test_low_threshold_finds_more(self, sample_doc):
        """Should find more candidates with lower threshold."""
        result = identifier.find_by_commonality(sample_doc, min_page_ratio=0.1)
        assert 100 in result
        assert 200 in result


class TestFindByTransparency:
    """Tests for the transparency-based detection."""

    def test_returns_list(self):
        """Should always return a list."""
        doc = FakeDocument(pages=[])
        result = identifier.find_by_transparency(doc)
        assert isinstance(result, list)


class TestFindTextByKeywords:
    """Tests for keyword-based text watermark detection."""

    def test_empty_keywords_returns_empty(self):
        """Should return empty list when no keywords provided."""
        doc = FakeDocument(pages=[])
        result = identifier.find_text_by_keywords(doc, [])
        assert result == []

    def test_keyword_match_found(self, text_doc):
        """Should find text blocks containing the keyword."""
        result = identifier.find_text_by_keywords(text_doc, ["CONFIDENTIAL"])
        assert len(result) > 0
        assert result[0]['text'] == "CONFIDENTIAL"

    def test_keyword_not_found(self, text_doc):
        """Should return empty when keyword not in any block."""
        result = identifier.find_text_by_keywords(text_doc, ["NONEXISTENT"])
        assert result == []


class TestFindTextByPosition:
    """Tests for position-based text repetition detection."""

    def test_single_page_returns_empty(self):
        """Should return empty for single-page documents."""
        doc = FakeDocument(pages=[FakePage()])
        result = identifier.find_text_by_position(doc)
        assert result == []

    def test_detects_repeated_text(self):
        """Should detect text appearing at same position across pages."""
        pages = []
        for i in range(10):
            blocks = [(50.0, 700.0, 200.0, 720.0, "WATERMARK", 0, 0)]
            pages.append(FakePage(text_blocks=blocks, page_number=i))
        doc = FakeDocument(pages=pages)
        result = identifier.find_text_by_position(doc, min_page_ratio=0.8)
        assert len(result) > 0


class TestFindWatermarkCandidates:
    """Tests for the strategy dispatcher."""

    def test_invalid_strategy_raises(self):
        """Should raise ValueError for unknown strategy."""
        doc = FakeDocument(pages=[])
        with pytest.raises(ValueError, match="Unknown strategy"):
            identifier.find_watermark_candidates(doc, strategy="nonexistent")

    def test_commonality_strategy(self, sample_doc):
        """Should dispatch to find_by_commonality."""
        result = identifier.find_watermark_candidates(
            sample_doc, strategy='commonality', min_page_ratio=0.8
        )
        assert 100 in result

    def test_text_keywords_strategy(self, text_doc):
        """Should dispatch to find_text_by_keywords."""
        result = identifier.find_watermark_candidates(
            text_doc, strategy='text_keywords', keywords=["CONFIDENTIAL"]
        )
        assert len(result) > 0
