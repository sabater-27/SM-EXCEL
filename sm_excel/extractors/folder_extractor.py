"""Extract all surveys in a SurveyMonkey folder and export to Excel.

Surveys within the folder are grouped by structural compatibility:

- Surveys that share the same question structure are consolidated into a
  **single Excel file** (one sheet per survey + a merged sheet).
- Surveys with a unique or incompatible structure are exported **individually**.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from sm_excel.client.survey_api import SurveyMonkeyClient
from sm_excel.exporters.excel_exporter import (
    export_dataframes_to_excel,
    safe_file_name,
)
from sm_excel.processors.response_processor import (
    merge_dataframes,
    parse_survey,
    parse_trend_data,
    pivot_trends_wide,
    survey_structure_to_dataframe,
    trends_to_dataframe,
)
from sm_excel.processors.structure_comparator import group_surveys_by_structure

logger = logging.getLogger(__name__)


def get_folder_survey_ids(
    client: SurveyMonkeyClient,
    folder_id: str,
) -> list[str]:
    """Return the list of survey IDs that belong to *folder_id*.

    Args:
        client:    Authenticated API client.
        folder_id: SurveyMonkey folder/collection identifier.

    Returns:
        List of survey ID strings.
    """
    summaries = client.get_folder_surveys(folder_id)
    ids = [str(s["id"]) for s in summaries if "id" in s]
    logger.info("Found %d surveys in folder %s", len(ids), folder_id)
    return ids


def download_all_surveys(
    client: SurveyMonkeyClient,
    survey_ids: list[str],
) -> list[Any]:
    """Download and parse every survey in *survey_ids*.

    Surveys that fail to download are logged and skipped.

    Args:
        client:     Authenticated API client.
        survey_ids: List of survey ID strings.

    Returns:
        List of successfully parsed :class:`~sm_excel.models.Survey` instances.
    """
    surveys = []
    for sid in survey_ids:
        try:
            raw = client.get_survey_details(sid)
            surveys.append(parse_survey(raw))
        except Exception:
            logger.warning(
                "Failed to download survey %s – skipping.", sid, exc_info=True
            )
    return surveys


def _fetch_trends_for_survey(
    client: SurveyMonkeyClient,
    survey: Any,
    trend_params: dict[str, Any] | None,
) -> pd.DataFrame:
    """Internal helper – download and pivot trends for a single survey."""
    all_points = []
    for page in survey.pages:
        try:
            raw = client.get_trends(survey.survey_id, page.page_id, params=trend_params)
            all_points.extend(parse_trend_data(raw, survey))
        except Exception:
            logger.warning(
                "Trends unavailable for survey %s / page %s",
                survey.survey_id,
                page.page_id,
                exc_info=True,
            )
    if not all_points:
        return pd.DataFrame()
    return pivot_trends_wide(trends_to_dataframe(all_points))


def export_consolidated_group(
    client: SurveyMonkeyClient,
    surveys: list[Any],
    structure_hash: str,
    output_dir: Path,
    trend_params: dict[str, Any] | None,
) -> Path:
    """Export a group of structurally compatible surveys into one Excel file.

    Sheets produced:
    - One sheet per individual survey named after its title.
    - A **consolidated_trends** sheet with all trend data merged.

    Args:
        client:         Authenticated API client.
        surveys:        List of compatible :class:`~sm_excel.models.Survey` instances.
        structure_hash: Hash string identifying this structural group.
        output_dir:     Target directory.
        trend_params:   Optional query parameters for the trends endpoint.

    Returns:
        :class:`pathlib.Path` of the written Excel file.
    """
    sheets: dict[str, pd.DataFrame] = {}
    all_trends: list[pd.DataFrame] = []

    for survey in surveys:
        sheet_name = safe_file_name(survey.title, max_len=31)
        structure_df = survey_structure_to_dataframe(survey)
        sheets[sheet_name] = structure_df

        trends_df = _fetch_trends_for_survey(client, survey, trend_params)
        if not trends_df.empty:
            trends_df.insert(0, "survey_title", survey.title)
            trends_df.insert(0, "survey_id", survey.survey_id)
            all_trends.append(trends_df)

    if all_trends:
        sheets["consolidated_trends"] = merge_dataframes(all_trends)

    filename = f"group_{structure_hash}.xlsx"
    out_path = export_dataframes_to_excel(sheets, output_dir, filename)
    logger.info(
        "Consolidated group %s (%d surveys) exported to %s",
        structure_hash,
        len(surveys),
        out_path,
    )
    return out_path


def export_individual_survey(
    client: SurveyMonkeyClient,
    survey: Any,
    output_dir: Path,
    trend_params: dict[str, Any] | None,
) -> Path:
    """Export a single survey as an independent Excel file.

    Used for surveys that do not share their structure with any other survey
    in the folder.

    Args:
        client:       Authenticated API client.
        survey:       Parsed :class:`~sm_excel.models.Survey`.
        output_dir:   Target directory.
        trend_params: Optional query parameters for the trends endpoint.

    Returns:
        :class:`pathlib.Path` of the written Excel file.
    """
    structure_df = survey_structure_to_dataframe(survey)
    trends_df = _fetch_trends_for_survey(client, survey, trend_params)

    sheets: dict[str, pd.DataFrame] = {"structure": structure_df}
    if not trends_df.empty:
        sheets["trends"] = trends_df

    filename = f"survey_{survey.survey_id}.xlsx"
    out_path = export_dataframes_to_excel(sheets, output_dir, filename)
    logger.info("Individual survey %s exported to %s", survey.survey_id, out_path)
    return out_path


def extract_folder_surveys(
    folder_id: str,
    output_dir: str | Path = "./output",
    trend_params: dict[str, Any] | None = None,
    client: SurveyMonkeyClient | None = None,
) -> list[Path]:
    """End-to-end extraction of all surveys in a folder.

    Steps:
    1. Retrieve all survey IDs in the folder.
    2. Download and parse each survey's structure.
    3. Group surveys by structural compatibility.
    4. For each group with ≥ 2 surveys → export a consolidated Excel.
    5. For each singleton group → export an individual Excel.

    Args:
        folder_id:    SurveyMonkey folder identifier.
        output_dir:   Directory where Excel files will be written.
        trend_params: Optional query parameters forwarded to the trends endpoint.
        client:       Optional pre-built client.

    Returns:
        List of :class:`pathlib.Path` objects for every Excel file written.
    """
    client = client or SurveyMonkeyClient()
    output_dir = Path(output_dir)

    logger.info("Starting folder extraction for folder %s", folder_id)

    survey_ids = get_folder_survey_ids(client, folder_id)
    if not survey_ids:
        logger.warning("No surveys found in folder %s", folder_id)
        return []

    surveys = download_all_surveys(client, survey_ids)
    if not surveys:
        logger.warning("All survey downloads failed for folder %s", folder_id)
        return []

    groups = group_surveys_by_structure(surveys)
    logger.info(
        "Surveys in folder %s grouped into %d structural group(s)",
        folder_id,
        len(groups),
    )

    output_paths: list[Path] = []

    for hash_key, group_surveys in groups.items():
        if len(group_surveys) > 1:
            path = export_consolidated_group(
                client, group_surveys, hash_key, output_dir, trend_params
            )
        else:
            path = export_individual_survey(
                client, group_surveys[0], output_dir, trend_params
            )
        output_paths.append(path)

    return output_paths
