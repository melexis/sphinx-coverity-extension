# -*- coding: utf-8 -*-

'''
Coverity plugin

Sphinx extension for restructured text that adds Coverity reporting to documentation.
See README.rst for more details.
'''

from __future__ import print_function
import pkg_resources

from docutils.parsers.rst import Directive
from docutils import nodes
from docutils.parsers.rst import directives
from mlx.coverity_services import CoverityConfigurationService, CoverityDefectService
try:
    # For Python 3.0 and later
    from urllib.error import URLError, HTTPError
except ImportError:
    # Fall back to Python 2's urllib2
    from urllib2 import URLError, HTTPError
from sphinx import __version__ as sphinx_version
if sphinx_version >= '1.6.0':
    from sphinx.util.logging import getLogger


def report_warning(env, msg, docname, lineno=None):
    '''Convenience function for logging a warning

    Args:
        msg (str): Message of the warning
        docname (str): Name of the document on which the error occured
        lineno (str): Line number in the document on which the error occured
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
        msg (str): Message of the warning
        nonl (bool): True when no new line at end
    '''
    if sphinx_version >= '1.6.0':
        logger = getLogger(__name__)
        logger.info(msg, nonl=nonl)
    else:
        env.info(msg, nonl=nonl)


# -----------------------------------------------------------------------------
# Declare new node types (based on others):
class CoverityDefect(nodes.General, nodes.Element):
    '''Coverity defect'''
    pass


# -----------------------------------------------------------------------------
# Directives
class CoverityDefectListDirective(Directive):
    """
    Directive to generate a list of defects.

    Syntax::

      .. coverity-list:: title
         :col: list of columns to be displayed
         :chart: display chart that labels each specified classification
         :checker: filter for only these checkers
         :impact: filter for only these impacts
         :kind: filter for only these kinds
         :classification: filter for only these classifications
         :action: filter for only these actions
         :component: filter for only these components
         :cwe: filter for only these CWE rating
         :cid: filter only these cid
    """
    # Optional argument: title (whitespace allowed)
    optional_arguments = 1
    final_argument_whitespace = True
    # Options
    option_spec = {'class': directives.class_option,
                   'col': directives.unchanged,
                   'widths': directives.value_or(('auto', 'grid'),
                                                 directives.positive_int_list),
                   'chart': directives.unchanged,
                   'checker': directives.unchanged,
                   'impact': directives.unchanged,
                   'kind': directives.unchanged,
                   'classification': directives.unchanged,
                   'action': directives.unchanged,
                   'component': directives.unchanged,
                   'cwe': directives.unchanged,
                   'cid': directives.unchanged,
                   }
    # Content disallowed
    has_content = False

    def run(self):
        item_list_node = CoverityDefect('')

        # Process title (optional argument)
        if len(self.arguments) > 0:
            item_list_node['title'] = self.arguments[0]
        else:
            item_list_node['title'] = 'Coverity report'

        # Process ``col`` option
        if 'col' in self.options:
            item_list_node['col'] = self.options['col'].split(',')
        elif 'chart' not in self.options:
            item_list_node['col'] = 'CID,Classification,Action,Comment'.split(',')
        else:
            item_list_node['col'] = []  # don't display a table if the ``chart`` option is present

        # Process ``widths`` option
        if 'widths' in self.options:
            item_list_node['widths'] = self.options['widths']
        else:
            item_list_node['widths'] = ''

        # Process ``chart`` option
        if 'chart' in self.options:
            item_list_node['chart'] = self.options['chart']
        else:
            item_list_node['chart'] = ''

        # Process the optional filters
        filters = ['checker', 'impact', 'kind', 'classification', 'action', 'component', 'cwe', 'cid']
        for fil in filters:
            if fil in self.options:
                item_list_node[fil] = self.options[fil]
            else:
                item_list_node[fil] = None

        return [item_list_node]


class SphinxCoverityConnector():
    def __init__(self):
        """
        Initialize the object by setting error variable to false
        """
        self.coverity_login_error = False

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

        env = app.builder.env

        # Login to Coverity and obtain stream information
        try:
            report_info(env, 'Login to Coverity server... ', True)
            coverity_conf_service = CoverityConfigurationService(app.config.coverity_credentials['transport'],
                                                                 app.config.coverity_credentials['hostname'],
                                                                 app.config.coverity_credentials['port'])
            coverity_conf_service.login(app.config.coverity_credentials['username'],
                                        app.config.coverity_credentials['password'])
            report_info(env, 'done')

            report_info(env, 'obtaining stream information... ', True)
            stream = coverity_conf_service.get_stream(app.config.coverity_credentials['stream'])
            if stream is None:
                raise ValueError('No such Coverity stream [%s] found on [%s]' %
                                 (app.config.coverity_credentials['stream'], coverity_conf_service.get_service_url()))
            report_info(env, 'done')

            # Get Stream's project name
            report_info(env, 'obtaining project name from stream... ', True)
            self.project_name = coverity_conf_service.get_project_name(stream)
            report_info(env, 'done')
            self.coverity_service = CoverityDefectService(coverity_conf_service)
            self.coverity_service.login(app.config.coverity_credentials['username'],
                                        app.config.coverity_credentials['password'])
        except (URLError, HTTPError, Exception, ValueError) as error_info:
            self.coverity_login_error_msg = error_info
            report_info(env, 'failed with: %s' % error_info)
            self.coverity_login_error = True

    # -----------------------------------------------------------------------------
    # Event handlers
    def process_coverity_nodes(self, app, doctree, fromdocname):
        """
        This function should be triggered upon ``doctree-resolved event``

        Obtain information from Coverity server and generate a table.
        """
        env = app.builder.env

        if self.coverity_login_error:
            # Create failed topnode
            for node in doctree.traverse(CoverityDefect):
                top_node = create_top_node("Failed to connect to Coverity Server")
                node.replace_self(top_node)
            report_warning(env, 'Connection failed: %s' % self.coverity_login_error_msg, fromdocname)
            return

        # Item matrix:
        # Create table with related items, printing their target references.
        # Only source and target items matching respective regexp shall be included
        for node in doctree.traverse(CoverityDefect):
            top_node = create_top_node(node['title'])

            # Initialize table
            if node['col']:
                table = nodes.table()
                table.set_class('longtable')
                if node['widths'] == 'auto':
                    table['classes'] += ['colwidths-auto']
                elif node['widths']:  # "grid" or list of integers
                    table['classes'] += ['colwidths-given']
                tgroup = nodes.tgroup()

                for _ in node['col']:
                    tgroup += [nodes.colspec(colwidth=5)]

                tgroup += nodes.thead('', create_row(node['col']))

                if isinstance(node['widths'], list):
                    colspecs = [child for child in tgroup.children
                                if child.tagname == 'colspec']
                    for colspec, col_width in zip(colspecs, node['widths']):
                        colspec['colwidth'] = col_width

                tbody = nodes.tbody()

                tgroup += tbody
                table += tgroup

            # Initialize dictionary to store counters
            if node['chart']:
                classification_count = {}
                for label in node['chart'].split(','):
                    classification_count[tuple(label.split('+'))] = 0

            # Get items from server
            report_info(env, 'obtaining defects... ', True)
            try:
                defects = self.coverity_service.get_defects(self.project_name, app.config.coverity_credentials['stream'],   # noqa: E501
                                                            checker=node['checker'], impact=node['impact'], kind=node['kind'],  # noqa: E501
                                                            classification=node['classification'], action=node['action'],   # noqa: E501
                                                            component=node['component'], cwe=node['cwe'], cid=node['cid'])  # noqa: E501
            except (URLError, AttributeError, Exception) as err:
                report_warning(env, 'failed with %s' % err, fromdocname)
                continue
            report_info(env, "%d received" % (defects['totalNumberOfRecords']))
            report_info(env, "building defects table and/or chart... ", True)

            try:
                for defect in defects['mergedDefects']:
                    if node['col']:
                        row = nodes.row()

                        # go through each col and decide if it is there or we print empty
                        for item_col in node['col']:
                            if 'CID' == item_col:
                                # CID is default and even if it is in disregard
                                row += create_cell(str(defect['cid']),
                                                   url=self.coverity_service.get_defect_url(
                                                       app.config.coverity_credentials['stream'],  # noqa: E501
                                                       str(defect['cid'])))
                            elif 'Category' == item_col:
                                row += create_cell(defect['displayCategory'])
                            elif 'Impact' == item_col:
                                row += create_cell(defect['displayImpact'])
                            elif 'Issue' == item_col:
                                row += create_cell(defect['displayIssueKind'])
                            elif 'Type' == item_col:
                                row += create_cell(defect['displayType'])
                            elif 'Checker' == item_col:
                                row += create_cell(defect['checkerName'])
                            elif 'Component' == item_col:
                                row += create_cell(defect['componentName'])
                            elif 'Comment' == item_col:
                                row += cov_attribute_value_to_col(defect, 'Comment')
                            elif 'Classification' == item_col:
                                row += cov_attribute_value_to_col(defect, 'Classification')
                            elif 'Action' == item_col:
                                row += cov_attribute_value_to_col(defect, 'Action')
                            elif 'Status' == item_col:
                                row += cov_attribute_value_to_col(defect, 'DefectStatus')
                            else:
                                # generic check which, if it is missing, prints empty cell anyway
                                row += cov_attribute_value_to_col(defect, item_col)
                        tbody += row

                    if node['chart']:
                        col = cov_attribute_value_to_col(defect, 'Classification')
                        classification_value = col.children[0].children[0]  # get text in paragraph of column
                        for label in classification_count.keys():
                            if classification_value in label:
                                classification_count[label] += 1

            except AttributeError as err:
                report_info(env, 'No issues matching your query or empty stream. %s' % err)
                top_node += nodes.paragraph(text='No issues matching your query or empty stream')

            if node['col']:
                top_node += table

            if node['chart']:
                total_defects = defects['totalNumberOfRecords']
                total_labeled = 0
                for count in classification_count.values():
                    total_labeled += count
                classification_count[('other', )] = total_defects - total_labeled
                top_node += nodes.paragraph(text=str(classification_count))

            report_info(env, "done")
            node.replace_self(top_node)
    #        try:
    #            percentage = int(100 * count_covered / count_total)
    #        except ZeroDivisionError:
    #            percentage = 0
    #        disp = 'Statistics: {cover} out of {total} covered: {pct}%'.format(cover=count_covered,
    #                                                                           total=count_total,
    #                                                                           pct=percentage)
    #        if node['graph']:
    #            p_node = nodes.paragraph()
    #            txt = nodes.Text(disp)
    #            p_node += txt
    #            top_node += p_node
    #
    #        top_node += table
    #


def create_ref_node(contents, url):
    p_node = nodes.paragraph()
    itemlink = nodes.reference()
    itemlink['refuri'] = url
    itemlink.append(nodes.Text(contents))
    targetid = nodes.make_id(contents)
    target = nodes.target('', '', ids=[targetid])
    p_node += target
    p_node += itemlink
    return p_node


def create_top_node(title):
    top_node = nodes.container()
    admon_node = nodes.admonition()
    title_node = nodes.title()
    title_node += nodes.Text(title)
    admon_node += title_node
    top_node += admon_node
    return top_node


def create_cell(contents, url=None):
    if isinstance(contents, str):
        if url is not None:
            contents = create_ref_node(contents, url)
        else:
            contents = nodes.paragraph(text=contents)

    return nodes.entry('', contents)


def create_row(cells):
    return nodes.row('', *[create_cell(c) for c in cells])


def cov_attribute_value_to_col(defect, name):
    """
        Search defects array and return value for name
    """
    col = create_cell(" ")

    for attribute in defect['defectStateAttributeValues']:
        if attribute['attributeDefinitionId'][0] == name:
            try:
                col = create_cell(attribute['attributeValueId'][0])
            except (AttributeError, IndexError):
                col = create_cell(" ")
    return col


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

    app.add_node(CoverityDefect)

    sphinx_coverity_connector = SphinxCoverityConnector()

    app.add_directive('coverity-list', CoverityDefectListDirective)

    app.connect('doctree-resolved', sphinx_coverity_connector.process_coverity_nodes)

    app.connect('builder-inited', sphinx_coverity_connector.initialize_environment)

    try:
        return {'version': '%(prog)s {version}'.format(version=pkg_resources.require('mlx.coverity')[0].version)}
    except LookupError:
        return {'version': 'dev'}
