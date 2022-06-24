# -*- coding: utf-8 -*-

'''
Coverity plugin

Sphinx extension for restructured text that adds Coverity reporting to documentation.
See README.rst for more details.
'''
from getpass import getpass
from urllib.error import URLError, HTTPError

import pkg_resources

from mlx.coverity_logging import report_info, report_warning
from mlx.coverity_services import CoverityConfigurationService, CoverityDefectService
from mlx.coverity_directives.coverity_defect_list import CoverityDefect, CoverityDefectListDirective


class SphinxCoverityConnector():
    """
    Class containing functions and variables for Sphinx to access in specific stages of the documentation build.
    """
    project_name = ''
    coverity_service = None

    def __init__(self):
        """
        Initialize the object by setting error variable to false
        """
        self.coverity_login_error = False
        self.coverity_login_error_msg = ''
        self.stream = ''

    def initialize_environment(self, app):
        """
        Perform initializations needed before the build process starts.
        """
        # LaTeX-support: since we generate empty tags, we need to relax the verbosity of that error
        if 'preamble' not in app.config.latex_elements:
            app.config.latex_elements['preamble'] = ''
        app.config.latex_elements['preamble'] += '''\
    \\makeatletter
    \\let\@noitemerr\\relax
    \\makeatother'''

        self.stream = app.config.coverity_credentials['stream']

        # Login to Coverity and obtain stream information
        try:
            self.input_credentials(app.config.coverity_credentials)
            report_info('Login to Coverity server... ', True)
            coverity_conf_service = CoverityConfigurationService(app.config.coverity_credentials['transport'],
                                                                 app.config.coverity_credentials['hostname'],
                                                                 app.config.coverity_credentials['port'])
            coverity_conf_service.login(app.config.coverity_credentials['username'],
                                        app.config.coverity_credentials['password'])
            report_info('done')

            report_info('obtaining stream information... ', True)
            stream = coverity_conf_service.get_stream(self.stream)
            if stream is None:
                raise ValueError('No such Coverity stream [%s] found on [%s]' %
                                 (self.stream, coverity_conf_service.get_service_url()))
            report_info('done')

            # Get Stream's project name
            report_info('obtaining project name from stream... ', True)
            self.project_name = coverity_conf_service.get_project_name(stream)
            report_info('done')
            self.coverity_service = CoverityDefectService(coverity_conf_service)
            self.coverity_service.login(app.config.coverity_credentials['username'],
                                        app.config.coverity_credentials['password'])
        except (URLError, HTTPError, Exception, ValueError) as error_info:  # pylint: disable=broad-except
            if isinstance(error_info, EOFError):
                self.coverity_login_error_msg = "Coverity credentials are not configured."
            else:
                self.coverity_login_error_msg = str(error_info)
            report_info('failed with: %s' % error_info)
            self.coverity_login_error = True

    # -----------------------------------------------------------------------------
    # Event handlers
    def process_coverity_nodes(self, app, doctree, fromdocname):
        """
        This function should be triggered upon ``doctree-resolved event``

        Obtain information from Coverity server and generate a table.
        """
        if self.coverity_login_error:
            # Create failed topnode
            for node in doctree.traverse(CoverityDefect):
                top_node = node.create_top_node("Failed to connect to Coverity Server")
                node.replace_self(top_node)
            report_warning('Connection failed: %s' % self.coverity_login_error_msg, fromdocname)
            return

        # Item matrix:
        # Create table with related items, printing their target references.
        # Only source and target items matching respective regexp shall be included
        for node in doctree.traverse(CoverityDefect):
            # Get items from server
            try:
                defects = self.get_filtered_defects(node)
            except (URLError, AttributeError, Exception) as err:  # pylint: disable=broad-except
                report_warning('failed with %s' % err, fromdocname)
                continue
            node.perform_replacement(defects, self, app, fromdocname)

    # -----------------------------------------------------------------------------
    # Helper functions of event handlers
    @staticmethod
    def input_credentials(config_credentials):
        """ Ask user to input username and/or password if they haven't been configured yet.

        Args:
            config_credentials (dict): Dictionary to store the user's credentials.
        """
        if not config_credentials['username']:
            config_credentials['username'] = input("Coverity username: ")
        if not config_credentials['password']:
            config_credentials['password'] = getpass("Coverity password: ")

    def get_filtered_defects(self, node):
        """ Fetch defects from suds using filters stored in the given CoverityDefect object.

        Args:
            node (CoverityDefect): CoverityDefect object with zero or more filters stored.

        Returns:
            (suds.sudsobject.mergedDefectsPageDataObj) Suds mergedDefectsPageDataObj object containing filtered defects.
        """
        report_info('obtaining defects... ', True)
        defects = self.coverity_service.get_defects(self.project_name, self.stream, node['filters'])
        report_info("%d received" % (defects['totalNumberOfRecords']))
        report_info("building defects table and/or chart... ", True)
        return defects


# Extension setup
def setup(app):
    '''Extension setup'''
    # Create default configuration. Can be customized in conf.py
    app.add_config_value('coverity_credentials',
                         {
                             'hostname': 'scan.coverity.com',
                             'port': '8080',
                             'transport': 'http',
                             'username': 'reporter',
                             'password': 'coverity',
                             'stream': 'some_coverty_stream',
                         },
                         'env')

    app.add_config_value('TRACEABILITY_ITEM_ID_REGEX', r"([A-Z_]+-[A-Z0-9_]+)", 'env')
    app.add_config_value('TRACEABILITY_ITEM_RELINK', {}, 'env')

    app.add_node(CoverityDefect)

    sphinx_coverity_connector = SphinxCoverityConnector()

    app.add_directive('coverity-list', CoverityDefectListDirective)

    app.connect('doctree-resolved', sphinx_coverity_connector.process_coverity_nodes)

    app.connect('builder-inited', sphinx_coverity_connector.initialize_environment)

    try:
        version = pkg_resources.require('mlx.coverity')[0].version
    except LookupError:
        version = 'dev'
    return {
        'version': version,
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
