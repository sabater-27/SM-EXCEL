"""Utilities for exporting DataFrames to Excel files.

All functions are stateless helpers; they accept DataFrames and file-system
paths and produce ``*.xlsx`` files using ``openpyxl`` via pandas.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_MAX_EXCEL_SHEET_NAME_LEN = 31  # Excel hard limit


def ensure_directory(path: str | Path) -> Path:
    """Create *path* (and all parents) if it does not exist.

    Args:
        path: Directory path to create.

    Returns:
        Resolved :class:`pathlib.Path` object.
    """
    p = Path(path).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_file_name(name: str, max_len: int = 200, suffix: str = "") -> str:
    """Sanitise *name* so it is safe to use as part of a file-system name.

    Rules applied:
    - Strip leading/trailing whitespace.
    - Replace characters that are illegal in most file-system paths with ``_``.
    - Truncate to *max_len* characters (before appending *suffix*).

    Args:
        name:    Raw name string (e.g. survey title).
        max_len: Maximum allowed character length (default 200).
        suffix:  Optional suffix to append (e.g. ``".xlsx"``).

    Returns:
        Cleaned, filesystem-safe name string.
    """
    name = name.strip()
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    name = re.sub(r"\s+", "_", name)
    name = name[:max_len]
    return name + suffix


def safe_sheet_name(name: str) -> str:
    """Sanitise *name* to comply with Excel sheet-name restrictions.

    Excel disallows the characters ``\\ / ? * [ ]`` in sheet names and limits
    them to 31 characters.

    Args:
        name: Raw sheet name candidate.

    Returns:
        Excel-safe sheet name (≤ 31 characters).
    """
    name = re.sub(r"[\\/?*\[\]:]", "_", name).strip()
    return name[:_MAX_EXCEL_SHEET_NAME_LEN]


def export_dataframe_to_excel(
    df: pd.DataFrame,
    output_dir: str | Path,
    filename: str,
    sheet_name: str = "Sheet1",
    index: bool = False,
) -> Path:
    """Write a single DataFrame to an Excel file.

    Args:
        df:         DataFrame to export.
        output_dir: Target directory (created if absent).
        filename:   Output file name (e.g. ``"survey_123.xlsx"``).
        sheet_name: Worksheet name inside the workbook.
        index:      Whether to write the DataFrame index.

    Returns:
        :class:`pathlib.Path` of the written file.
    """
    out_dir = ensure_directory(output_dir)
    out_path = out_dir / filename

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=safe_sheet_name(sheet_name), index=index)

    logger.info("Exported %d rows to %s", len(df), out_path)
    return out_path


def export_dataframes_to_excel(
    sheets: dict[str, pd.DataFrame],
    output_dir: str | Path,
    filename: str,
    index: bool = False,
) -> Path:
    """Write multiple DataFrames to a single Excel workbook.

    Each key in *sheets* becomes a worksheet name; the value is the DataFrame
    written to that sheet.  Sheet names are automatically sanitised to comply
    with Excel restrictions.

    Args:
        sheets:     Mapping of sheet name → DataFrame.
        output_dir: Target directory (created if absent).
        filename:   Output file name (e.g. ``"folder_report.xlsx"``).
        index:      Whether to write DataFrame indices.

    Returns:
        :class:`pathlib.Path` of the written file.

    Raises:
        ValueError: if *sheets* is empty.
    """
    if not sheets:
        raise ValueError("sheets dict must contain at least one entry.")

    out_dir = ensure_directory(output_dir)
    out_path = out_dir / filename

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        for raw_name, df in sheets.items():
            sheet = safe_sheet_name(raw_name)
            df.to_excel(writer, sheet_name=sheet, index=index)
            logger.debug("  → sheet '%s': %d rows", sheet, len(df))

    logger.info("Workbook with %d sheet(s) exported to %s", len(sheets), out_path)
    return out_path
