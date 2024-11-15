"""Module for the Coverity node base class."""

from re import findall

from docutils import nodes
from sphinx.errors import NoUri
from urlextract import URLExtract
from sphinx.util.logging import getLogger


LOGGER = getLogger("mlx.coverity")


class ItemElement(nodes.General, nodes.Element):
    """Base class for Coverity nodes."""

    @staticmethod
    def create_ref_node(contents, url):
        """Creates reference node inside a paragraph.

        Args:
            contents (str): Text to be displayed.
            url (str): URL to be used for the reference.

        Returns:
            (nodes.paragraph) Paragraph node containing a reference based on the given url.
        """
        p_node = nodes.paragraph()
        itemlink = nodes.reference()
        itemlink["refuri"] = url
        itemlink.append(nodes.Text(contents))
        targetid = nodes.make_id(contents)
        target = nodes.target("", "", ids=[targetid])
        p_node += target
        p_node += itemlink
        return p_node

    @staticmethod
    def create_top_node(title):
        """Creates a container node containing an admonition with the given title inside.

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

        return nodes.entry("", contents)

    def create_row(self, cells):
        """Creates a table row node containing the given strings inside entry nodes.

        Args:
            cells (list): List of strings to each be divided into cells.

        Returns:
            (nodes.row) Row node containing all given entry nodes.
        """
        return nodes.row("", *[self.create_cell(c) for c in cells])

    def cov_attribute_value_to_col(self, defect, name):
        """
        Create cell with the value in the defect for the given name.

        Args:
            defect (dict): The defect where the keys are column keys and the values are the corresponding defect values
            name (str): The key name of the attribute

        Returns:
            (nodes.entry) Entry node containing a paragraph with the given contents
        """
        if name in defect:
            col = self.create_cell(defect[name])
        else:
            col = self.create_cell(" ")
        return col

    def create_paragraph_with_links(self, defect, col_key, *args):
        """
        Create a paragraph with the provided text. Hyperlinks are made interactive, and traceability item IDs get linked
        to their definition.

        Args:
            defect (dict): The defect where the keys are column keys and the values are the corresponding defect values
            col_key (str): Column key according to Coverity Connect.

        Returns:
            (nodes.paragraph) Paragraph node filled with column contents for the given defect. Item IDs and hyperlinks
                have been made interactive.
        """
        remaining_text = str(defect[col_key])
        cid = str(defect["cid"])
        contents = nodes.paragraph()
        self.link_to_urls(contents, remaining_text, cid, *args)
        return contents

    @staticmethod
    def link_to_urls(contents, text, *args):
        """
        Makes URLs interactive and passes other text to link_to_item_ids, which treats the item IDs.

        Args:
            contents (nodes.paragraph): The paragraph
            text (str): The text to parse
        """
        remaining_text = text
        extractor = URLExtract()
        urls = extractor.find_urls(remaining_text)
        for url in urls:
            text_before = remaining_text.split(url)[0]
            if text_before:
                link_to_item_ids(contents, text_before, *args)

            ref_node = nodes.reference()
            ref_node["refuri"] = url
            ref_node.append(nodes.Text(url))
            contents += ref_node

            remaining_text = remaining_text.replace(text_before + url, "", 1)

        if remaining_text:
            link_to_item_ids(contents, text, *args)


def link_to_item_ids(contents, text, cid, app, docname):
    """
    Makes a link of item IDs when they are found in a traceability collection and adds all other text to the paragraph.

    Args:
        contents (nodes.paragraph): The paragraph
        text (str): The text to parse
        cid (str): CID of the item
        app (sphinx.application.Sphinx): Sphinx' application object.
        docname (str): Relative path to the document in which the error occured, without extension.
    """
    if not app.config.TRACEABILITY_ITEM_ID_REGEX:
        return  # empty string as regex to disable traceability link generation
    remaining_text = text
    item_matches = findall(app.config.TRACEABILITY_ITEM_ID_REGEX, remaining_text)
    for item in item_matches:
        text_before = remaining_text.split(item)[0]
        if text_before:
            contents.append(nodes.Text(text_before))
        remaining_text = remaining_text.replace(text_before + item, "", 1)

        if item in app.config.TRACEABILITY_ITEM_RELINK:
            item = app.config.TRACEABILITY_ITEM_RELINK[item]
        ref_node = make_internal_item_ref(app, docname, item, cid)
        if ref_node is None:  # no link could be made
            ref_node = nodes.Text(item)
        contents.append(ref_node)

    if remaining_text:
        contents.append(nodes.Text(remaining_text))  # no URL or item ID in this text


def make_internal_item_ref(app, fromdocname, item_id, cid):
    """
    Creates and returns a reference node for an item or returns None when the item cannot be found in the traceability
    collection. A warning is raised when a traceability collection exists, but an item ID cannot be found in it.

    Args:
        app (sphinx.application.Sphinx): Sphinx' application object.
        fromdocname (str): Relative path to the document in which the error occured, without extension.
        item_id (str): Item ID
        cid (str): CID of the item

    Returns:
        (nodes.reference/None): The reference node for the given item.
                                None if the given item cannot be found in the traceablity collection.
    """
    env = app.builder.env
    if not hasattr(env, "traceability_collection"):
        return None
    item_info = env.traceability_collection.get_item(item_id)
    if not item_info:
        LOGGER.warning(
            f"CID {cid}: Could not find item ID {item_id!r} in traceability collection.",
            location=fromdocname
        )
        return None
    ref_node = nodes.reference("", "")
    ref_node["refdocname"] = item_info.docname
    try:
        ref_node["refuri"] = app.builder.get_relative_uri(fromdocname, item_info.docname) + "#" + item_id
    except NoUri:
        return None
    ref_node.append(nodes.Text(item_id))
    return ref_node
