"""High-level SurveyMonkey API methods built on top of api_client."""

from __future__ import annotations

import logging
from typing import Any

from sm_excel import config
from sm_excel.client.api_client import generate_headers, get_all_pages, request_get

logger = logging.getLogger(__name__)


class SurveyMonkeyClient:
    """Stateful client that encapsulates all API calls.

    Usage::

        client = SurveyMonkeyClient()
        survey_data = client.get_survey("12345678")
    """

    def __init__(self, token: str | None = None, base_url: str | None = None) -> None:
        self._token = token or config.get_token()
        self._base_url = base_url or config.get_base_url()
        self._headers = generate_headers(self._token)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _url(self, *parts: str) -> str:
        """Build a full API URL from path parts."""
        path = "/".join(str(p).strip("/") for p in parts)
        return f"{self._base_url}/{path}"

    def _get(self, *parts: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return request_get(self._url(*parts), headers=self._headers, params=params)

    def _get_all(self, *parts: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return get_all_pages(self._url(*parts), headers=self._headers, params=params)

    # ------------------------------------------------------------------
    # Survey endpoints
    # ------------------------------------------------------------------

    def get_survey(self, survey_id: str) -> dict[str, Any]:
        """Fetch metadata for a single survey.

        Args:
            survey_id: The SurveyMonkey numeric survey identifier.

        Returns:
            Raw API response dict for the survey object.
        """
        logger.info("Fetching survey %s", survey_id)
        return self._get("surveys", survey_id)

    def get_survey_details(self, survey_id: str) -> dict[str, Any]:
        """Fetch full survey details including pages and questions.

        The ``/surveys/{id}/details`` endpoint returns the complete survey
        structure in a single call.

        Args:
            survey_id: The SurveyMonkey numeric survey identifier.

        Returns:
            Raw API response dict containing pages and questions.
        """
        logger.info("Fetching survey details for %s", survey_id)
        return self._get("surveys", survey_id, "details")

    def get_pages(self, survey_id: str) -> list[dict[str, Any]]:
        """Return all pages for a survey (paginated).

        Args:
            survey_id: The SurveyMonkey numeric survey identifier.

        Returns:
            List of raw page objects.
        """
        logger.info("Fetching pages for survey %s", survey_id)
        return self._get_all("surveys", survey_id, "pages")

    def get_questions(self, survey_id: str, page_id: str) -> list[dict[str, Any]]:
        """Return all questions on a specific page (paginated).

        Args:
            survey_id: The SurveyMonkey numeric survey identifier.
            page_id:   The page identifier.

        Returns:
            List of raw question objects.
        """
        logger.info("Fetching questions for survey %s, page %s", survey_id, page_id)
        return self._get_all("surveys", survey_id, "pages", page_id, "questions")

    def get_trends(
        self,
        survey_id: str,
        page_id: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Fetch trend data for all questions on a page.

        Corresponds to:
        ``GET /v3/surveys/{survey_id}/pages/{page_id}/trends``

        Args:
            survey_id: The SurveyMonkey numeric survey identifier.
            page_id:   The page identifier.
            params:    Optional extra query parameters (e.g. ``start_date``,
                       ``end_date``, ``granularity``).

        Returns:
            Raw API response dict containing trend data per question/choice.
        """
        logger.info(
            "Fetching trends for survey %s, page %s", survey_id, page_id
        )
        return self._get(
            "surveys", survey_id, "pages", page_id, "trends",
            params=params,
        )

    def list_surveys(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Return all surveys accessible with the current token (paginated).

        Args:
            params: Optional filters (``folder_id``, ``start_date``, etc.).

        Returns:
            List of raw survey summary objects.
        """
        logger.info("Listing all surveys")
        return self._get_all("surveys", params=params)

    # ------------------------------------------------------------------
    # Folder endpoints
    # ------------------------------------------------------------------

    def get_folder(self, folder_id: str) -> dict[str, Any]:
        """Fetch metadata for a single folder/collection.

        Args:
            folder_id: The SurveyMonkey folder identifier.

        Returns:
            Raw API response dict for the folder object.
        """
        logger.info("Fetching folder %s", folder_id)
        return self._get("survey_folders", folder_id)

    def list_folders(self) -> list[dict[str, Any]]:
        """Return all survey folders accessible with the current token.

        Returns:
            List of raw folder objects.
        """
        logger.info("Listing all folders")
        return self._get_all("survey_folders")

    def get_folder_surveys(self, folder_id: str) -> list[dict[str, Any]]:
        """Return all survey summaries that belong to a specific folder.

        SurveyMonkey does not expose a dedicated "list surveys in folder"
        endpoint; instead, surveys carry a ``folder_id`` field.  This method
        filters the full survey list accordingly.

        Args:
            folder_id: The folder/collection identifier.

        Returns:
            List of raw survey summary objects belonging to the folder.
        """
        logger.info("Listing surveys in folder %s", folder_id)
        surveys = self.list_surveys(params={"folder_id": folder_id})
        # Belt-and-suspenders: also filter client-side in case the API
        # returns surveys from other folders.
        return [s for s in surveys if str(s.get("folder_id", "")) == str(folder_id)]
