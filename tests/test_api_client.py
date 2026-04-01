"""Tests for sm_excel.client.api_client."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from sm_excel.client.api_client import generate_headers, request_get, get_all_pages


class TestGenerateHeaders:
    def test_returns_bearer_token(self):
        headers = generate_headers("mytoken123")
        assert headers["Authorization"] == "Bearer mytoken123"

    def test_contains_content_type(self):
        headers = generate_headers("tok")
        assert headers["Content-Type"] == "application/json"

    def test_empty_token_raises(self):
        with pytest.raises(ValueError):
            generate_headers("")

    def test_non_string_raises(self):
        with pytest.raises((ValueError, AttributeError)):
            generate_headers(None)  # type: ignore[arg-type]


class TestRequestGet:
    def _mock_response(self, status_code=200, json_data=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data or {}
        resp.raise_for_status = MagicMock()
        resp.headers = {}
        return resp

    @patch("sm_excel.client.api_client.requests.get")
    def test_happy_path(self, mock_get):
        mock_get.return_value = self._mock_response(json_data={"id": "1"})
        result = request_get("http://example.com", headers={})
        assert result == {"id": "1"}

    @patch("sm_excel.client.api_client.requests.get")
    def test_raises_on_404(self, mock_get):
        resp = self._mock_response(status_code=404)
        resp.raise_for_status.side_effect = requests.HTTPError("404")
        mock_get.return_value = resp
        with pytest.raises(requests.HTTPError):
            request_get("http://example.com", headers={})

    @patch("sm_excel.client.api_client.time.sleep", return_value=None)
    @patch("sm_excel.client.api_client.requests.get")
    def test_retries_on_429_then_succeeds(self, mock_get, _sleep):
        rate_limited = self._mock_response(status_code=429)
        rate_limited.headers = {"Retry-After": "0"}
        success = self._mock_response(json_data={"ok": True})
        mock_get.side_effect = [rate_limited, success]
        result = request_get("http://example.com", headers={})
        assert result == {"ok": True}

    @patch("sm_excel.client.api_client.requests.get")
    def test_connection_error_propagates(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("network down")
        with pytest.raises(requests.ConnectionError):
            request_get("http://example.com", headers={})


class TestGetAllPages:
    @patch("sm_excel.client.api_client.requests.get")
    def test_single_page(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {}
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {
            "data": [{"id": "1"}, {"id": "2"}],
            "links": {},
        }
        mock_get.return_value = resp
        items = get_all_pages("http://example.com/surveys", headers={})
        assert len(items) == 2

    @patch("sm_excel.client.api_client.requests.get")
    def test_multiple_pages(self, mock_get):
        page1 = MagicMock()
        page1.status_code = 200
        page1.headers = {}
        page1.raise_for_status = MagicMock()
        page1.json.return_value = {
            "data": [{"id": "1"}],
            "links": {"next": "http://example.com/surveys?page=2"},
        }
        page2 = MagicMock()
        page2.status_code = 200
        page2.headers = {}
        page2.raise_for_status = MagicMock()
        page2.json.return_value = {
            "data": [{"id": "2"}],
            "links": {},
        }
        mock_get.side_effect = [page1, page2]
        items = get_all_pages("http://example.com/surveys", headers={})
        assert [i["id"] for i in items] == ["1", "2"]
