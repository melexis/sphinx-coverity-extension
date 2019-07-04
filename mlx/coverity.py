# -*- coding: utf-8 -*-

'''
Coverity plugin

Sphinx extension for restructured text that adds Coverity reporting to documentation.
See README.rst for more details.
'''
from __future__ import print_function

from hashlib import sha256
from os import environ, mkdir, path
from re import findall

import pkg_resources
from docutils import nodes
from docutils.parsers.rst import Directive, directives
from sphinx import __version__ as sphinx_version
from sphinx.environment import NoUri
if sphinx_version >= '1.6.0':
    from sphinx.util.logging import getLogger
from urlextract import URLExtract

from mlx.coverity_services import CoverityConfigurationService, CoverityDefectService
import matplotlib as mpl
if not environ.get('DISPLAY'):
    mpl.use('Agg')
import matplotlib.pyplot as plt  # noqa: E731

try:
    # For Python 3.0 and later
    from urllib.error import URLError, HTTPError
except ImportError:
    # Fall back to Python 2's urllib2
    from urllib2 import URLError, HTTPError


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


def initialize_table_from_node(node):
    """ Initializes a table node using the contents of a CoverityDefect node.

    Args:
        node (CoverityDefect): A CoverityDefect node object.

    Returns:
        (nodes.table, nodes.tbody) A table node and its body initialized with column widths and a table header.
    """
    table = nodes.table()
    table['classes'].append('longtable')
    if node['widths'] == 'auto':
        table['classes'].append('colwidths-auto')
    elif node['widths']:  # "grid" or list of integers
        table['classes'].append('colwidths-given')
    tgroup = nodes.tgroup()

    for _ in node['col']:
        tgroup += [nodes.colspec(colwidth=5)]
    tgroup += nodes.thead('', create_row(node['col']))

    if isinstance(node['widths'], list):
        colspecs = [child for child in tgroup.children if child.tagname == 'colspec']
        for colspec, col_width in zip(colspecs, node['widths']):
            colspec['colwidth'] = col_width

    tbody = nodes.tbody()
    tgroup += tbody
    table += tgroup
    return table, tbody


def pct_wrapper(sizes):
    """ Helper function for matplotlib which returns the percentage and the absolute size of the slice.

    Args:
        sizes (list): List containing the amount of elements per slice.
    """
    def make_pct(pct):
        absolute = int(round(pct / 100 * sum(sizes)))
        return "{:.0f}%\n({:d})".format(pct, absolute)
    return make_pct


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
         :widths: list of predefined column widths
         :chart: display chart that labels each allowed <<attribute>> value
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
        """
        Processes the contents of the directive
        """
        item_list_node = CoverityDefect('')

        # Process title (optional argument)
        if self.arguments:
            item_list_node['title'] = self.arguments[0]
        else:
            item_list_node['title'] = 'Coverity report'

        # Process ``col`` option
        if 'col' in self.options:
            item_list_node['col'] = self.options['col'].split(',')
        elif 'chart' not in self.options:
            item_list_node['col'] = 'CID,Classification,Action,Comment'.split(',')  # use default colums
        else:
            item_list_node['col'] = []  # don't display a table if the ``chart`` option is present without ``col``

        # Process ``widths`` option
        if 'widths' in self.options:
            item_list_node['widths'] = self.options['widths']
        else:
            item_list_node['widths'] = ''

        # Process ``chart`` option
        if 'chart' in self.options:
            if ':' in self.options['chart']:
                item_list_node['chart_attribute'] = self.options['chart'].split(':')[0].capitalize()
            else:
                item_list_node['chart_attribute'] = 'Classification'

            parameters = self.options['chart'].split(':')[-1]  # str
            item_list_node['chart'] = parameters.split(',')  # list
            # try to convert parameters to int, in case a min slice size is defined instead of filter options
            try:
                item_list_node['min_slice_size'] = int(item_list_node['chart'][0])
                item_list_node['chart'] = []  # only when a min slice size is defined
            except ValueError:
                item_list_node['min_slice_size'] = 1
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
    """
    Class containing functions and variables for Sphinx to access in specific stages of the documentation build.
    """
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
                table, tbody = initialize_table_from_node(node)

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

            # Initialize dictionary to store counters
            if isinstance(node['chart'], list):
                chart_labels = {}
                combined_labels = {}
                for label in node['chart']:
                    if '+' in label:
                        combined_labels[label] = label.split('+')
                    for attr_val in label.split('+'):
                        if attr_val in chart_labels.keys():
                            report_warning(env,
                                           "Attribute value '%s' should not be specified more than once in chart "
                                           "option." % attr_val,
                                           fromdocname)
                        chart_labels[attr_val] = 0
            column_map = {
                'Cid': 'cid',
                'Category': 'displayCategory',
                'Impact': 'displayImpact',
                'Issue': 'displayIssueKind',
                'Type': 'displayType',
                'Checker': 'checkerName',
                'Component': 'componentName',
            }
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
                                                       app.config.coverity_credentials['stream'],
                                                       str(defect['cid'])))
                            elif 'Location' == item_col:
                                info = self.coverity_service.get_defect(str(defect['cid']),
                                                                        app.config.coverity_credentials['stream'])
                                linenum = info[-1]['defectInstances'][-1]['events'][-1]['lineNumber']
                                row += create_cell("{}#L{}".format(defect['filePathname'], linenum))
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
                                text = str(cov_attribute_value_to_col(defect, 'Comment').children[0].children[0])
                                contents = create_paragraph_with_links(text, str(defect['cid']), app, fromdocname)
                                row += nodes.entry('', contents)
                            elif 'Reference' == item_col:
                                text = str(cov_attribute_value_to_col(defect, 'Ext. Reference').children[0].children[0])
                                contents = create_paragraph_with_links(text, str(defect['cid']), app, fromdocname)
                                row += nodes.entry('', contents)
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

                    if isinstance(node['chart'], list):
                        if node['chart_attribute'] in column_map.keys():
                            classification_value = str(defect[column_map[node['chart_attribute']]])
                        else:
                            col = cov_attribute_value_to_col(defect, node['chart_attribute'])
                            classification_value = str(col.children[0].children[0])  # get text in paragraph of column

                        if classification_value in chart_labels.keys():
                            chart_labels[classification_value] += 1
                        elif not node['chart']:  # remove those that don't comply with min_slice_length
                            chart_labels[classification_value] = 1

            except AttributeError as err:
                report_info(env, 'No issues matching your query or empty stream. %s' % err)
                top_node += nodes.paragraph(text='No issues matching your query or empty stream')

            if node['col']:
                top_node += table

            if isinstance(node['chart'], list):
                for new_label, old_labels in combined_labels.items():
                    count = 0
                    for old_label in old_labels:
                        count += chart_labels.pop(old_label)  # remove old_label and store its count
                    chart_labels[new_label] = count  # add combined count under new_label

                # only keep those labels that comply with the min_slice_size requirement
                chart_labels = {label: count for label, count in chart_labels.items()
                                if count >= node['min_slice_size']}

                total_labeled = sum(list(chart_labels.values()))
                other_count = defects['totalNumberOfRecords'] - total_labeled
                if other_count:
                    chart_labels['Other'] = other_count

                labels = list(chart_labels.keys())
                sizes = list(chart_labels.values())
                fig, axes = plt.subplots()
                fig.set_size_inches(7, 4)
                axes.pie(sizes, labels=labels, autopct=pct_wrapper(sizes), startangle=90)
                axes.axis('equal')
                folder_name = path.join(env.app.srcdir, '_images')
                if not path.exists(folder_name):
                    mkdir(folder_name)
                hash_string = ''
                for pie_slice in axes.__dict__['texts']:
                    hash_string += str(pie_slice)
                hash_value = sha256(hash_string.encode()).hexdigest()  # create hash value based on chart parameters
                rel_file_path = path.join('_images', 'piechart-{}.png'.format(hash_value))
                if rel_file_path not in env.images.keys():
                    fig.savefig(path.join(env.app.srcdir, rel_file_path), format='png')
                    # store file name in build env
                    env.images[rel_file_path] = ['_images', path.split(rel_file_path)[-1]]

                image_node = nodes.image()
                image_node['uri'] = rel_file_path
                image_node['candidates'] = '*'  # look at uri value for source path, relative to the srcdir folder
                top_node += image_node

            report_info(env, "done")
            node.replace_self(top_node)


def create_ref_node(contents, url):
    """ Creates reference node inside a paragraph

    Args:
        contents (str): Text to be displayed.
        url (str): URL to be used for the reference.

    Returns:
        (nodes.paragraph) Paragraph node containing a reference based on the given url.
    """
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
    """ Creates a container node containing an admonition with the given title inside.

    Args:
        title (str): Title text to be displayed.

    Returns:
        (nodes.container) Container node with the title laid out.
    """
    top_node = nodes.container()
    admon_node = nodes.admonition()
    title_node = nodes.title()
    title_node += nodes.Text(title)
    admon_node += title_node
    top_node += admon_node
    return top_node


def create_cell(contents, url=None):
    """
    Creates a table entry node with the given contents inside. If a string is given, it gets used inside a paragraph
    node, either as a text node or a reference node in case a URL is given.

    Args:
        contents (str|nodes.Node): Title text to be displayed.

    Returns:
        (nodes.entry) Entry node containing a paragraph with the given contents.
    """
    if isinstance(contents, str):
        if url is not None:
            contents = create_ref_node(contents, url)
        else:
            contents = nodes.paragraph(text=contents)

    return nodes.entry('', contents)


def create_row(cells):
    """ Creates a table row node containing the given strings inside entry nodes.

    Args:
        cells (list): List of strings to each be divided into cells.

    Returns:
        (nodes.row) Row node containing all given entry nodes.
    """
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


def create_paragraph_with_links(text, *args):
    """
    Create a paragraph with the provided text. Hyperlinks are made interactive, and traceability item IDs get linked to
    their definition.
    """
    contents = nodes.paragraph()
    remaining_text = text
    link_to_urls(contents, remaining_text, *args)
    return contents


def link_to_urls(contents, text, *args):
    """
    Makes URLs interactive and passes other text to link_to_item_ids, which treats the item IDs.
    """
    remaining_text = text
    extractor = URLExtract()
    urls = extractor.find_urls(remaining_text)
    for url in urls:
        text_before = remaining_text.split(url)[0]
        if text_before:
            link_to_item_ids(contents, text_before, *args)

        ref_node = nodes.reference()
        ref_node['refuri'] = url
        ref_node.append(nodes.Text(url))
        contents += ref_node

        remaining_text = remaining_text.replace(text_before + url, '', 1)

    if remaining_text:
        link_to_item_ids(contents, text, *args)


def link_to_item_ids(contents, text, cid, app, docname):
    """
    Makes a link of item IDs when they are found in a traceability collection and adds all other text to the paragraph.
    """
    remaining_text = text
    item_matches = findall(app.config.TRACEABILITY_ITEM_ID_REGEX, remaining_text)
    for item in item_matches:
        text_before = remaining_text.split(item)[0]
        if text_before:
            contents.append(nodes.Text(text_before))
        ref_node = make_internal_item_ref(app, docname, item, cid)
        if ref_node is None:  # no link could be made
            ref_node = nodes.Text(item)
        contents.append(ref_node)

        remaining_text = remaining_text.replace(text_before + item, '', 1)

    if remaining_text:
        contents.append(nodes.Text(remaining_text))  # no URL or item ID in this text


def make_internal_item_ref(app, fromdocname, item, cid):
    """
    Creates and returns a reference node for an item or returns None when the item cannot be found in the traceability
    collection. A warning is raised when a traceability collection exists, but an item ID cannot be found in it.
    """
    env = app.builder.env

    if not hasattr(env, 'traceability_collection'):
        return None

    item_info = env.traceability_collection.get_item(item)
    if not item_info:
        report_warning(env,
                       "CID %s: Could not find item ID '%s' in traceability collection." % (cid, item),
                       fromdocname)
        return None

    ref_node = nodes.reference('', '')
    ref_node['refdocname'] = item_info.docname
    try:
        ref_node['refuri'] = app.builder.get_relative_uri(fromdocname, item_info.docname) + '#' + item
    except NoUri:
        return None
    ref_node.append(nodes.Text(item))
    return ref_node


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

    app.add_node(CoverityDefect)

    sphinx_coverity_connector = SphinxCoverityConnector()

    app.add_directive('coverity-list', CoverityDefectListDirective)

    app.connect('doctree-resolved', sphinx_coverity_connector.process_coverity_nodes)

    app.connect('builder-inited', sphinx_coverity_connector.initialize_environment)

    try:
        return {'version': '%(prog)s {version}'.format(version=pkg_resources.require('mlx.coverity')[0].version)}
    except LookupError:
        return {'version': 'dev'}
