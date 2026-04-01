"""Convert raw SurveyMonkey API responses into tidy pandas DataFrames.

All public functions are pure transformations: they accept raw Python
dicts / lists and return DataFrames.  No I/O or HTTP calls happen here.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd

from sm_excel.models import Choice, Page, Question, Survey, TrendDataPoint

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column-name utilities
# ---------------------------------------------------------------------------


def clean_column_name(name: str) -> str:
    """Normalise a raw string into a safe, lowercase column name.

    Rules applied:
    - Strip leading/trailing whitespace.
    - Lowercase everything.
    - Replace runs of non-alphanumeric characters with a single underscore.
    - Strip leading/trailing underscores.

    Args:
        name: Raw column name (e.g. question heading or key from the API).

    Returns:
        Cleaned column name string.
    """
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    return name.strip("_")


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Apply :func:`clean_column_name` to every column of *df*.

    Args:
        df: Input DataFrame (columns may have raw/user-facing names).

    Returns:
        New DataFrame with cleaned column names (original is not mutated).
    """
    df = df.copy()
    df.columns = [clean_column_name(str(c)) for c in df.columns]
    return df


# ---------------------------------------------------------------------------
# Model builders: raw dict → dataclass
# ---------------------------------------------------------------------------


def parse_choice(raw: dict[str, Any]) -> Choice:
    """Build a :class:`~sm_excel.models.Choice` from a raw API dict."""
    return Choice(
        choice_id=str(raw.get("id", "")),
        text=str(raw.get("text", "")),
        position=int(raw.get("position", 0)),
    )


def parse_question(raw: dict[str, Any], page_id: str) -> Question:
    """Build a :class:`~sm_excel.models.Question` from a raw API dict.

    Args:
        raw:     Raw question object from the API.
        page_id: Identifier of the containing page.

    Returns:
        Populated :class:`Question` dataclass instance.
    """
    family = raw.get("family", "")
    subtype = raw.get("subtype", "")
    headings = raw.get("headings", [])
    heading = headings[0].get("heading", "") if headings else raw.get("heading", "")

    choices_raw = (
        raw.get("answers", {}).get("choices", [])
        or raw.get("answers", {}).get("rows", [])
    )
    choices = [parse_choice(c) for c in choices_raw]

    return Question(
        question_id=str(raw.get("id", "")),
        heading=str(heading),
        family=str(family),
        subtype=str(subtype),
        position=int(raw.get("position", 0)),
        page_id=page_id,
        choices=choices,
    )


def parse_page(raw: dict[str, Any]) -> Page:
    """Build a :class:`~sm_excel.models.Page` from a raw API dict.

    Questions embedded in the page response are also parsed.

    Args:
        raw: Raw page object (may already include ``questions`` list).

    Returns:
        Populated :class:`Page` dataclass instance.
    """
    page_id = str(raw.get("id", ""))
    questions = [
        parse_question(q, page_id) for q in raw.get("questions", [])
    ]
    return Page(
        page_id=page_id,
        title=str(raw.get("title", "")),
        position=int(raw.get("position", 0)),
        questions=questions,
    )


def parse_survey(raw: dict[str, Any]) -> Survey:
    """Build a :class:`~sm_excel.models.Survey` from a raw API details dict.

    The ``/surveys/{id}/details`` endpoint embeds pages and questions inside
    the response, so this function handles that nested structure.

    Args:
        raw: Raw survey details object from the API.

    Returns:
        Populated :class:`Survey` dataclass instance.
    """
    pages = [parse_page(p) for p in raw.get("pages", [])]
    return Survey(
        survey_id=str(raw.get("id", "")),
        title=str(raw.get("title", "")),
        pages=pages,
    )


# ---------------------------------------------------------------------------
# Trend data parser
# ---------------------------------------------------------------------------


def parse_trend_data(
    raw_trends: dict[str, Any],
    survey: Survey,
) -> list[TrendDataPoint]:
    """Convert the raw trends API response into a list of data-points.

    The trends response groups data by question_id → choice_id → time series.
    This function flattens that hierarchy into individual
    :class:`~sm_excel.models.TrendDataPoint` objects.

    Args:
        raw_trends: Raw response from ``GET /surveys/{id}/pages/{pid}/trends``.
        survey:     Parsed :class:`Survey` (used for question/choice lookups).

    Returns:
        Flat list of :class:`TrendDataPoint` instances.
    """
    question_index: dict[str, Question] = {
        q.question_id: q for q in survey.all_questions
    }
    choice_index: dict[str, dict[str, Choice]] = {
        q.question_id: {c.choice_id: c for c in q.choices}
        for q in survey.all_questions
    }

    data_points: list[TrendDataPoint] = []

    for q_block in raw_trends.get("data", []):
        question_id = str(q_block.get("id", ""))
        question = question_index.get(question_id)

        for choice_block in q_block.get("answers", {}).get("choices", []):
            choice_id = str(choice_block.get("id", ""))
            choice = (choice_index.get(question_id) or {}).get(choice_id)
            choice_text = choice.text if choice else str(choice_block.get("text", ""))

            for period in choice_block.get("time_period", []):
                data_points.append(
                    TrendDataPoint(
                        question_id=question_id,
                        choice_id=choice_id,
                        choice_text=choice_text,
                        period_start=str(period.get("start_date", "")),
                        period_end=str(period.get("end_date", "")),
                        count=int(period.get("count", 0)),
                        percent=float(period.get("percent", 0.0)),
                        extra={
                            "question_heading": question.heading if question else "",
                        },
                    )
                )

    return data_points


# ---------------------------------------------------------------------------
# DataFrame builders
# ---------------------------------------------------------------------------


def survey_structure_to_dataframe(survey: Survey) -> pd.DataFrame:
    """Build a DataFrame describing the question structure of a survey.

    Each row represents one question.  Columns::

        survey_id | survey_title | page_id | page_title | page_position
        | question_id | question_heading | family | subtype
        | question_position | choices

    Args:
        survey: Parsed :class:`Survey` instance.

    Returns:
        DataFrame with one row per question.
    """
    rows = []
    for page in survey.pages:
        for question in page.questions:
            rows.append(
                {
                    "survey_id": survey.survey_id,
                    "survey_title": survey.title,
                    "page_id": page.page_id,
                    "page_title": page.title,
                    "page_position": page.position,
                    "question_id": question.question_id,
                    "question_heading": question.heading,
                    "family": question.family,
                    "subtype": question.subtype,
                    "question_position": question.position,
                    "choices": "|".join(c.text for c in question.choices),
                }
            )
    return pd.DataFrame(rows)


def trends_to_dataframe(data_points: list[TrendDataPoint]) -> pd.DataFrame:
    """Convert a list of :class:`TrendDataPoint` objects to a wide DataFrame.

    The resulting DataFrame has one row per (question, choice, period) and
    columns::

        question_id | question_heading | choice_id | choice_text
        | period_start | period_end | count | percent

    Args:
        data_points: Output of :func:`parse_trend_data`.

    Returns:
        DataFrame in "wide" format (one metric per row).
    """
    if not data_points:
        return pd.DataFrame()

    rows = [
        {
            "question_id": dp.question_id,
            "question_heading": dp.extra.get("question_heading", ""),
            "choice_id": dp.choice_id,
            "choice_text": dp.choice_text,
            "period_start": dp.period_start,
            "period_end": dp.period_end,
            "count": dp.count,
            "percent": dp.percent,
        }
        for dp in data_points
    ]
    return pd.DataFrame(rows)


def pivot_trends_wide(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot a trends DataFrame so each choice is a column.

    Input columns: question_heading, choice_text, period_start, count, percent.
    Output: one row per period_start, one column per (question_heading, choice_text).

    Args:
        df: Output of :func:`trends_to_dataframe`.

    Returns:
        Wide-format DataFrame.
    """
    if df.empty:
        return df

    df = df.copy()
    df["col_label"] = (
        df["question_heading"].apply(clean_column_name)
        + "__"
        + df["choice_text"].apply(clean_column_name)
    )

    wide = df.pivot_table(
        index="period_start",
        columns="col_label",
        values="count",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()
    wide.columns.name = None
    return wide


def merge_dataframes(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate a list of compatible DataFrames into one.

    All DataFrames must share the same column schema.  Missing columns are
    filled with ``NaN``.

    Args:
        frames: List of DataFrames with matching (or compatible) columns.

    Returns:
        A single merged DataFrame.

    Raises:
        ValueError: if *frames* is empty.
    """
    if not frames:
        raise ValueError("Cannot merge an empty list of DataFrames.")
    return pd.concat(frames, ignore_index=True, sort=False)
