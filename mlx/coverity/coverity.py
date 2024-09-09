# -*- coding: utf-8 -*-

"""
Coverity plugin

Sphinx extension for restructured text that adds Coverity reporting to documentation.
See README.rst for more details.
"""

from getpass import getpass
from urllib.error import URLError, HTTPError

from docutils import nodes

from .__coverity_version__ import __version__
from .coverity_logging import report_info, report_warning
from .coverity_services import CoverityDefectService
from .coverity_directives.coverity_defect_list import (
    CoverityDefect,
    CoverityDefectListDirective,
)


class SphinxCoverityConnector:
    """
    Class containing functions and variables for Sphinx to access in specific stages of the documentation build.
    """

    def __init__(self):
        """
        Initialize the object by setting error variable to false
        """
        self.coverity_login_error = False
        self.coverity_login_error_msg = ""

    def initialize_environment(self, app):
        """
        Perform initializations needed before the build process starts.
        """
        # LaTeX-support: since we generate empty tags, we need to relax the verbosity of that error
        if "preamble" not in app.config.latex_elements:
            app.config.latex_elements["preamble"] = ""
        app.config.latex_elements["preamble"] += r"""
    \\makeatletter
    \\let\@noitemerr\\relax
    \\makeatother"""

        self.stream = app.config.coverity_credentials["stream"]
        self.snapshot = app.config.coverity_credentials.get("snapshot", "")
        # Login to Coverity and obtain stream information
        try:
            self.input_credentials(app.config.coverity_credentials)
            report_info("Initialize a session on Coverity server... ", True)
            self.coverity_service = CoverityDefectService(
                app.config.coverity_credentials["hostname"],
            )
            self.coverity_service.login(
                app.config.coverity_credentials["username"], app.config.coverity_credentials["password"]
            )
            report_info("done")
            report_info("Verify the given stream name... ")
            self.coverity_service.validate_stream(self.stream)
            report_info("done")
            if self.snapshot:
                report_info("Verify the given snapshot ID and obtain all enabled checkers... ")
                self.snapshot = self.coverity_service.validate_snapshot(self.snapshot)
                report_info("done")
            else:
                self.snapshot = "last()"
            # Get all column keys
            report_info("obtaining all column keys... ")
            self.coverity_service.retrieve_column_keys()
            report_info("done")
            # Get all checkers
            report_info("obtaining all checkers... ")
            self.coverity_service.retrieve_checkers()
            report_info("done")
        except (URLError, HTTPError, Exception, ValueError) as error_info:  # pylint: disable=broad-except
            if isinstance(error_info, EOFError):
                self.coverity_login_error_msg = "Coverity credentials are not configured."
            else:
                self.coverity_login_error_msg = str(error_info)
            report_info("failed with: %s" % error_info)
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
            report_warning("Connection failed: %s" % self.coverity_login_error_msg, fromdocname)
            return

        # Item matrix:
        # Create table with related items, printing their target references.
        # Only source and target items matching respective regexp shall be included
        for node in doctree.traverse(CoverityDefect):
            # Get items from server
            try:
                defects = self.get_filtered_defects(node)
                if defects["totalRows"] == -1:
                    error_message = "There are no defects with the specified filters"
                    report_warning(error_message, fromdocname, lineno=node["line"])
                else:
                    report_info("building defects table and/or chart... ", True)
                    node.perform_replacement(defects, self, app, fromdocname)
                    report_info("done")
            except (URLError, AttributeError, Exception) as err:  # pylint: disable=broad-except
                error_message = f"failed to process coverity-list with {err!r}"
                report_warning(error_message, fromdocname, lineno=node["line"])
                top_node = node.create_top_node(node["title"])
                top_node += nodes.paragraph(text=error_message)
                node.replace_self(top_node)
                continue

    # -----------------------------------------------------------------------------
    # Helper functions of event handlers
    @staticmethod
    def input_credentials(config_credentials):
        """Ask user to input username and/or password if they haven't been configured yet.

        Args:
            config_credentials (dict): Dictionary to store the user's credentials.
        """
        if not config_credentials["username"]:
            config_credentials["username"] = input("Coverity username: ")
        if not config_credentials["password"]:
            config_credentials["password"] = getpass("Coverity password: ")

    def get_filtered_defects(self, node):
        """Fetch defects from REST API using filters stored in the given CoverityDefect object.

        Args:
            node (CoverityDefect): CoverityDefect object with zero or more filters stored.

        Returns:
            dict: The content of the request to retrieve defects. This has a structure like:
                {
                    "offset": 0,
                    "totalRows": 2720,
                    "columns": [list of column keys]
                    "rows": [list of dictionaries {"key": <key>, "value": <value>}]
                }
        """
        report_info("obtaining defects... ")
        column_names = set(node["col"])
        if "chart_attribute" in node and node["chart_attribute"].upper() in node.column_map:
            column_names.add(node["chart_attribute"])
        defects = self.coverity_service.get_defects(self.stream, node["filters"], column_names, self.snapshot)
        report_info("%d received" % (defects["totalRows"]))
        return defects


# Extension setup
def setup(app):
    """Extension setup"""
    # Create default configuration. Can be customized in conf.py
    app.add_config_value(
        "coverity_credentials",
        {
            "hostname": "scan.coverity.com",
            "username": "reporter",
            "password": "coverity",
            "stream": "some_stream",
        },
        "env",
    )

    app.add_config_value("TRACEABILITY_ITEM_ID_REGEX", r"([A-Z_]+-[A-Z0-9_]+)", "env")
    app.add_config_value("TRACEABILITY_ITEM_RELINK", {}, "env")

    app.add_node(CoverityDefect)

    sphinx_coverity_connector = SphinxCoverityConnector()

    app.add_directive("coverity-list", CoverityDefectListDirective)

    app.connect("doctree-resolved", sphinx_coverity_connector.process_coverity_nodes)

    app.connect("builder-inited", sphinx_coverity_connector.initialize_environment)

    try:
        version = __version__
    except LookupError:
        version = "dev"
    return {
        "version": version,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
