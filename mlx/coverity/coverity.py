# -*- coding: utf-8 -*-

"""
Coverity plugin

Sphinx extension for restructured text that adds Coverity reporting to documentation.
See README.rst for more details.
"""

from getpass import getpass
import logging
import os
from urllib.error import URLError, HTTPError
from sphinx.util.logging import getLogger, VERBOSITY_MAP

from docutils import nodes

from .__coverity_version__ import __version__
from .coverity_services import CoverityDefectService
from .coverity_directives.coverity_defect_list import (
    CoverityDefect,
    CoverityDefectListDirective,
)

LOGGER = getLogger("mlx.coverity")


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
            LOGGER.info("Initialize a session on Coverity server... ")
            self.coverity_service = CoverityDefectService(
                app.config.coverity_credentials["hostname"],
            )
            self.coverity_service.login(
                app.config.coverity_credentials["username"], app.config.coverity_credentials["password"]
            )
            LOGGER.info("done")
            LOGGER.info("Verify the given stream name... ")
            self.coverity_service.validate_stream(self.stream)
            LOGGER.info("done")
            if self.snapshot:
                LOGGER.info("Verify the given snapshot ID and obtain all enabled checkers... ")
                self.snapshot = self.coverity_service.validate_snapshot(self.snapshot)
                LOGGER.info("done")
            else:
                self.snapshot = "last()"
            # Get all column keys
            LOGGER.info("obtaining all column keys... ")
            self.coverity_service.retrieve_column_keys()
            LOGGER.info("done")
            # Get all checkers
            LOGGER.info("obtaining all checkers... ")
            self.coverity_service.retrieve_checkers()
            LOGGER.info("done")
        except (URLError, HTTPError, Exception, ValueError) as error_info:  # pylint: disable=broad-except
            if isinstance(error_info, EOFError):
                self.coverity_login_error_msg = "Coverity credentials are not configured."
            else:
                self.coverity_login_error_msg = str(error_info)
            LOGGER.info(f"failed with: {error_info}")
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
            LOGGER.warning(f"Connection failed: {self.coverity_login_error_msg}", location=fromdocname)
            return

        # Item matrix:
        # Create table with related items, printing their target references.
        # Only source and target items matching respective regexp shall be included
        for node in doctree.traverse(CoverityDefect):
            # Get items from server
            try:
                defects = self.get_filtered_defects(node)
            except URLError as err:
                error_message = f"failed to process coverity-list with {err!r}"
                LOGGER.warning(error_message, location=(fromdocname, node["line"]))
                top_node = node.create_top_node(node["title"])
                top_node += nodes.paragraph(text=error_message)
                node.replace_self(top_node)
                continue
            else:
                if defects["totalRows"] == -1:
                    error_message = "There are no defects with the specified filters"
                    LOGGER.warning(error_message, location=(fromdocname, node["line"]))
                else:
                    LOGGER.info("building defects table and/or chart... ")
                    node.perform_replacement(defects, self, app, fromdocname)
                    LOGGER.info("done")


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
        LOGGER.info("obtaining defects... ")
        column_names = set(node["col"])
        if "chart_attribute" in node and node["chart_attribute"].upper() in node.column_map:
            column_names.add(node["chart_attribute"])
        defects = self.coverity_service.get_defects(self.stream, node["filters"], column_names, self.snapshot)
        LOGGER.info("%d received" % (defects["totalRows"]))
        return defects

def validate_coverity_credentials(app):
    """Validate the configuration of coverity_credentials.

    Args:
        app (sphinx.application.Sphinx): Sphinx' application object.
    """
    for required_element in ["hostname", "username", "password", "stream"]:
        if required_element not in app.config.coverity_credentials:
            LOGGER.error(f"{required_element} is a required configuration in 'coverity_credentials' in conf.py")

# Extension setup
def setup(app):
    """Extension setup"""

    # Set logging level with --verbose (-v) option of Sphinx,
    # This option can be given up to three times to get more debug logging output.
    LOGGER.setLevel(VERBOSITY_MAP[app.verbosity])

    # Create default configuration. Can be customized in conf.py
    app.add_config_value(
        "coverity_credentials",
        {},
        "env",
        dict,
    )

    validate_coverity_credentials(app)

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
