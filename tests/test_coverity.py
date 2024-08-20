from unittest import TestCase
from unittest.mock import MagicMock, patch

import json
import requests
import requests_mock
from urllib.parse import urlencode
from pathlib import Path
from parameterized import parameterized


from mlx.coverity import SphinxCoverityConnector
from mlx.coverity_services import CoverityDefectService
import mlx.coverity_services
from .filters import test_defect_filter_0, test_defect_filter_1

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

    def initialize_coverity_service(self, login=False):
        """Logs in Coverity Service and initializes the urls used for REST API.

        Returns:
            CoverityDefectService: The coverity defect service
        """
        coverity_conf_service = CoverityDefectService("scan.coverity.com/")

        if login:
            # Login to Coverity
            coverity_conf_service.login("user", "password")

        # urls that are used in GET or POST requests
        endpoint = coverity_conf_service.api_endpoint
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

        return coverity_conf_service

    @patch("mlx.coverity_services.requests")
    def test_session_login(self, mock_requests):
        """Test login function of CoverityDefectService"""
        mock_requests.return_value = MagicMock(spec=requests)

        # Get the base url
        coverity_conf_service = CoverityDefectService("scan.coverity.com/")
        self.assertEqual("https://scan.coverity.com/api/v2", coverity_conf_service.api_endpoint)

        # Login to Coverity

    @patch("mlx.coverity_services.requests")
    def test_stream_validation(self, mock_requests):
        mock_requests.return_value = MagicMock(spec=requests)

        self.fake_stream = "test_stream"
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
        with open(f"{TEST_FOLDER}/columns_keys.json", "r") as content:
            column_keys = json.loads(content.read())
        self.fake_stream = "test_stream"
        # initialize what needed for the REST API
        coverity_service = self.initialize_coverity_service(login=True)
        with requests_mock.mock() as mocker:
            mocker.get(self.column_keys_url, json=column_keys)
            coverity_service.retrieve_column_keys()
            history = mocker.request_history
            assert mocker.call_count == 1
            assert history[0].method == "GET"
            assert history[0].url == self.column_keys_url
            assert history[0].verify
            assert coverity_service.columns["Issue Kind"] == "displayIssueKind"
            assert coverity_service.columns["CID"] == "cid"

    def test_retrieve_checkers(self):
        self.fake_stream = "test_stream"
        self.fake_checkers = {
            "checkerAttribute": {"name": "checker", "displayName": "Checker"},
            "checkerAttributedata": [
                {"key": "MISRA", "value": "MISRA"},
                {"key": "CHECKER", "value": "CHECKER"}
            ],
        }
        # initialize what needed for the REST API
        coverity_service = self.initialize_coverity_service(login=True)

        with requests_mock.mock() as mocker:
            mocker.get(self.checkers_url, json=self.fake_checkers)
            coverity_service.retrieve_checkers()
            history = mocker.request_history
            assert mocker.call_count == 1
            assert history[0].method == "GET"
            assert history[0].url == self.checkers_url
            assert history[0].verify
            assert coverity_service.checkers == ["MISRA", "CHECKER"]

    @parameterized.expand([
        [test_defect_filter_0.filters, test_defect_filter_0.column_names, test_defect_filter_0.request_data],
        [test_defect_filter_1.filters, test_defect_filter_1.column_names, test_defect_filter_1.request_data]
    ])
    def test_get_defects(self, filters, column_names, request_data):
        with open(f"{TEST_FOLDER}/columns_keys.json", "r") as content:
            column_keys = json.loads(content.read())
        self.fake_checkers = {
            "checkerAttribute": {"name": "checker", "displayName": "Checker"},
            "checkerAttributedata": [
                {"key": "MISRA 1", "value": "MISRA 1"},
                {"key": "MISRA 2", "value": "MISRA 2"},
                {"key": "MISRA 3", "value": "MISRA 3"},
                {"key": "CHECKER 1", "value": "CHECKER 1"},
                {"key": "CHECKER 2", "value": "CHECKER 2"}
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
                coverity_service.get_defects(self.fake_stream, filters, column_names)
                data = mock_method.call_args[0][0]
                mock_method.assert_called_once()
                assert ordered(data) == ordered(request_data)

    def test_get_filtered_defects(self):
        with open(f"{TEST_FOLDER}/columns_keys.json", "r") as content:
            column_keys = json.loads(content.read())

        self.fake_checkers = {
            "checkerAttribute": {
                "name": "checker",
                "displayName": "Checker"
            },
            "checkerAttributedata": [
                {
                    "key": "MISRA 1",
                    "value": "MISRA 1"
                },
                {
                    "key": "MISRA 2",
                    "value": "MISRA 2"
                },
                {
                    "key": "MISRA 3",
                    "value": "MISRA 3"
                },
                {
                    "key": "CHECK",
                    "value": "CHECK"
                }
            ]
        }
        self.fake_stream = "test_stream"

        # initialize what needed for the REST API
        coverity_service = self.initialize_coverity_service(login=True)

        with requests_mock.mock() as mocker:
            mocker.get(self.column_keys_url, json=column_keys)
            mocker.get(self.checkers_url, json=self.fake_checkers)
            mocker.post(self.issues_url, json={})

            coverity_service.retrieve_checkers()
            coverity_service.retrieve_column_keys()

            sphinx_coverity_connector = SphinxCoverityConnector()
            sphinx_coverity_connector.coverity_service = coverity_service
            sphinx_coverity_connector.stream = self.fake_stream
            node_filters = {
                "checker": "MISRA", "impact": None, "kind": None,
                "classification": "Intentional,Bug,Pending,Unclassified", "action": None, "component": None,
                "cwe": None, "cid": None
            }
            column_names = {"Comment", "Checker", "Classification", "CID"}
            fake_node = {"col": column_names,
                         "filters": node_filters}

            with patch.object(CoverityDefectService, "get_defects") as mock_method:
                sphinx_coverity_connector.get_filtered_defects(fake_node)
                mock_method.assert_called_once_with(self.fake_stream, fake_node["filters"], column_names)

    def test_failed_login(self):
        fake_stream = "test_stream"

        coverity_conf_service = CoverityDefectService("scan.coverity.com/")
        stream_url = f"{coverity_conf_service.api_endpoint}/streams/{fake_stream}"

        with requests_mock.mock() as mocker:
            mocker.get(stream_url, headers={"Authorization": "Basic fail"}, status_code=401)
            # Login to Coverity
            coverity_conf_service.login("user", "password")
            # Validate stream name
            with self.assertRaises(requests.HTTPError) as err:
                coverity_conf_service.validate_stream(fake_stream)
            self.assertEqual(err.exception.response.status_code, 401)
