"""Extract a single survey and export it to an Excel file.

This module is the entry-point for individual-survey extraction.  It
orchestrates the API client, response processor, and Excel exporter
without any web-framework dependencies.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from sm_excel.client.survey_api import SurveyMonkeyClient
from sm_excel.exporters.excel_exporter import export_dataframes_to_excel, safe_sheet_name
from sm_excel.processors.response_processor import (
    parse_survey,
    parse_trend_data,
    survey_structure_to_dataframe,
    trends_to_dataframe,
    pivot_trends_wide,
)

logger = logging.getLogger(__name__)


def fetch_survey_structure(
    client: SurveyMonkeyClient,
    survey_id: str,
) -> tuple[Any, pd.DataFrame]:
    """Download a survey's full structure and return both the model and a DataFrame.

    Args:
        client:    Authenticated :class:`~sm_excel.client.survey_api.SurveyMonkeyClient`.
        survey_id: SurveyMonkey numeric survey identifier.

    Returns:
        A 2-tuple of:
        - :class:`~sm_excel.models.Survey` dataclass instance.
        - DataFrame describing the question structure.
    """
    raw = client.get_survey_details(survey_id)
    survey = parse_survey(raw)
    structure_df = survey_structure_to_dataframe(survey)
    return survey, structure_df


def fetch_survey_trends(
    client: SurveyMonkeyClient,
    survey: Any,
    trend_params: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Download trend data for every page of *survey* and return a merged DataFrame.

    Args:
        client:       Authenticated API client.
        survey:       Parsed :class:`~sm_excel.models.Survey` instance.
        trend_params: Optional query parameters forwarded to the trends endpoint
                      (e.g. ``{"start_date": "2024-01-01", "granularity": "month"}``).

    Returns:
        Wide-format trends DataFrame (one row per period_start, one column
        per question/choice combination).  Returns an empty DataFrame if no
        trend data is available.
    """
    all_data_points = []

    for page in survey.pages:
        try:
            raw_trends = client.get_trends(
                survey.survey_id, page.page_id, params=trend_params
            )
            data_points = parse_trend_data(raw_trends, survey)
            all_data_points.extend(data_points)
        except Exception:
            logger.warning(
                "Could not fetch trends for survey %s / page %s",
                survey.survey_id,
                page.page_id,
                exc_info=True,
            )

    if not all_data_points:
        return pd.DataFrame()

    long_df = trends_to_dataframe(all_data_points)
    return pivot_trends_wide(long_df)


def extract_individual_survey(
    survey_id: str,
    output_dir: str | Path = "./output",
    trend_params: dict[str, Any] | None = None,
    client: SurveyMonkeyClient | None = None,
) -> Path:
    """End-to-end extraction of a single survey to an Excel file.

    Sheets produced:
    - **structure** – one row per question (metadata).
    - **trends**    – wide-format trend data per period (if available).

    Args:
        survey_id:  SurveyMonkey numeric survey identifier.
        output_dir: Directory where the Excel file will be written.
        trend_params: Optional query parameters for the trends endpoint.
        client:     Optional pre-built client (useful for testing / reuse).

    Returns:
        :class:`pathlib.Path` of the written Excel file.
    """
    client = client or SurveyMonkeyClient()
    output_dir = Path(output_dir)

    logger.info("Starting individual extraction for survey %s", survey_id)

    survey, structure_df = fetch_survey_structure(client, survey_id)
    trends_df = fetch_survey_trends(client, survey, trend_params)

    sheets: dict[str, pd.DataFrame] = {
        "structure": structure_df,
    }
    if not trends_df.empty:
        sheets["trends"] = trends_df

    filename = f"survey_{survey_id}.xlsx"
    out_path = export_dataframes_to_excel(sheets, output_dir, filename)
    logger.info("Individual survey exported to %s", out_path)
    return out_path
