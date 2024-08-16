from unittest import TestCase

try:
    from unittest.mock import MagicMock, patch
except ImportError:
    from mock import MagicMock, patch

import json
import requests
import requests_mock
from urllib.parse import urlencode

import mlx.coverity
import mlx.coverity_services


class TestCoverity(TestCase):
    def setUp(self):
        """SetUp to be run before each test to provide clean working env"""

    def initialize_coverity_service(self, login=False):
        """Logs in Coverity Service and initializes the urls used for REST API.

        Returns:
            CoverityDefectService: The coveritye defect service
        """
        coverity_conf_service = mlx.coverity.CoverityDefectService("scan.coverity.com/")

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

        with open("tests/columns_keys.json", "rb") as content:
            mock_get.return_value.content = content.read()
        mock_get.return_value.ok = True
        coverity_conf_service.retrieve_checkers()
        mock_get.assert_called_once()

    def test_get_defects_call(self):
        with open("tests/columns_keys.json", "r") as content:
            column_keys = json.loads(content.read())

        self.filters = {
            "checker": None,
            "impact": None,
            "kind": None,
            "classification": None,
            "action": None,
            "component": None,
            "cwe": None,
            "cid": None,
        }
        self.fake_json = {"test": "succes"}
        self.fake_checkers = {
            "checkerAttribute": {"name": "checker", "displayName": "Checker"},
            "checkerAttributedata": [{"key": "checker_key", "value": "checker_value"}],
        }

        self.fake_stream = "test_stream"
        # initialize what needed for the REST API
        coverity_service = self.initialize_coverity_service(login=True)

        with requests_mock.mock() as mocker:
            mocker.get(self.column_keys_url, json=column_keys)
            mocker.get(self.checkers_url, json=self.fake_checkers)
            mocker.get(self.stream_url, json={"stream": "valid"})
            mocker.post(self.issues_url, json=self.fake_json)

            # Validate stream name
            coverity_service.validate_stream(self.fake_stream)
            # Retrieve column keys
            assert coverity_service.retrieve_column_keys()["Issue Kind"] == "displayIssueKind"
            assert coverity_service.retrieve_column_keys()["CID"] == "cid"
            # Retrieve checkers
            assert coverity_service.retrieve_checkers() == ["checker_key"]
            # Get defects
            assert coverity_service.get_defects(self.fake_stream, self.filters, column_names=["CID"]) == self.fake_json
            # Total amount of request are 4 => column keys, checkers, stream and defects/issues
            assert mocker.call_count == 4

            # check get requests
            get_urls = [self.stream_url, self.column_keys_url, self.checkers_url]
            for index in range(len(get_urls)):
                mock_req = mocker.request_history[index]
                assert mock_req.url == get_urls[index]
                assert mock_req.verify
                assert mock_req.headers["Authorization"] == requests.auth._basic_auth_str("user", "password")
            # check post request (last request)
            assert mocker.last_request.url == self.issues_url
            assert mocker.last_request.verify
            assert mocker.last_request.headers["Authorization"] == requests.auth._basic_auth_str("user", "password")

    def test_get_filtered_defects(self):
        with open("tests/columns_keys.json", "r") as content:
            column_keys = json.loads(content.read())

        with open("tests/fake_json.json", "r") as content:
            self.fake_json = json.loads(content.read())

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
            mocker.get(self.stream_url, json={"stream": "valid"})
            test_post = mocker.post(self.issues_url, json=self.fake_json)

            coverity_service.retrieve_checkers()
            coverity_service.retrieve_column_keys()

            sphinx_coverity_connector = mlx.coverity.SphinxCoverityConnector()
            sphinx_coverity_connector.coverity_service = coverity_service
            sphinx_coverity_connector.stream = self.fake_stream
            node_filters = {'checker': 'MISRA', 'impact': None, 'kind': None,
                            'classification': 'Intentional,Bug,Pending,Unclassified', 'action': None,
                            'component': None, 'cwe': None, 'cid': None}
            column_names =  {'Comment', 'Checker', 'Classification', 'CID'}
            fake_node = {"col": column_names,
                         "filters": node_filters}
            defects = sphinx_coverity_connector.get_filtered_defects(fake_node)
            breakpoint()
            assert defects == self.fake_json

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
