"""Tests for sm_excel.processors.response_processor."""

import pandas as pd
import pytest

from sm_excel.models import Choice, Page, Question, Survey
from sm_excel.processors.response_processor import (
    clean_column_name,
    clean_column_names,
    merge_dataframes,
    parse_page,
    parse_question,
    parse_survey,
    parse_trend_data,
    pivot_trends_wide,
    survey_structure_to_dataframe,
    trends_to_dataframe,
)
from tests.conftest import make_survey, make_question


class TestCleanColumnName:
    def test_lowercase(self):
        assert clean_column_name("MyColumn") == "mycolumn"

    def test_spaces_replaced(self):
        assert clean_column_name("My Column Name") == "my_column_name"

    def test_special_chars_replaced(self):
        assert clean_column_name("Q1: How are you?") == "q1_how_are_you"

    def test_strip_leading_trailing_underscores(self):
        assert clean_column_name("  _test_  ") == "test"


class TestCleanColumnNames:
    def test_renames_columns(self):
        df = pd.DataFrame(columns=["My Name", "Score (%)"])
        result = clean_column_names(df)
        assert list(result.columns) == ["my_name", "score"]


class TestParseQuestion:
    def test_basic_parse(self):
        raw = {
            "id": "q99",
            "headings": [{"heading": "Rate our service"}],
            "family": "rating",
            "subtype": "star",
            "position": 2,
            "answers": {
                "choices": [
                    {"id": "c1", "text": "1 star", "position": 1},
                    {"id": "c2", "text": "5 stars", "position": 2},
                ]
            },
        }
        q = parse_question(raw, page_id="p1")
        assert q.question_id == "q99"
        assert q.heading == "Rate our service"
        assert q.family == "rating"
        assert len(q.choices) == 2


class TestParseSurvey:
    def test_parses_pages_and_questions(self):
        raw = {
            "id": "123",
            "title": "Customer Satisfaction",
            "pages": [
                {
                    "id": "p1",
                    "title": "Page 1",
                    "position": 1,
                    "questions": [
                        {
                            "id": "q1",
                            "headings": [{"heading": "Q1"}],
                            "family": "single_choice",
                            "subtype": "vertical",
                            "position": 1,
                            "answers": {"choices": []},
                        }
                    ],
                }
            ],
        }
        survey = parse_survey(raw)
        assert survey.survey_id == "123"
        assert len(survey.pages) == 1
        assert len(survey.all_questions) == 1


class TestSurveyStructureToDataframe:
    def test_one_row_per_question(self):
        survey = make_survey(questions=[make_question("q1"), make_question("q2")])
        df = survey_structure_to_dataframe(survey)
        assert len(df) == 2
        assert "question_id" in df.columns
        assert "survey_id" in df.columns


class TestParseTrendData:
    def test_extracts_data_points(self):
        survey = make_survey()
        q = survey.all_questions[0]
        raw_trends = {
            "data": [
                {
                    "id": q.question_id,
                    "answers": {
                        "choices": [
                            {
                                "id": "c1",
                                "text": "Very satisfied",
                                "time_period": [
                                    {
                                        "start_date": "2024-01-01",
                                        "end_date": "2024-01-31",
                                        "count": 42,
                                        "percent": 0.56,
                                    }
                                ],
                            }
                        ]
                    },
                }
            ]
        }
        data_points = parse_trend_data(raw_trends, survey)
        assert len(data_points) == 1
        assert data_points[0].count == 42
        assert data_points[0].percent == 0.56


class TestTrendsToDataframe:
    def test_returns_empty_on_no_data(self):
        df = trends_to_dataframe([])
        assert df.empty

    def test_columns_present(self):
        from sm_excel.models import TrendDataPoint

        dp = TrendDataPoint(
            question_id="q1",
            choice_id="c1",
            choice_text="Yes",
            period_start="2024-01-01",
            period_end="2024-01-31",
            count=10,
            percent=0.5,
        )
        df = trends_to_dataframe([dp])
        assert "count" in df.columns
        assert "percent" in df.columns


class TestPivotTrendsWide:
    def test_pivot_produces_wide_format(self):
        from sm_excel.models import TrendDataPoint

        dps = [
            TrendDataPoint("q1", "c1", "Yes", "2024-01", "2024-01", 10, 0.5),
            TrendDataPoint("q1", "c1", "Yes", "2024-02", "2024-02", 20, 0.6),
        ]
        long_df = trends_to_dataframe(dps)
        wide_df = pivot_trends_wide(long_df)
        assert "period_start" in wide_df.columns
        assert len(wide_df) == 2


class TestMergeDataFrames:
    def test_merges_rows(self):
        df1 = pd.DataFrame({"a": [1, 2]})
        df2 = pd.DataFrame({"a": [3, 4]})
        merged = merge_dataframes([df1, df2])
        assert len(merged) == 4

    def test_empty_list_raises(self):
        with pytest.raises(ValueError):
            merge_dataframes([])
