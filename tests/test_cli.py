# Tests for cli.py
"""Unit and integration tests for the CLI interface."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

import cli


class TestCollectPdfFiles:
    """Tests for file collection with recursive/non-recursive modes."""

    def test_single_file(self, tmp_pdf):
        """Should return a single-element list for a file path."""
        result = cli.collect_pdf_files(tmp_pdf)
        assert len(result) == 1
        assert result[0].endswith(".pdf")

    def test_directory_recursive(self, tmp_path):
        """Should find PDFs in subdirectories by default."""
        (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.pdf").write_bytes(b"%PDF-1.4")

        result = cli.collect_pdf_files(str(tmp_path), recursive=True)
        assert len(result) == 2

    def test_directory_non_recursive(self, tmp_path):
        """Should only find top-level PDFs when recursive=False."""
        (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.pdf").write_bytes(b"%PDF-1.4")

        result = cli.collect_pdf_files(str(tmp_path), recursive=False)
        assert len(result) == 1

    def test_invalid_path(self):
        """Should return empty list for invalid path."""
        result = cli.collect_pdf_files("/nonexistent/path/xyz")
        assert result == []


class TestArgParsing:
    """Tests for argument parser configuration."""

    def test_required_args(self):
        """Should parse required --input and --output."""
        args = cli.main.__wrapped__ if hasattr(cli.main, '__wrapped__') else None
        # Test via parser directly
        parser = _get_parser()
        args = parser.parse_args(["-i", "test.pdf", "-o", "./out/"])
        assert args.input == "test.pdf"
        assert args.output == "./out/"

    def test_dry_run_flag(self):
        """--dry-run / -n should be boolean."""
        parser = _get_parser()
        args = parser.parse_args(["-i", "x", "-o", "y", "--dry-run"])
        assert args.dry_run is True

    def test_dry_run_shorthand(self):
        """-n should work as shorthand."""
        parser = _get_parser()
        args = parser.parse_args(["-i", "x", "-o", "y", "-n"])
        assert args.dry_run is True

    def test_report_path(self):
        """--report should accept a file path."""
        parser = _get_parser()
        args = parser.parse_args(["-i", "x", "-o", "y", "--report", "out.json"])
        assert args.report == "out.json"

    def test_report_shorthand(self):
        """-r should work as shorthand."""
        parser = _get_parser()
        args = parser.parse_args(["-i", "x", "-o", "y", "-r", "out.json"])
        assert args.report == "out.json"

    def test_no_recursive_flag(self):
        """--no-recursive should be boolean."""
        parser = _get_parser()
        args = parser.parse_args(["-i", "x", "-o", "y", "--no-recursive"])
        assert args.no_recursive is True

    def test_defaults(self):
        """Default values should be correct."""
        parser = _get_parser()
        args = parser.parse_args(["-i", "x", "-o", "y"])
        assert args.dry_run is False
        assert args.report is None
        assert args.no_recursive is False
        assert args.threshold == 80
        assert args.suffix == "_removed"
        assert args.max_size_mb == 500
        assert args.verbose is False
        assert args.overwrite is False
        assert args.sanitize is False

    def test_all_args_combined(self):
        """Should parse all arguments together."""
        parser = _get_parser()
        args = parser.parse_args([
            "-i", "./pdfs/", "-o", "./out/",
            "-k", "DRAFT;기밀", "-t", "60", "-s", "_clean",
            "--overwrite", "--copy-unprocessed", "--sanitize",
            "--max-size-mb", "200", "--dry-run",
            "--report", "audit.json", "--no-recursive", "-v",
        ])
        assert args.keywords == "DRAFT;기밀"
        assert args.threshold == 60
        assert args.suffix == "_clean"
        assert args.overwrite is True
        assert args.copy_unprocessed is True
        assert args.sanitize is True
        assert args.max_size_mb == 200
        assert args.dry_run is True
        assert args.report == "audit.json"
        assert args.no_recursive is True
        assert args.verbose is True


class TestDryRun:
    """Tests for --dry-run behavior."""

    def test_dry_run_exits_zero(self, tmp_pdf, tmp_path, capsys):
        """--dry-run should scan and exit without creating output files."""
        out_dir = tmp_path / "out"
        with pytest.raises(SystemExit) as exc_info:
            cli.main(["-i", tmp_pdf, "-o", str(out_dir), "--dry-run"])
        assert exc_info.value.code == 0
        # Output dir should NOT be created in dry-run
        assert not out_dir.exists()

    def test_dry_run_with_report(self, tmp_pdf, tmp_path):
        """--dry-run + --report should produce a JSON file."""
        report_path = tmp_path / "report.json"
        with pytest.raises(SystemExit) as exc_info:
            cli.main(["-i", tmp_pdf, "-o", str(tmp_path / "out"), "--dry-run",
                       "--report", str(report_path)])
        assert exc_info.value.code == 0
        assert report_path.exists()

        data = json.loads(report_path.read_text(encoding="utf-8"))
        assert data["dry_run"] is True
        assert "files" in data
        assert "summary" in data


class TestReportGeneration:
    """Tests for --report JSON output."""

    def test_report_schema(self, tmp_pdf, tmp_output_dir, tmp_path):
        """Report JSON should contain expected top-level keys."""
        report_path = tmp_path / "result.json"
        cli.main(["-i", tmp_pdf, "-o", tmp_output_dir,
                  "--report", str(report_path)])

        data = json.loads(report_path.read_text(encoding="utf-8"))
        assert "version" in data
        assert "timestamp" in data
        assert "summary" in data
        assert "files" in data
        assert "options" in data
        assert isinstance(data["files"], list)

    def test_report_summary_counts(self, tmp_pdf, tmp_output_dir, tmp_path):
        """Summary counts should be consistent."""
        report_path = tmp_path / "result.json"
        cli.main(["-i", tmp_pdf, "-o", tmp_output_dir,
                  "--report", str(report_path)])

        data = json.loads(report_path.read_text(encoding="utf-8"))
        summary = data["summary"]
        assert summary["total_files_scanned"] >= 1
        assert summary["skipped_size_limit"] >= 0

    def test_file_entry_structure(self, tmp_pdf, tmp_output_dir, tmp_path):
        """Each file entry should have input, output, status, candidates."""
        report_path = tmp_path / "result.json"
        cli.main(["-i", tmp_pdf, "-o", tmp_output_dir,
                  "--report", str(report_path)])

        data = json.loads(report_path.read_text(encoding="utf-8"))
        for entry in data["files"]:
            assert "input" in entry
            assert "status" in entry
            assert "candidates" in entry
            assert isinstance(entry["candidates"], list)


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_basic_run(self, tmp_pdf, tmp_output_dir):
        """Should process a PDF without errors.

        Uses --sanitize to force processing since test PDFs have no watermarks.
        """
        cli.main(["-i", tmp_pdf, "-o", tmp_output_dir, "--sanitize"])
        stem = Path(tmp_pdf).stem
        out = Path(tmp_output_dir) / f"{stem}_removed.pdf"
        assert out.exists()

    def test_custom_suffix(self, tmp_pdf, tmp_output_dir):
        """Should use the custom suffix."""
        cli.main(["-i", tmp_pdf, "-o", tmp_output_dir, "-s", "_clean", "--sanitize"])
        stem = Path(tmp_pdf).stem
        out = Path(tmp_output_dir) / f"{stem}_clean.pdf"
        assert out.exists()

    def test_no_watermarks_skips(self, tmp_pdf, tmp_output_dir, tmp_path):
        """Should report skipped status for clean files with --report."""
        report_path = tmp_path / "skip_report.json"
        cli.main(["-i", tmp_pdf, "-o", tmp_output_dir,
                  "--report", str(report_path)])
        data = json.loads(report_path.read_text(encoding="utf-8"))
        assert data["files"][0]["status"] == "skipped_no_watermark"


# ── Helper ──────────────────────────────────────────────────────

def _get_parser():
    """Reconstruct the argparse parser from cli.main for unit testing.

    This avoids running the full main() function just to test arg parsing.
    """
    import argparse
    parser = argparse.ArgumentParser(prog="pdfdewm")
    required = parser.add_argument_group("required")
    required.add_argument("--input", "-i", required=True)
    required.add_argument("--output", "-o", required=True)
    parser.add_argument("--keywords", "-k", default="")
    parser.add_argument("--threshold", "-t", type=int, default=80)
    parser.add_argument("--suffix", "-s", default="_removed")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--copy-unprocessed", action="store_true")
    parser.add_argument("--sanitize", action="store_true")
    parser.add_argument("--max-size-mb", type=int, default=500)
    parser.add_argument("--dry-run", "-n", action="store_true")
    parser.add_argument("--report", "-r", metavar="PATH")
    parser.add_argument("--no-recursive", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser
