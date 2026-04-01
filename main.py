"""Command-line interface for SM-EXCEL.

Usage examples::

    # Extract a single survey
    python main.py survey 12345678 --output ./output

    # Extract all surveys in a folder
    python main.py folder 987654 --output ./output

    # Pass trend parameters
    python main.py survey 12345678 --start-date 2024-01-01 --end-date 2024-12-31
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from sm_excel.extractors.folder_extractor import extract_folder_surveys
from sm_excel.extractors.individual_extractor import extract_individual_survey

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)


def _build_trend_params(args: argparse.Namespace) -> dict | None:
    """Build optional trend query parameters from parsed CLI arguments."""
    params: dict = {}
    if getattr(args, "start_date", None):
        params["start_date"] = args.start_date
    if getattr(args, "end_date", None):
        params["end_date"] = args.end_date
    if getattr(args, "granularity", None):
        params["granularity"] = args.granularity
    return params or None


def cmd_survey(args: argparse.Namespace) -> None:
    """Handle the ``survey`` sub-command."""
    trend_params = _build_trend_params(args)
    out_path = extract_individual_survey(
        survey_id=args.survey_id,
        output_dir=args.output,
        trend_params=trend_params,
    )
    print(f"✅  Survey exported to: {out_path}")


def cmd_folder(args: argparse.Namespace) -> None:
    """Handle the ``folder`` sub-command."""
    trend_params = _build_trend_params(args)
    out_paths = extract_folder_surveys(
        folder_id=args.folder_id,
        output_dir=args.output,
        trend_params=trend_params,
    )
    if out_paths:
        print(f"✅  Folder exported – {len(out_paths)} file(s):")
        for p in out_paths:
            print(f"     {p}")
    else:
        print("⚠️   No files were generated.")


def build_parser() -> argparse.ArgumentParser:
    """Create and return the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="sm-excel",
        description="Extract SurveyMonkey surveys to Excel files.",
    )
    parser.add_argument(
        "--output",
        default="./output",
        metavar="DIR",
        help="Output directory for Excel files (default: ./output)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ---- survey sub-command ----
    sp_survey = subparsers.add_parser("survey", help="Extract a single survey.")
    sp_survey.add_argument("survey_id", help="SurveyMonkey survey ID")
    sp_survey.add_argument("--start-date", help="Trend start date (YYYY-MM-DD)")
    sp_survey.add_argument("--end-date", help="Trend end date (YYYY-MM-DD)")
    sp_survey.add_argument(
        "--granularity",
        choices=["day", "week", "month", "quarter", "year"],
        help="Trend granularity",
    )
    sp_survey.set_defaults(func=cmd_survey)

    # ---- folder sub-command ----
    sp_folder = subparsers.add_parser(
        "folder", help="Extract all surveys in a folder."
    )
    sp_folder.add_argument("folder_id", help="SurveyMonkey folder ID")
    sp_folder.add_argument("--start-date", help="Trend start date (YYYY-MM-DD)")
    sp_folder.add_argument("--end-date", help="Trend end date (YYYY-MM-DD)")
    sp_folder.add_argument(
        "--granularity",
        choices=["day", "week", "month", "quarter", "year"],
        help="Trend granularity",
    )
    sp_folder.set_defaults(func=cmd_folder)

    return parser


def main(argv: list[str] | None = None) -> None:
    """Entry-point for the sm-excel CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        sys.exit(1)
    except Exception as exc:
        logger.error("Unexpected error: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
