""" Module for the Coverity node base class. """
from re import findall

from docutils import nodes
from sphinx.errors import NoUri
from urlextract import URLExtract

from mlx.coverity_logging import report_warning


class ItemElement(nodes.General, nodes.Element):
    """ Base class for Coverity nodes. """

    @staticmethod
    def create_ref_node(contents, url):
        """ Creates reference node inside a paragraph.

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

    @staticmethod
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

    def create_cell(self, contents, url=None):
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
                contents = self.create_ref_node(contents, url)
            else:
                contents = nodes.paragraph(text=contents)

        return nodes.entry('', contents)

    def create_row(self, cells):
        """ Creates a table row node containing the given strings inside entry nodes.

        Args:
            cells (list): List of strings to each be divided into cells.

        Returns:
            (nodes.row) Row node containing all given entry nodes.
        """
        return nodes.row('', *[self.create_cell(c) for c in cells])

    def cov_attribute_value_to_col(self, defect, name):
        """
        Search defects array and return value for name
        """
        col = self.create_cell(" ")

        for attribute in defect['defectStateAttributeValues']:
            if attribute['attributeDefinitionId'][0] == name:
                try:
                    col = self.create_cell(attribute['attributeValueId'][0])
                except (AttributeError, IndexError):
                    col = self.create_cell(" ")
        return col

    def create_paragraph_with_links(self, defect, col_name, *args):
        """
        Create a paragraph with the provided text. Hyperlinks are made interactive, and traceability item IDs get linked
        to their definition.

        Args:
            defect (suds.sudsobject.mergedDefectDataObj): Defect object from suds.
            col_name (str): Column name according to suds.

        Returns:
            (nodes.paragraph) Paragraph node filled with column contents for the given defect. Item IDs and hyperlinks
                have been made interactive.
        """
        text = str(self.cov_attribute_value_to_col(defect, col_name).children[0].children[0])
        cid = str(defect['cid'])
        contents = nodes.paragraph()
        remaining_text = text
        self.link_to_urls(contents, remaining_text, cid, *args)
        return contents

    @staticmethod
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
    if not app.config.TRACEABILITY_ITEM_ID_REGEX:
        return  # empty string as regex to disable traceability link generation
    remaining_text = text
    item_matches = findall(app.config.TRACEABILITY_ITEM_ID_REGEX, remaining_text)
    for item in item_matches:
        text_before = remaining_text.split(item)[0]
        if text_before:
            contents.append(nodes.Text(text_before))
        remaining_text = remaining_text.replace(text_before + item, '', 1)

        if item in app.config.TRACEABILITY_ITEM_RELINK:
            item = app.config.TRACEABILITY_ITEM_RELINK[item]
        ref_node = make_internal_item_ref(app, docname, item, cid)
        if ref_node is None:  # no link could be made
            ref_node = nodes.Text(item)
        contents.append(ref_node)

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
        report_warning("CID %s: Could not find item ID '%s' in traceability collection." % (cid, item), fromdocname)
        return None
    ref_node = nodes.reference('', '')
    ref_node['refdocname'] = item_info.docname
    try:
        ref_node['refuri'] = app.builder.get_relative_uri(fromdocname, item_info.docname) + '#' + item
    except NoUri:
        return None
    ref_node.append(nodes.Text(item))
    return ref_node
