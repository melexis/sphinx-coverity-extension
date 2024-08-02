from unittest import TestCase

try:
    from unittest.mock import MagicMock, patch
except ImportError:
    from mock import MagicMock, patch

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
        self.assertEqual("https://scan.coverity.com/api/v2", coverity_conf_service.base_url)

        # Login to Coverity
        coverity_conf_service.login("user", "password")
        mock_requests.Session.assert_called_once()

    @patch.object(mlx.coverity_services.requests.Session, 'get')
    def test_retrieve_checkers(self, mock_get):
        """Test retrieving checkers (CoverityDefectService)"""
        coverity_conf_service = mlx.coverity_services.CoverityDefectService("scan.coverity.com/")

        # Login to Coverity
        coverity_conf_service.login("user", "password")

        with open("tests/column_keys.json", "rb") as content:
            mock_get.return_value.content = content.read()
        mock_get.return_value.ok = True
        coverity_conf_service.retrieve_checkers()
        mock_get.assert_called_once()

    def test_get_defects(self):
        filters = {
            'checker': None,
            'impact': None,
            'kind': None,
            'classification': None,
            'action': None,
            'component': None,
            'cwe': None,
            'cid': None,
        }
        fake_json = {"test": "succes"}
        fake_checkers = {
            "checkerAttribute": {
                "name": "checker",
                "displayName": "Checker"
            },
            "checkerAttributedata": [
                {
                "key": "test_key",
                "value": "test_value"
                }
            ]
        }
        fake_stream = "test_stream"
        coverity_conf_service = mlx.coverity.CoverityDefectService("scan.coverity.com/")

        # Login to Coverity
        coverity_conf_service.login("user", "password")

        # urls that are used in GET or POST requests
        stream_url = f"{coverity_conf_service.base_url.rstrip('/')}/streams/{fake_stream}"
        issue_url = coverity_conf_service.base_url.rstrip("/") + \
            "/issues/search?includeColumnLabels=true&offset=0&queryType=bySnapshot&rowCount=-1&sortOrder=asc"
        column_keys_url = coverity_conf_service.base_url.rstrip("/") + \
            "/issues/columns?queryType=bySnapshot&retrieveGroupByColumns=false"
        checkers_url = f"{coverity_conf_service.base_url.rstrip('/')}/checkerAttributes/checker"

        with requests_mock.mock() as mocker:
            mocker.get(stream_url, json={"stream": "valid"})
            with open("tests/column_keys.json", "rb") as content:
                mocker.get(column_keys_url, json=content.read())
            mocker.get(checkers_url, json=fake_checkers)
            mocker.post(issue_url, json=fake_json)

            assert coverity_conf_service.get_defects(fake_stream, filters, column_names=["CID"]) == fake_json
            assert mocker.called
