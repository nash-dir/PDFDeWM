# Tests for core.py
"""Unit tests for the core scanning and processing logic."""

import pytest
import threading
from pathlib import Path

import core


class TestCheckFileSize:
    """Tests for file size validation."""

    def test_small_file_passes(self, tmp_path):
        """Should return True for files within the limit."""
        small_file = tmp_path / "small.pdf"
        small_file.write_bytes(b"x" * 100)
        assert core._check_file_size(str(small_file)) is True

    def test_oversized_file_rejected(self, tmp_path):
        """Should return False for files exceeding the limit."""
        big_file = tmp_path / "big.pdf"
        big_file.write_bytes(b"x" * 100)
        assert core._check_file_size(str(big_file), max_bytes=50) is False

    def test_custom_limit(self, tmp_path):
        """Should respect custom max_bytes parameter."""
        f = tmp_path / "medium.pdf"
        f.write_bytes(b"x" * 1000)
        assert core._check_file_size(str(f), max_bytes=2000) is True
        assert core._check_file_size(str(f), max_bytes=500) is False


class TestScanFilesForWatermarks:
    """Tests for the main scanning function."""

    def test_empty_file_list(self):
        """Should return empty dict for no files."""
        result = core.scan_files_for_watermarks([], 0.8)
        assert result == {}

    def test_cancel_flag_stops_scan(self, tmp_pdf):
        """Should stop scanning when cancel flag is set."""
        cancel = threading.Event()
        cancel.set()
        result = core.scan_files_for_watermarks([tmp_pdf], 0.8, cancel_flag=cancel)
        assert result == {}

    def test_invalid_file_handled(self, tmp_path):
        """Should gracefully handle non-PDF files."""
        fake = tmp_path / "fake.pdf"
        fake.write_text("not a real pdf")
        result = core.scan_files_for_watermarks([str(fake)], 0.8)
        assert isinstance(result, dict)

    def test_scan_real_pdf(self, tmp_pdf):
        """Should scan a real PDF without errors."""
        result = core.scan_files_for_watermarks([tmp_pdf], 0.8)
        assert isinstance(result, dict)


class TestProcessAndRemoveWatermarks:
    """Tests for the removal pipeline."""

    def test_invalid_output_dir(self, tmp_pdf):
        """Should handle non-existent output directory."""
        core.process_and_remove_watermarks(
            tmp_pdf, "/nonexistent/dir", {}, "_clean"
        )

    def test_skip_existing_no_overwrite(self, tmp_pdf, tmp_output_dir):
        """Should skip if output exists and overwrite=False."""
        stem = Path(tmp_pdf).stem
        existing = Path(tmp_output_dir) / f"{stem}_clean.pdf"
        existing.write_bytes(b"existing")

        core.process_and_remove_watermarks(
            tmp_pdf, tmp_output_dir, {}, "_clean", overwrite=False
        )
        assert existing.read_bytes() == b"existing"

    def test_processes_real_pdf(self, tmp_pdf, tmp_output_dir):
        """Should process a real PDF and produce output."""
        core.process_and_remove_watermarks(
            tmp_pdf, tmp_output_dir, {}, "_clean", overwrite=True
        )
        stem = Path(tmp_pdf).stem
        output = Path(tmp_output_dir) / f"{stem}_clean.pdf"
        assert output.exists()


class TestCopyUnprocessedFile:
    """Tests for the file copy function."""

    def test_copies_file(self, tmp_pdf, tmp_output_dir):
        """Should copy the file to the output directory."""
        core.copy_unprocessed_file(tmp_pdf, tmp_output_dir)
        name = Path(tmp_pdf).name
        assert (Path(tmp_output_dir) / name).exists()

    def test_skip_same_source_dest(self, tmp_pdf):
        """Should not copy if source == destination."""
        parent = str(Path(tmp_pdf).parent)
        core.copy_unprocessed_file(tmp_pdf, parent)
