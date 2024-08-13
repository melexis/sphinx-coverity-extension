from unittest import TestCase

try:
    from unittest.mock import MagicMock, patch
except ImportError:
    from mock import MagicMock, patch

import json
import requests
import requests_mock

import mlx.coverity
import mlx.coverity_services


class TestCoverity(TestCase):
    def setUp(self):
        """SetUp to be run before each test to provide clean working env"""

    @patch("mlx.coverity_services.requests")
    def test_session_login(self, mock_requests):
        """Test login function of CoverityDefectService"""
        mock_requests.return_value = MagicMock(spec=requests)

        # Get the base url
        coverity_conf_service = mlx.coverity_services.CoverityDefectService("scan.coverity.com/")
        self.assertEqual("https://scan.coverity.com/api/v2", coverity_conf_service.api_endpoint)

        # Login to Coverity
        coverity_conf_service.login("user", "password")
        mock_requests.Session.assert_called_once()

    @patch.object(mlx.coverity_services.requests.Session, "get")
    def test_retrieve_checkers(self, mock_get):
        """Test retrieving checkers (CoverityDefectService)"""
        coverity_conf_service = mlx.coverity_services.CoverityDefectService("scan.coverity.com/")

        # Login to Coverity
        coverity_conf_service.login("user", "password")

        with open("tests/columns.json", "rb") as content:
            mock_get.return_value.content = content.read()
        mock_get.return_value.ok = True
        coverity_conf_service.retrieve_checkers()
        mock_get.assert_called_once()

    def test_get_defects(self):
        filters = {
            "checker": None,
            "impact": None,
            "kind": None,
            "classification": None,
            "action": None,
            "component": None,
            "cwe": None,
            "cid": None,
        }
        fake_json = {"test": "succes"}
        fake_checkers = {
            "checkerAttribute": {"name": "checker", "displayName": "Checker"},
            "checkerAttributedata": [{"key": "checker_key", "value": "checker_value"}],
        }
        fake_stream = "test_stream"
        coverity_conf_service = mlx.coverity.CoverityDefectService("scan.coverity.com/")

        # Login to Coverity
        coverity_conf_service.login("user", "password")

        # urls that are used in GET or POST requests
        column_keys_url = (
            coverity_conf_service.api_endpoint
            + "/issues/columns?queryType=bySnapshot&retrieveGroupByColumns=false"
        )
        checkers_url = f"{coverity_conf_service.api_endpoint}/checkerAttributes/checker"
        stream_url = f"{coverity_conf_service.api_endpoint}/streams/{fake_stream}"
        issues_url = (
            coverity_conf_service.api_endpoint
            + "/issues/search?includeColumnLabels=true&offset=0&queryType=bySnapshot&rowCount=-1&sortOrder=asc"
        )

        with requests_mock.mock() as mocker:
            with open("tests/columns.json", "r") as content:
                column_keys = json.loads(content.read())
            mocker.get(column_keys_url, json=column_keys)
            mocker.get(checkers_url, json=fake_checkers)
            mocker.get(stream_url, json={"stream": "valid"})
            mocker.post(issues_url, json=fake_json)

            # Validate stream name
            coverity_conf_service.validate_stream(fake_stream)
            # Retrieve column keys
            assert coverity_conf_service.retrieve_column_keys() == column_keys
            # Retrieve checkers
            assert coverity_conf_service.retrieve_checkers() == ["checker_key"]
            # Get defects
            assert coverity_conf_service.get_defects(fake_stream, filters, column_names=["CID"]) == fake_json
            # Total amount of request are 4 => column keys, checkers, stream and defects/issues
            assert mocker.call_count == 4

            # check get requests
            get_urls = [stream_url, column_keys_url, checkers_url]
            for index in range(len(get_urls)):
                mock_req = mocker.request_history[index]
                assert mock_req.url == get_urls[index]
                assert mock_req.verify
                assert mock_req.headers["Authorization"] == requests.auth._basic_auth_str("user", "password")
            # check post request (last request)
            assert mocker.last_request.url == issues_url
            assert mocker.last_request.verify
            assert mocker.last_request.headers["Authorization"] == requests.auth._basic_auth_str("user", "password")

    def test_failed_login(self):
        fake_stream = "test_stream"

        coverity_conf_service = mlx.coverity.CoverityDefectService("scan.coverity.com/")
        stream_url = f"{coverity_conf_service.api_endpoint.rstrip('/')}/streams/{fake_stream}"

        with requests_mock.mock() as mocker:
            mocker.get(stream_url, headers={"Authorization": "Basic fail"}, status_code=401)
            # Login to Coverity
            coverity_conf_service.login("user", "password")
            # Validate stream name
            with self.assertRaises(requests.HTTPError) as err:
                coverity_conf_service.validate_stream(fake_stream)
            self.assertEqual(err.exception.response.status_code, 401)
