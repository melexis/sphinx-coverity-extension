from unittest import TestCase
try:
    from unittest.mock import MagicMock, patch, call
except ImportError as err:
    from mock import MagicMock, patch, call
import mlx.coverity as cov

class TestCoverity(TestCase):

    def SetUp(self):
        ''' SetUp to be run before each test to provide clean working env '''

    @patch('mlx.coverity_services', autospec=True)
    def test_dummy(self, cov_mock):
        ''' Currently just a dummy unit test '''
        cov_mock_object = MagicMock(spec=cov.CoverityConfigurationService)
        cov_mock.return_value = cov_mock_object
        


