"""Tests for sm_excel.exporters.excel_exporter."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from sm_excel.exporters.excel_exporter import (
    ensure_directory,
    export_dataframe_to_excel,
    export_dataframes_to_excel,
    safe_file_name,
    safe_sheet_name,
)


class TestEnsureDirectory:
    def test_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "new" / "nested"
            result = ensure_directory(target)
            assert result.is_dir()

    def test_existing_directory_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = ensure_directory(tmp)
            assert result.is_dir()


class TestSafeFileName:
    def test_removes_illegal_chars(self):
        # ':' and '"' are both illegal; the space between them produces extra '_'
        result = safe_file_name('survey: "test"')
        assert ":" not in result
        assert '"' not in result
        assert result.startswith("survey")

    def test_spaces_replaced(self):
        assert safe_file_name("my survey") == "my_survey"

    def test_truncation(self):
        long_name = "a" * 300
        assert len(safe_file_name(long_name)) <= 200


class TestSafeSheetName:
    def test_truncates_to_31(self):
        long = "A" * 50
        assert len(safe_sheet_name(long)) <= 31

    def test_removes_illegal_chars(self):
        assert "?" not in safe_sheet_name("Sheet?Name")
        assert "[" not in safe_sheet_name("Sheet[1]")


class TestExportDataframeToExcel:
    def test_file_created(self):
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        with tempfile.TemporaryDirectory() as tmp:
            path = export_dataframe_to_excel(df, tmp, "test.xlsx")
            assert path.exists()
            assert path.suffix == ".xlsx"

    def test_data_readable(self):
        df = pd.DataFrame({"col1": ["x", "y"]})
        with tempfile.TemporaryDirectory() as tmp:
            path = export_dataframe_to_excel(df, tmp, "out.xlsx")
            read_back = pd.read_excel(path)
            assert list(read_back["col1"]) == ["x", "y"]


class TestExportDataframesToExcel:
    def test_multiple_sheets(self):
        sheets = {
            "Sheet A": pd.DataFrame({"x": [1]}),
            "Sheet B": pd.DataFrame({"y": [2]}),
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = export_dataframes_to_excel(sheets, tmp, "multi.xlsx")
            assert path.exists()
            xl = pd.ExcelFile(path)
            assert len(xl.sheet_names) == 2

    def test_empty_sheets_raises(self):
        with pytest.raises(ValueError):
            export_dataframes_to_excel({}, "/tmp", "empty.xlsx")
