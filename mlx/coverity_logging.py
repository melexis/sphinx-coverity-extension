""" Module to provide functions that accommodate logging while supporting different Sphinx versions. """
from sphinx import __version__ as sphinx_version
if sphinx_version >= '1.6.0':
    from sphinx.util.logging import getLogger


def report_warning(env, msg, docname, lineno=None):
    '''Convenience function for logging a warning

    Args:
        env (sphinx.environment.BuildEnvironment): Sphinx' build environment.
        msg (str): Message of the warning
        docname (str): Name of the document in which the error occurred
        lineno (str): Line number in the document on which the error occurred
    '''
    if sphinx_version >= '1.6.0':
        logger = getLogger(__name__)
        if lineno is not None:
            logger.warning(msg, location=(docname, lineno))
        else:
            logger.warning(msg, location=docname)
    else:
        env.warn(docname, msg, lineno=lineno)


def report_info(env, msg, nonl=False):
    '''Convenience function for information printing

    Args:
        env (sphinx.environment.BuildEnvironment): Sphinx' build environment.
        msg (str): Message of the warning
        nonl (bool): True when no new line at end
    '''
    if sphinx_version >= '1.6.0':
        logger = getLogger(__name__)
        logger.info(msg, nonl=nonl)
    else:
        env.info(msg, nonl=nonl)
