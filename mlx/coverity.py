# -*- coding: utf-8 -*-

'''
Traceability plugin

Sphinx extension for restructured text that added traceable documentation items.
See readme for more details.
'''

from __future__ import print_function
import re
from docutils.parsers.rst import Directive
from sphinx.roles import XRefRole
from sphinx.util.nodes import make_refnode
from sphinx.environment import NoUri
from docutils import nodes
from docutils.parsers.rst import directives
from docutils.utils import get_source_line
from mlx.coverity_services import CoverityConfigurationService, CoverityDefectService, ISSUE_KIND_2_LABEL
from setuptools_scm import get_version
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
         :graph: display graphs on end of list
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
                   'graph': directives.unchanged,
                   'checker': directives.unchanged,
                   'impact': directives.unchanged,
                   'kind': directives.unchanged,
                   'classification': directives.unchanged,
                   'action': directives.unchanged,
                   'component': directives.unchanged,
                   'cwe': directives.unchanged,
                   'cid': directives.unchanged
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
        else:
            item_list_node['col'] = 'CID,State,Classification,Action,Checker,Comment'.split(',')

        # Process ``graph`` option
        if 'graph' in self.options:
            item_list_node['graph'] = self.options['graph']
        else:
            item_list_node['graph'] = ''

        # Process even more optional filters ``checker`` option
        filters = ['checker', 'impact', 'kind', 'classification', 'action', 'component', 'cwe', 'cid']
        for fil in filters:
            if fil in self.options:
                item_list_node[fil] = self.options[fil]
            else:
                item_list_node[fil] = None

        return [item_list_node]


class ItemMatrixDirective(Directive):
    """
    Directive to generate a matrix of item cross-references, based on
    a given set of relationship types.

    Syntax::

      .. item-matrix:: title
         :target: regexp
         :source: regexp
         :targettitle: Target column header
         :sourcetitle: Source column header
         :type: <<relationship>> ...
         :stats:

    """
    # Optional argument: title (whitespace allowed)
    optional_arguments = 1
    final_argument_whitespace = True
    # Options
    option_spec = {'class': directives.class_option,
                   'target': directives.unchanged,
                   'source': directives.unchanged,
                   'targettitle': directives.unchanged,
                   'sourcetitle': directives.unchanged,
                   'type': directives.unchanged,
                   'stats': directives.flag}
    # Content disallowed
    has_content = False

    def run(self):
        env = self.state.document.settings.env

        item_matrix_node = ItemMatrix('')

        # Process title (optional argument)
        if len(self.arguments) > 0:
            item_matrix_node['title'] = self.arguments[0]
        else:
            item_matrix_node['title'] = 'Traceability matrix of items'

        # Process ``target`` & ``source`` options
        for option in ('target', 'source'):
            if option in self.options:
                item_matrix_node[option] = self.options[option]
            else:
                item_matrix_node[option] = ''

        # Process ``type`` option, given as a string with relationship types
        # separated by space. It is converted to a list.
        if 'type' in self.options:
            item_matrix_node['type'] = self.options['type'].split()
        else:
            item_matrix_node['type'] = []

        # Check if given relationships are in configuration
        for rel in item_matrix_node['type']:
            if rel not in env.traceability_collection.iter_relations():
                report_warning(env, 'Traceability: unknown relation for item-matrix: %s' % rel,
                               env.docname, self.lineno)

        # Check statistics flag
        if 'stats' in self.options:
            item_matrix_node['stats'] = True
        else:
            item_matrix_node['stats'] = False

        # Check source title
        if 'sourcetitle' in self.options:
            item_matrix_node['sourcetitle'] = self.options['sourcetitle']
        else:
            item_matrix_node['sourcetitle'] = 'Source'

        # Check target title
        if 'targettitle' in self.options:
            item_matrix_node['targettitle'] = self.options['targettitle']
        else:
            item_matrix_node['targettitle'] = 'Target'

        return [item_matrix_node]


# -----------------------------------------------------------------------------
# Event handlers

def perform_consistency_check(app, doctree):

    '''
    New in sphinx 1.6: consistency checker callback

    Used to perform the self-test on the collection of items
    '''
    env = app.builder.env

    try:
        env.traceability_collection.self_test()
    except TraceabilityException as err:
        report_warning(env, err, err.get_document())
    except MultipleTraceabilityExceptions as errs:
        for err in errs.iter():
            report_warning(env, err, err.get_document())

def process_item_nodes(app, doctree, fromdocname):
    """
    This function should be triggered upon ``doctree-resolved event``

    Replace all ItemList nodes with a list of the collected items.
    Augment each item with a backlink to the original location.

    """
    env = app.builder.env

    if sphinx_version < '1.6.0':
        try:
            env.traceability_collection.self_test(fromdocname)
        except CoverityException as err:
            report_warning(env, err, fromdocname)
        except MultipleCoverityExceptions as errs:
            for err in errs.iter():
                report_warning(env, err, err.get_document())

    # Login to Coverity and obtain stream information
    coverity_conf_service = CoverityConfigurationService(app.config.coverity_credentials['transport'],\
            app.config.coverity_credentials['hostname'], app.config.coverity_credentials['port'])
    print("Login to Coverity server... ", end='')
    coverity_conf_service.login(app.config.coverity_credentials['username'], app.config.coverity_credentials['password'])
    print("done")
    print("obtaining stream information... ", end='')
    stream = coverity_conf_service.get_stream(app.config.coverity_credentials['stream'])
    if stream is None:
        print("failed")
        raise ValueError('No such Coverity stream [%s] found on [%s]',\
                app.config.coverity_credentials['stream'], coverity_conf_service.get_service_url())
    print("done")

    # Get Stream's project name
    print("obtaining project name from stream... ", end='')
    project_name = coverity_conf_service.get_project_name(stream)
    print("done")
    coverity_service = CoverityDefectService(coverity_conf_service)
    coverity_service.login(app.config.coverity_credentials['username'], app.config.coverity_credentials['password'])

    # Item matrix:
    # Create table with related items, printing their target references.
    # Only source and target items matching respective regexp shall be included
    for node in doctree.traverse(CoverityDefect):
        top_node = create_top_node(node['title'])
        table = nodes.table()
        tgroup = nodes.tgroup()
        tgroup += [nodes.colspec(colwidth=5)]
        tgroup += nodes.thead('', create_row(node['col']))

        tbody = nodes.tbody()
        for c in node['col']:
            print(c)
        count_total = 0
        count_covered = 0

        # Get items from server
        print("obtaining defects... ", end='')
        defects = coverity_service.get_defects(project_name, app.config.coverity_credentials['stream'],\
                checker=node['checker'], impact=node['impact'], kind=node['kind'], classification=node['classification'], action=node['action'], component=node['component'], cwe=node['cwe'], cid=node['cid'])
        print("%d received"% (defects['totalNumberOfRecords']))
        print("building defects table... ", end='')
        for defect in defects['mergedDefects']:
            row = nodes.row()
            col = create_cell(str(defect['cid']))

            # go through each col and decide if it is there or we print empty
            for item_col in node['col']:
                if 'CID' == item_col:
                    # CID is default and even if it is in disregard
                    continue
                elif 'Category' == item_col:
                    col += create_cell(defect['displayCategory'])
                elif 'Impact' == item_col:
                    col += create_cell(defect['displayImpact'])
                elif 'Issue' == item_col:
                    col += create_cell(defect['displayIssueKind'])
                elif 'Type' == item_col:
                    col += create_cell(defect['displayType'])
                elif 'Comment' == item_col:
                    col += cov_attribute_value_to_col(defect, 'Comment')
                elif 'Classification' == item_col:
                    col += cov_attribute_value_to_col(defect, 'Classification')
                elif 'Action' == item_col:
                    col += cov_attribute_value_to_col(defect, 'Action')
                elif 'Checker' == item_col:
                    col += cov_attribute_value_to_col(defect, 'Checker')
                elif 'State' == item_col:
                    col += cov_attribute_value_to_col(defect, 'State')
                else:
                    # generic check which if it is missing prints empty cell anyway
                    col += cov_attribute_value_to_col(defect, item_col)

            row += col
            tbody += row
        print("done")
        tgroup += tbody
        table += tgroup
        top_node += table
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
def create_top_node(title):
    top_node = nodes.container()
    admon_node = nodes.admonition()
    title_node = nodes.title()
    title_node += nodes.Text(title)
    admon_node += title_node
    top_node += admon_node
    return top_node

def create_cell(contents):
    if isinstance(contents, basestring):
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
            except AttributeError as e:
                col = create_cell(" ")
    return col

def initialize_environment(app):
    """
    Perform initializations needed before the build process starts.
    """
    env = app.builder.env

    # LaTeX-support: since we generate empty tags, we need to relax the verbosity of that error
    if 'preamble' not in app.config.latex_elements:
        app.config.latex_elements['preamble'] = ''
    app.config.latex_elements['preamble'] += '''\
\\makeatletter
\\let\@noitemerr\\relax
\\makeatother'''


def make_item_ref(app, node, fromdocname, item_id, caption=True):
    """
    Creates a reference node for an item, embedded in a
    paragraph. Reference text adds also a caption if it exists.

    """
    env = app.builder.env
    item_info = env.traceability_collection.get_item(item_id)

    p_node = nodes.paragraph()

    # Only create link when target item exists, warn otherwise (in html and terminal)
    if item_info.is_placeholder():
        docname, lineno = get_source_line(node)
        report_warning(env, 'Traceability: cannot link to %s, item is not defined' % item_id,
                       docname, lineno)
        txt = nodes.Text('%s not defined, broken link' % item_id)
        p_node.append(txt)
    else:
        if item_info.caption != '' and caption:
            caption = ' : ' + item_info.caption
        else:
            caption = ''

        newnode = nodes.reference('', '')
        innernode = nodes.emphasis(item_id + caption, item_id + caption)
        newnode['refdocname'] = item_info.docname
        try:
            newnode['refuri'] = app.builder.get_relative_uri(fromdocname,
                                                             item_info.docname)
            newnode['refuri'] += '#' + item_id
        except NoUri:
            # ignore if no URI can be determined, e.g. for LaTeX output :(
            pass
        newnode.append(innernode)
        p_node += newnode

    return p_node


# Extension setup

def setup(app):
    '''Extension setup'''

    # Create default configuration. Can be customized in conf.py
    app.add_config_value('coverity_credentials',
                         {'hostname': 'scan.coverity.com',
                          'port': '8080',
                          'transport': 'http',
                          'username': 'reporter',
                          'password': 'coverity',
                          'stream': 'some_coverty_stream',},
                         'env')

    app.add_node(CoverityDefect)

    app.add_directive('coverity-list', CoverityDefectListDirective)

    app.connect('doctree-resolved', process_item_nodes)

    app.connect('builder-inited', initialize_environment)

    try:
        return {'version': get_version()}
    except LookupError as e:
        return {'version': 'dev'}
