""" Module for the CoverityDefect class along with its directive. """
from hashlib import sha256
from os import environ, path
from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import Directive, directives
import matplotlib as mpl
if not environ.get('DISPLAY'):
    mpl.use('Agg')
import matplotlib.pyplot as plt

from mlx.coverity_logging import report_info, report_warning
from mlx.coverity_item_element import ItemElement


def pct_wrapper(sizes):
    """ Helper function for matplotlib which returns the percentage and the absolute size of the slice.

    Args:
        sizes (list): List containing the amount of elements per slice.
    """
    def make_pct(pct):
        absolute = int(round(pct / 100 * sum(sizes)))
        return "{:.0f}%\n({:d})".format(pct, absolute)
    return make_pct


class CoverityDefect(ItemElement):
    """Coverity defect"""

    stream = ''
    coverity_service = None
    tbody = None
    chart_labels = {}
    filters = {
        'checker': None,
        'impact': None,
        'kind': None,
        'classification': None,
        'action': None,
        'component': None,
        'cwe': None,
        'cid': None,
    }
    column_map = {
        'CID': 'cid',
        'CATEGORY': 'displayCategory',
        'IMPACT': 'displayImpact',
        'ISSUE': 'displayIssueKind',
        'TYPE': 'displayType',
        'CHECKER': 'checkerName',
        'COMPONENT': 'componentName',
    }
    defect_states_map = {
        'COMMENT': 'Comment',
        'REFERENCE': 'Ext. Reference',
        'CLASSIFICATION': 'Classification',
        'ACTION': 'Action',
        'STATUS': 'DefectStatus',
    }

    def perform_replacement(self, defects, connector, app, fromdocname):
        """ Replaces the empty node with a fully built CoverityDefect based on the given defects.

        Args:
            defects (suds.sudsobject.mergedDefectsPageDataObj): Suds mergedDefectsPageDataObj object containing filtered
                defects.
            connector (SphinxCoverityConnector): Object containing the stream and CoverityDefectService object in use.
            app (sphinx.application.Sphinx): Sphinx' application object.
            fromdocname (str): Relative path to the document in which the error occured, without extension.
        """
        env = app.builder.env
        self.stream = connector.stream
        self.coverity_service = connector.coverity_service
        top_node = self.create_top_node(self['title'])

        # Initialize table and dictionaries to store counters and labels for pie chart
        if self['col']:
            table = self.initialize_table()
        if isinstance(self['chart'], list):
            combined_labels = self.initialize_labels(self['chart'], fromdocname)

        # Fill table and increase counters for pie chart
        try:
            self.fill_table_and_count_attributes(defects['mergedDefects'], app, fromdocname)
        except AttributeError as err:
            report_info('No issues matching your query or empty stream. %s' % err)
            top_node += nodes.paragraph(text='No issues matching your query or empty stream')
            # don't generate empty pie chart image
            self.replace_self(top_node)
            return

        if self['col']:
            top_node += table

        if isinstance(self['chart'], list):
            self._prepare_labels_and_values(combined_labels, defects['totalNumberOfRecords'])
            top_node += self.build_pie_chart(env)

        report_info("done")
        self.replace_self(top_node)

    def initialize_table(self):
        """ Initializes a table node.

        Returns:
            (nodes.table) A table node initialized with column widths and a table header.
        """
        table = nodes.table()
        table['classes'].append('longtable')
        if self['widths'] == 'auto':
            table['classes'].append('colwidths-auto')
        elif self['widths']:  # "grid" or list of integers
            table['classes'].append('colwidths-given')
        tgroup = nodes.tgroup()

        for _ in self['col']:
            tgroup += [nodes.colspec(colwidth=5)]
        tgroup += nodes.thead('', self.create_row(self['col']))

        if isinstance(self['widths'], list):
            colspecs = [child for child in tgroup.children if child.tagname == 'colspec']
            for colspec, col_width in zip(colspecs, self['widths']):
                colspec['colwidth'] = col_width

        self.tbody = nodes.tbody()
        tgroup += self.tbody
        table += tgroup
        return table

    def initialize_labels(self, labels, docname):
        """
        Initialize dictionaries related to pie chart labels. The chart_labels class attribute is used for storing
        counters for each specified attribute value, and the returned dictionary is used for storing labels that consist
        of multiple attribute values that have been concatenated by a + character.

        Args:
            labels (list): List of labels (str) for the pie chart.
            docname (str): Name of the document in which the error occurred.

        Returns:
            (dict) Dictionary with the label_set arguments as keys and a list of associated attribute values as values.
        """
        self.chart_labels = {}
        combined_labels = {}
        for label in labels:
            attr_values = label.split('+')
            for attr_val in attr_values:
                if attr_val in self.chart_labels:
                    report_warning("Attribute value '%s' should be unique in chart option." % attr_val, docname)
                self.chart_labels[attr_val] = 0
            if len(attr_values) > 1:
                combined_labels[label] = attr_values
        return combined_labels

    def fill_table_and_count_attributes(self, defects, *args):
        """
        Fills the table body of the col option is in use, and counts the amount of each attribute value of the chart
        option is in use.

        Args:
            defects (list): List of defect objects (mergedDefectDataObj).
        """
        for defect in defects:
            if self['col']:
                self.tbody += self.get_filled_row(defect, self['col'], *args)

            if isinstance(self['chart'], list):
                self.increase_attribute_value_count(defect)

    def get_filled_row(self, defect, columns, *args):
        """ Goes through each column and decides if it is there or prints empty cell.

        Args:
            defect (suds.sudsobject.mergedDefectDataObj): Defect object from suds.
            columns (list): List of column names (str).

        Returns:
            (nodes.row) Filled row node.
        """
        row = nodes.row()
        for item_col in columns:
            item_col = item_col.upper()
            if item_col == 'CID':
                # CID is default and even if it is in disregard
                row += self.create_cell(str(defect['cid']),
                                        url=self.coverity_service.get_defect_url(self.stream, str(defect['cid'])))
            elif item_col == 'LOCATION':
                info = self.coverity_service.get_defect(str(defect['cid']),
                                                        self.stream)
                linenum = info[-1]['defectInstances'][-1]['events'][-1]['lineNumber']
                row += self.create_cell("{}#L{}".format(defect['filePathname'], linenum))
            elif item_col in self.column_map:
                row += self.create_cell(defect[self.column_map[item_col]])
            elif item_col in ('COMMENT', 'REFERENCE'):
                row += nodes.entry('', self.create_paragraph_with_links(defect,
                                                                        self.defect_states_map[item_col],
                                                                        *args))
            elif item_col in self.defect_states_map:
                row += self.cov_attribute_value_to_col(defect, self.defect_states_map[item_col])
            else:
                # generic check which, if it is missing, prints empty cell anyway
                row += self.cov_attribute_value_to_col(defect, item_col)
        return row

    def _prepare_labels_and_values(self, combined_labels, total_count):
        """ Prepares the labels and values to be used to build the pie chart.

        Args:
            combined_labels (dict): Dictionary with the label_set arguments as keys and a list of associated attribute
                values as values.
            total_count (int): Total amount of filtered defects.
        """
        for new_label, old_labels in combined_labels.items():
            count = 0
            for old_label in old_labels:
                count += self.chart_labels.pop(old_label)  # remove old_label and store its count
            self.chart_labels[new_label] = count  # add combined count under new_label

        # only keep those labels that comply with the min_slice_size requirement
        self.chart_labels = {label: count for label, count in self.chart_labels.items()
                             if count >= self['min_slice_size']}

        total_labeled = sum(list(self.chart_labels.values()))
        other_count = total_count - total_labeled
        if other_count:
            self.chart_labels['Other'] = other_count

    def build_pie_chart(self, env):
        """
        Builds and returns image node containing the pie chart image.

        Args:
            env (sphinx.environment.BuildEnvironment): Sphinx' build environment.

        Returns:
            (nodes.image) Image node containing the pie chart image.
        """
        labels = list(self.chart_labels)
        sizes = list(self.chart_labels.values())
        fig, axes = plt.subplots()
        fig.set_size_inches(7, 4)
        _, texts, autotexts = axes.pie(sizes, labels=labels, autopct=pct_wrapper(sizes), startangle=90)
        axes.axis('equal')
        Path(env.app.srcdir, '_images').mkdir(mode=0o777, parents=True, exist_ok=True)
        hash_string = str(texts) + str(autotexts)
        hash_value = sha256(hash_string.encode()).hexdigest()  # create hash value based on chart parameters
        rel_file_path = path.join('_images', 'piechart-{}.png'.format(hash_value))
        if rel_file_path not in env.images:
            fig.savefig(path.join(env.app.srcdir, rel_file_path), format='png')
            # store file name in build env
            env.images[rel_file_path] = ['_images', path.split(rel_file_path)[-1]]

        image_node = nodes.image()
        image_node['uri'] = rel_file_path
        image_node['candidates'] = '*'  # look at uri value for source path, relative to the srcdir folder
        return image_node

    def increase_attribute_value_count(self, defect):
        """ Increases the counter for a chart attribute value belonging to the defect.

        Args:
            defect (suds.sudsobject.mergedDefectDataObj): Defect object from suds.
        """
        if self['chart_attribute'].upper() in self.column_map:
            attribute_value = str(defect[self.column_map[self['chart_attribute'].upper()]])
        else:
            col = self.cov_attribute_value_to_col(defect, self['chart_attribute'])
            attribute_value = str(col.children[0].children[0])  # get text in paragraph of column

        if attribute_value in self.chart_labels:
            self.chart_labels[attribute_value] += 1
        elif not self['chart']:  # remove those that don't comply with min_slice_length
            self.chart_labels[attribute_value] = 1


class CoverityDefectListDirective(Directive):
    """ Directive to generate a list of defects.

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
        item_list_node = CoverityDefect()

        # Process title (optional argument)
        item_list_node['title'] = self.arguments[0] if self.arguments else 'Coverity report'

        # Process ``col`` option
        if 'col' in self.options:
            item_list_node['col'] = self.options['col'].split(',')
        elif 'chart' not in self.options:
            item_list_node['col'] = 'CID,Classification,Action,Comment'.split(',')  # use default colums
        else:
            item_list_node['col'] = []  # don't display a table if the ``chart`` option is present without ``col``

        # Process ``widths`` option
        item_list_node['widths'] = self.options['widths'] if 'widths' in self.options else ''

        # Process ``chart`` option
        if 'chart' in self.options:
            self._process_chart_option(item_list_node)
        else:
            item_list_node['chart'] = ''

        # Process the optional filters
        item_list_node['filters'] = {k: (self.options[k] if k in self.options else v)
                                     for (k, v) in item_list_node.filters.items()}
        return [item_list_node]

    def _process_chart_option(self, node):
        """ Processes the `chart` option.

        Args:
            node (CoverityDefect): CoverityDefect object used to store this directive's options and their parameters.
        """
        if ':' in self.options['chart']:
            node['chart_attribute'] = self.options['chart'].split(':')[0].capitalize()
        else:
            node['chart_attribute'] = 'Classification'

        parameters = self.options['chart'].split(':')[-1]  # str
        node['chart'] = parameters.split(',')  # list
        # try to convert parameters to int, in case a min slice size is defined instead of filter options
        try:
            node['min_slice_size'] = int(node['chart'][0])
            node['chart'] = []  # only when a min slice size is defined
        except ValueError:
            node['min_slice_size'] = 1
