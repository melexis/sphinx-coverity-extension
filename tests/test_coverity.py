from unittest import TestCase
try:
    from unittest.mock import MagicMock, patch
    # from unittest.mock import call
except ImportError:
    from mock import MagicMock, patch
    # from mock import call
import mlx.coverity as cov
import mlx.coverity_services as covservices

# For Coverity - SOAP
from suds.client import Client
from suds.wsse import Security, UsernameToken
from lxml import objectify


class TestCoverity(TestCase):

    def setUp(self):
        ''' SetUp to be run before each test to provide clean working env '''

    @patch('mlx.coverity_services.UsernameToken')
    @patch('mlx.coverity_services.Security')
    @patch('mlx.coverity_services.Client')
    def test_configuration_service_login(self, suds_client_mock, suds_security_mock, suds_username_mock):
        ''' Test login function of CoverityConfigurationService '''
        suds_client_mock.return_value = MagicMock(spec=Client)
        suds_client_mock.return_value.service = MagicMock(spec=covservices.Service)
        suds_client_mock.return_value.service.getVersion = MagicMock()
        suds_security_mock.return_value = MagicMock(spec=Security)
        suds_security_mock.return_value.tokens = []
        suds_username_mock.return_value = MagicMock(spec=UsernameToken, return_value="bljah")

        # Login to Coverity and obtain stream information
        coverity_conf_service = cov.CoverityConfigurationService('http', 'scan.coverity.com', '8080')
        suds_client_mock.assert_called_once_with('http://scan.coverity.com:8080/ws/v9/configurationservice?wsdl')

        coverity_conf_service.login('user', 'password')
        suds_security_mock.assert_called_once()
        suds_username_mock.assert_called_once_with('user', 'password')
        # suds_security_mock.tokens.assert_called_once_with("bljah")
        # suds_client_mock.set_options.assert_called_once_with(wsse=suds_security_mock)

    @patch('mlx.coverity_services.UsernameToken')
    @patch('mlx.coverity_services.Security')
    @patch('mlx.coverity_services.Client')
    def test_defect_service_login(self, suds_client_mock, suds_security_mock, suds_username_mock):
        ''' Test login function of CoverityDefectService '''
        suds_client_mock.return_value = MagicMock(spec=Client)
        suds_client_mock.return_value.service = MagicMock(spec=covservices.Service)
        suds_client_mock.return_value.service.getVersion = MagicMock()
        suds_security_mock.return_value = MagicMock(spec=Security)
        suds_security_mock.return_value.tokens = []
        suds_username_mock.return_value = MagicMock(spec=UsernameToken, return_value="bljah")

        # Login to Coverity and obtain stream information
        coverity_conf_service = cov.CoverityConfigurationService('http', 'scan.coverity.com', '8080')
        suds_client_mock.assert_called_once_with('http://scan.coverity.com:8080/ws/v9/configurationservice?wsdl')

        # Test CoverityDefectService
        coverity_service = cov.CoverityDefectService(coverity_conf_service)
        suds_client_mock.assert_called_with('http://scan.coverity.com:8080/ws/v9/defectservice?wsdl')

        coverity_service.login('user', 'password')
        suds_security_mock.assert_called_once()
        suds_username_mock.assert_called_once_with('user', 'password')

    @patch('mlx.coverity_services.UsernameToken')
    @patch('mlx.coverity_services.Security')
    @patch('mlx.coverity_services.Client')
    def test_defect_service_defects(self, suds_client_mock, suds_security_mock, suds_username_mock):
        ''' Test login function of CoverityDefectService '''
        suds_client_mock.return_value = MagicMock(spec=Client)
        suds_client_mock.return_value.service = MagicMock(spec=covservices.Service)
        suds_client_mock.return_value.service.getVersion = MagicMock()
        with open('tests/defect_soap.xml', 'rb') as xmlfile:
            defect_soap = objectify.fromstring(xmlfile.read())
        suds_client_mock.return_value.service.getMergedDefectsForSnapshotScope = MagicMock(spec=defect_soap,
                                                                                           return_value=defect_soap)
        suds_client_mock.return_value.factory = MagicMock()
        suds_security_mock.return_value = MagicMock(spec=Security)
        suds_security_mock.return_value.tokens = []
        suds_username_mock.return_value = MagicMock(spec=UsernameToken, return_value="bljah")

        # Login to Coverity and obtain stream information
        coverity_conf_service = cov.CoverityConfigurationService('http', 'scan.coverity.com', '8080')
        suds_client_mock.assert_called_once_with('http://scan.coverity.com:8080/ws/v9/configurationservice?wsdl')

        # Test CoverityDefectService
        coverity_service = cov.CoverityDefectService(coverity_conf_service)
        suds_client_mock.assert_called_with('http://scan.coverity.com:8080/ws/v9/defectservice?wsdl')

        coverity_service.login('user', 'password')
        suds_security_mock.assert_called_once()
        suds_username_mock.assert_called_once_with('user', 'password')

        coverity_service.get_defects('projectname', 'somestream')

    @patch('mlx.coverity_services.UsernameToken')
    @patch('mlx.coverity_services.Security')
    @patch('mlx.coverity_services.Client')
    def test_configuration_service_login_no_username_error(self, suds_client_mock, suds_security_mock,
                                                           suds_username_mock):
        ''' Test login function of CoverityConfigurationService when error occurs'''
        suds_client_mock.return_value = MagicMock(spec=Client)
        suds_client_mock.return_value.service = MagicMock(spec=covservices.Service)
        suds_client_mock.return_value.service.getVersion = MagicMock()
        suds_security_mock.return_value = MagicMock(spec=Security)
        suds_security_mock.return_value.tokens = []

        # Login to Coverity and obtain stream information
        coverity_conf_service = cov.CoverityConfigurationService('http', 'scan.coverity.com', '8080')
        suds_client_mock.assert_called_once_with('http://scan.coverity.com:8080/ws/v9/configurationservice?wsdl')

        suds_client_mock.side_effect = Exception((401, 'Unauthorized'))
        coverity_conf_service.login('', '')
