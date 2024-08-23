"""Module to provide functions that accommodate logging."""

from sphinx.util.logging import getLogger
from logging import WARNING

LOGGER = getLogger(__name__)
LOGGER.setLevel(WARNING)


def report_warning(msg, docname, lineno=None):
    """Convenience function for logging a warning

    Args:
        msg (str): Message of the warning
        docname (str): Name of the document in which the error occurred
        lineno (str): Line number in the document on which the error occurred
    """
    if lineno is not None:
        LOGGER.warning(msg, location=(docname, lineno))
    else:
        LOGGER.warning(msg, location=docname)


def report_info(msg, nonl=False):
    """Convenience function for information printing

    Args:
        msg (str): Message of the warning
        nonl (bool): True when no new line at end
    """
    LOGGER.info(msg, nonl=nonl)
