from unittest import TestCase
from unittest.mock import MagicMock, patch

import json
import requests
import requests_mock
from urllib.parse import urlencode
from pathlib import Path
from parameterized import parameterized

from mlx.coverity import SphinxCoverityConnector, CoverityDefect, CoverityDefectService
from .filters import (test_defect_filter_0,
                      test_defect_filter_1,
                      test_defect_filter_2,
                      test_defect_filter_3,
                      test_snapshot)

TEST_FOLDER = Path(__file__).parent


def ordered(obj):
    if isinstance(obj, dict):
        return sorted((k, ordered(v)) for k, v in obj.items())
    if isinstance(obj, list):
        return sorted(ordered(x) for x in obj)
    else:
        return obj


class TestCoverity(TestCase):
    def setUp(self):
        """SetUp to be run before each test to provide clean working env"""
        self.fake_stream = "test_stream"

    def initialize_coverity_service(self, login=False):
        """Logs in Coverity Service and initializes the urls used for REST API.

        Returns:
            CoverityDefectService: The coverity defect service
        """
        coverity_service = CoverityDefectService("scan.coverity.com/")

        if login:
            # Login to Coverity
            coverity_service.login("user", "password")

        # urls that are used in GET or POST requests
        endpoint = coverity_service.api_endpoint
        params = {
            "queryType": "bySnapshot",
            "retrieveGroupByColumns": "false"
        }
        self.column_keys_url = f"{endpoint}/issues/columns?{urlencode(params)}"
        self.checkers_url = f"{endpoint}/checkerAttributes/checker"
        self.stream_url = f"{endpoint}/streams/{self.fake_stream}"
        params = {
            "includeColumnLabels": "true",
            "offset": 0,
            "queryType": "bySnapshot",
            "rowCount": -1,
            "sortOrder": "asc",
        }
        self.issues_url = f"{endpoint}/issues/search?{urlencode(params)}"

        return coverity_service

    def test_session_by_stream_validation(self):
        """To test the session authentication, the function `validate_stream` is used."""
        coverity_service = self.initialize_coverity_service(login=False)
        with requests_mock.mock() as mocker:
            mocker.get(self.stream_url, json={})
            # Login to Coverity
            coverity_service.login("user", "password")
            coverity_service.validate_stream(self.fake_stream)
            stream_request = mocker.last_request
            assert stream_request.headers["Authorization"] == requests.auth._basic_auth_str("user", "password")

    @patch("mlx.coverity.coverity_services.requests")
    def test_stream_validation(self, mock_requests):
        """Test if the function `validate_stream` is called once with the correct url"""
        mock_requests.return_value = MagicMock(spec=requests)

        # Get the base url
        coverity_service = CoverityDefectService("scan.coverity.com/")
        # Login to Coverity
        coverity_service.login("user", "password")
        with patch.object(CoverityDefectService, "_request") as mock_method:
            # Validate stream name
            coverity_service.validate_stream(self.fake_stream)
            mock_method.assert_called_once()
            mock_method.assert_called_with("https://scan.coverity.com/api/v2/streams/test_stream")

    def test_retrieve_columns(self):
        """Test the function `retrieve_column_keys`.
        Check if the the columns property is correctly initialized by checking if the name of a column returns
        the correct key."""
        with open(f"{TEST_FOLDER}/columns_keys.json", "r") as content:
            column_keys = json.loads(content.read())
        # initialize what needed for the REST API
        coverity_service = self.initialize_coverity_service(login=True)
        with requests_mock.mock() as mocker:
            mocker.get(self.column_keys_url, json=column_keys)
            coverity_service.retrieve_column_keys()
            assert mocker.call_count == 1
            mock_request = mocker.last_request
            assert mock_request.method == "GET"
            assert mock_request.url == self.column_keys_url
            assert mock_request.verify
            assert coverity_service.columns["Issue Kind"] == "displayIssueKind"
            assert coverity_service.columns["CID"] == "cid"

    def test_retrieve_checkers(self):
        """Test the function `retrieve_checkers`. Check if the returned list of the checkers property is equal to the
        keys of checkerAttributedata of the returned data of the request."""
        self.fake_checkers = {
            "checkerAttribute": {"name": "checker", "displayName": "Checker"},
            "checkerAttributedata": [
                {"key": "MISRA", "value": "M"},
                {"key": "CHECKER", "value": "C"}
            ],
        }
        # initialize what needed for the REST API
        coverity_service = self.initialize_coverity_service(login=True)

        with requests_mock.mock() as mocker:
            mocker.get(self.checkers_url, json=self.fake_checkers)
            coverity_service.retrieve_checkers()
            assert mocker.call_count == 1
            mock_request = mocker.last_request
            assert mock_request.method == "GET"
            assert mock_request.url == self.checkers_url
            assert mock_request.verify
            assert coverity_service.checkers == ["MISRA", "CHECKER"]

    @parameterized.expand([
        test_defect_filter_0,
        test_defect_filter_1,
        test_defect_filter_2,
        test_defect_filter_3,
    ])
    def test_get_defects(self, filters, column_names, request_data):
        """Check get defects with different filters. Check if the response of `get_defects` is the same as expected.
        The data is obtained from the filters.py file.
        Due to the usage of set in `get_defects` (column_keys), the function `ordered` is used to compare the returned
        data of the request where order does not matter."""
        with open(f"{TEST_FOLDER}/columns_keys.json", "r") as content:
            column_keys = json.loads(content.read())
        self.fake_checkers = {
            "checkerAttribute": {"name": "checker", "displayName": "Checker"},
            "checkerAttributedata": [
                {"key": "MISRA 1", "value": "M 1"},
                {"key": "MISRA 2 KEY", "value": "MISRA 2 VALUE"},
                {"key": "MISRA 3", "value": "M 3"},
                {"key": "C 1", "value": "CHECKER 1"},
                {"key": "C 2", "value": "CHECKER 2"}
            ],
        }
        # initialize what needed for the REST API
        coverity_service = self.initialize_coverity_service(login=True)

        with requests_mock.mock() as mocker:
            mocker.get(self.column_keys_url, json=column_keys)
            mocker.get(self.checkers_url, json=self.fake_checkers)
            # Retrieve checkers; required for get_defects()
            coverity_service.retrieve_checkers()
            # Retreive columns; required for get_defects()
            coverity_service.retrieve_column_keys()
            # Get defects
            with patch.object(CoverityDefectService, "retrieve_issues") as mock_method:
                coverity_service.get_defects(self.fake_stream, filters, column_names, "")
                data = mock_method.call_args[0][0]
                mock_method.assert_called_once()
                assert ordered(data) == ordered(request_data)

    def test_get_defects_with_snapshot(self):
        with open(f"{TEST_FOLDER}/columns_keys.json", "r") as content:
            column_keys = json.loads(content.read())
        self.fake_checkers = {
            "checkerAttribute": {"name": "checker", "displayName": "Checker"},
            "checkerAttributedata": [
                {"key": "MISRA 1", "value": "M 1"},
                {"key": "MISRA 2 KEY", "value": "MISRA 2 VALUE"},
                {"key": "MISRA 3", "value": "M 3"},
                {"key": "C 1", "value": "CHECKER 1"},
                {"key": "C 2", "value": "CHECKER 2"}
            ],
        }
        self.fake_stream = "test_stream"
        # initialize what needed for the REST API
        coverity_service = self.initialize_coverity_service(login=True)

        with requests_mock.mock() as mocker:
            mocker.get(self.column_keys_url, json=column_keys)
            mocker.get(self.checkers_url, json=self.fake_checkers)
            # Retrieve checkers; required for get_defects()
            coverity_service.retrieve_checkers()
            # Retreive columns; required for get_defects()
            coverity_service.retrieve_column_keys()
            # Get defects
            with patch.object(CoverityDefectService, "retrieve_issues") as mock_method:
                coverity_service.get_defects(self.fake_stream, test_snapshot.filters, test_snapshot.column_names, "123")
                data = mock_method.call_args[0][0]
                mock_method.assert_called_once()
                assert ordered(data) == ordered(test_snapshot.request_data)

    def test_get_filtered_defects(self):
        """Test `get_filtered_defects` of SphinxCoverityConnector. Check if `get_defects` is called once with the
        correct arguments.
        Tests also when `chart_attribute` of the node exists, the name will be added to column_names."""
        fake_snapshot = "123"
        sphinx_coverity_connector = SphinxCoverityConnector()
        sphinx_coverity_connector.coverity_service = self.initialize_coverity_service(login=False)
        sphinx_coverity_connector.stream = self.fake_stream
        sphinx_coverity_connector.snaphsot = fake_snapshot
        node_filters = {
            "checker": "MISRA", "impact": None, "kind": None,
            "classification": "Intentional,Bug,Pending,Unclassified", "action": None, "component": None,
            "cwe": None, "cid": None
        }
        column_names = {"Comment", "Classification", "CID"}
        fake_node = CoverityDefect()
        fake_node["col"] = column_names
        fake_node["filters"] = node_filters
        with patch.object(CoverityDefectService, "get_defects") as mock_method:
            sphinx_coverity_connector.get_filtered_defects(fake_node)
            mock_method.assert_called_once_with(self.fake_stream, fake_node["filters"], column_names, fake_snapshot)
            fake_node["chart_attribute"] = "Checker"
            column_names.add("Checker")
            sphinx_coverity_connector.get_filtered_defects(fake_node)
            mock_method.assert_called_with(self.fake_stream, fake_node["filters"], column_names, fake_snapshot)

    def test_failed_login(self):
        """Test a failed login by mocking the status code when validating the stream."""
        coverity_conf_service = CoverityDefectService("scan.coverity.com/")
        stream_url = f"{coverity_conf_service.api_endpoint}/streams/{self.fake_stream}"

        with requests_mock.mock() as mocker:
            mocker.get(stream_url, headers={"Authorization": "Basic fail"}, status_code=401)
            # Login to Coverity
            coverity_conf_service.login("user", "password")
            # Validate stream name
            with self.assertRaises(requests.HTTPError) as err:
                coverity_conf_service.validate_stream(self.fake_stream)
            self.assertEqual(err.exception.response.status_code, 401)
