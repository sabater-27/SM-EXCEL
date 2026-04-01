"""Configuration loaded from environment variables / .env file."""

import os
from dotenv import load_dotenv

load_dotenv()


def get_token() -> str:
    """Return the SurveyMonkey OAuth access token from the environment.

    Raises:
        EnvironmentError: if SURVEYMONKEY_TOKEN is not set.
    """
    token = os.getenv("SURVEYMONKEY_TOKEN", "").strip()
    if not token:
        raise EnvironmentError(
            "SURVEYMONKEY_TOKEN is not set. "
            "Copy .env.example to .env and fill in your token."
        )
    return token


def get_base_url() -> str:
    """Return the SurveyMonkey API base URL."""
    return os.getenv(
        "SURVEYMONKEY_BASE_URL", "https://api.surveymonkey.com/v3"
    ).rstrip("/")


def get_output_dir() -> str:
    """Return the default output directory for Excel files."""
    return os.getenv("OUTPUT_DIR", "./output")
