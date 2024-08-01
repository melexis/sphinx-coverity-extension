from unittest import TestCase

try:
    from unittest.mock import MagicMock, patch
    # from unittest.mock import call
except ImportError:
    from mock import MagicMock, patch
    # from mock import call
import mlx.coverity_services
import requests


class TestCoverity(TestCase):
    def setUp(self):
        """SetUp to be run before each test to provide clean working env"""

    @patch("mlx.coverity_services.requests")
    def test_session_login(self, mock_requests):
        """Test login function of CoverityDefectService"""
        mock_requests.return_value = MagicMock(spec=requests)

        # Get the base url
        coverity_conf_service = mlx.coverity_services.CoverityDefectService("https", "scan.coverity.com/")
        self.assertEqual("https://scan.coverity.com/api/v2", coverity_conf_service.base_url)

        # Login to Coverity
        coverity_conf_service.login("user", "password")
        mock_requests.Session.assert_called_once()

    @patch.object(mlx.coverity_services.requests.Session, 'get')
    def test_retrieve_checkers(self, mock_get):
        """Test retrieving checkers (CoverityDefectService)"""
        coverity_conf_service = mlx.coverity_services.CoverityDefectService("https", "scan.coverity.com/")

        # Login to Coverity
        coverity_conf_service.login("user", "password")

        with open("tests/column_keys.json", "rb") as content:
            mock_get.return_value.content = content.read()
        mock_get.return_value.ok = True
        coverity_conf_service.retrieve_checkers()
        mock_get.assert_called_once()
