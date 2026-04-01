"""Tests for the CLI entry-point (main.py)."""

from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest

from main import build_parser, cmd_survey, cmd_folder


class TestParser:
    def test_survey_command_parsed(self):
        parser = build_parser()
        args = parser.parse_args(["survey", "12345"])
        assert args.command == "survey"
        assert args.survey_id == "12345"

    def test_folder_command_parsed(self):
        parser = build_parser()
        args = parser.parse_args(["folder", "99"])
        assert args.command == "folder"
        assert args.folder_id == "99"

    def test_output_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--output", "/tmp/out", "survey", "1"])
        assert args.output == "/tmp/out"

    def test_missing_command_fails(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])


class TestCmdSurvey:
    @patch("main.extract_individual_survey", return_value=Path("/tmp/survey.xlsx"))
    def test_calls_extractor(self, mock_extract):
        parser = build_parser()
        args = parser.parse_args(["survey", "123"])
        cmd_survey(args)
        mock_extract.assert_called_once()
        call_kwargs = mock_extract.call_args
        assert call_kwargs.kwargs.get("survey_id") == "123" or call_kwargs.args[0] == "123"


class TestCmdFolder:
    @patch(
        "main.extract_folder_surveys",
        return_value=[Path("/tmp/g1.xlsx"), Path("/tmp/g2.xlsx")],
    )
    def test_calls_folder_extractor(self, mock_extract):
        parser = build_parser()
        args = parser.parse_args(["folder", "456"])
        cmd_folder(args)
        mock_extract.assert_called_once()
