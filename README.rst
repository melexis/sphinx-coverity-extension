.. image:: https://img.shields.io/badge/License-GPL%20v3-blue.svg
    :target: https://www.gnu.org/licenses/gpl-3.0
    :alt: GPL3 License

.. image:: https://badge.fury.io/py/mlx.coverity.svg
    :target: https://badge.fury.io/py/mlx.coverity
    :alt: Pypi packaged release

.. image:: https://github.com/melexis/sphinx-coverity-extension/actions/workflows/python-package.yml/badge.svg?branch=master
    :target: https://github.com/melexis/sphinx-coverity-extension/actions/workflows/python-package.yml
    :alt: Build status

.. image:: https://img.shields.io/badge/Documentation-published-brightgreen.svg
    :target: https://melexis.github.io/sphinx-coverity-extension/
    :alt: Documentation

.. image:: https://codecov.io/gh/melexis/sphinx-coverity-extension/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/melexis/sphinx-coverity-extension
    :alt: Code Coverage

.. image:: https://codeclimate.com/github/melexis/sphinx-coverity-extension/badges/gpa.svg
    :target: https://codeclimate.com/github/melexis/sphinx-coverity-extension
    :alt: Code Climate Status

.. image:: https://codeclimate.com/github/melexis/sphinx-coverity-extension/badges/issue_count.svg
    :target: https://codeclimate.com/github/melexis/sphinx-coverity-extension
    :alt: Issue Count

.. image:: https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat
    :target: https://github.com/melexis/sphinx-coverity-extension/issues
    :alt: Contributions welcome

======================
Sphinx Coverity plugin
======================

Publish Coverity report along your documentation - up-to-date at every build. Include comments and other special data
in the same table and draw some nice graphs to showcase the quality.

----
Goal
----

Coverity's reporting capabilities enable you to export data into separate documentation. While this might be preferred,
it is also detached from your software documentation. Another lack is that it does not include comments or any
other special fields. That means you can end up with a huge amount of intentionally triaged defects, without any
explanation why they are intentional. Because of that, you cannot link your explanations for actions to that report and
numbers could mean just anything. This plugin should enable simple and seamless Coverity reporting integration into
existing Sphinx documentation. Generating a reStructuredText table of defects was one option, but that allows changing
before it is rendered, so to provide a more trustworthy path, this plugin retrieves the data through Coverity API and
generates/renders documentation via Sphinx without intermediate (editable) artifacts.

.. _coverity_installing:

----------
Installing
----------

.. code-block::

    pip install mlx.coverity

.. _coverity_config:

-------------
Configuration
-------------

The *conf.py* file contains the documentation configuration for your project. This file needs to be equipped in order
to configure the Coverity plugin.

First, the plugin needs to be enabled in the *extensions* variable:

.. code-block::

    extensions = [
        'mlx.coverity',
        ...
    ]

.. _coverity_credentials:

Credentials
===========

Python variable *coverity_credentials* should be defined in order to override the default configuration of the Coverity
plugin.

Example of custom credentials for the plugin:

.. code-block:: python

    coverity_credentials = {
        'hostname': 'scan.coverity.com',
        'username': 'myusername',
        'password': 'mypassword',
        'stream': 'some_coverity_stream',
        'snapshot': '1',
    }

Snapshot is optional. When an empty string is given, the last snapshot is used.

Link to traceability items
==========================

The plugin can be linked to `Traceability extension`_. This means that this plugin can link to traceability items in the
description of Coverity defects by creating a reference in the docnode. Python variable *TRACEABILITY_ITEM_ID_REGEX*
should be defined in order to override the default regular expression below. An empty string as regex will disable this
feature.

.. code-block:: python

    TRACEABILITY_ITEM_ID_REGEX = r"([A-Z_]+-[A-Z0-9_]+)"

Alter links to traceability items
=================================

If the item ID matched by *TRACEABILITY_ITEM_ID_REGEX* is incorrect, e.g. it does not exist in the collection of
traceability items, you can configure the plugin to link to the desired item ID instead.
Add the item ID returned by Coverity as a key to the Python dictionary *TRACEABILITY_ITEM_ID_REGEX* and the desired
item ID as value.

.. code-block:: python

    TRACEABILITY_ITEM_RELINK = {
        "STATIC_DEVIATE-MISRA_RULE_1_0": "STATIC_DEVIATE-MISRA_1_0",
    }

Default config
==============

The plugin itself holds a default config that can be used for any Coverity project:

.. code-block:: python

    coverity_credentials = {
        'hostname': 'scan.coverity.com',
        'username': 'reporter',
        'password': 'coverity',
        'stream': 'some_coverity_stream',
    }

    TRACEABILITY_ITEM_ID_REGEX = r"([A-Z_]+-[A-Z0-9_]+)"
    TRACEABILITY_ITEM_RELINK = {}

This default configuration, which is built into the plugin, can be overridden through the *conf.py* of your project.


-----
Usage
-----

Inside your reStructuredText file you can call a block `.. coverity-list:`, which will generate the table
with title and defined columns. For example, to display CID, Classification, Action and Comment columns, while
filtering classification items with value `Bug`, you should use the following snippet:

.. code-block:: python

    .. coverity-list:: Custom table title
        :col: CID,Classification,Action,Comment
        :widths: 10 20 20 50
        :classification: Bug

The plugin will then automatically replace this block with the table queried from the Coverity server.

You can also call this block `.. coverity-list:` to generate a pie chart. For example, to label the amount of items
classified as Intentional and the amount of items classified as Pending or Unclassified, while filtering classification
items, you should use the following snippet:

.. code-block:: python

    .. coverity-list:: Custom chart title
        :chart: classification:Intentional,Pending+Unclassified
        :classification: Bug,Intentional,Pending,Unclassified

The plugin allows the use of both display options, `col`and `chart`, at the same time as well. In that case, they share
all filtering options.

Options of coverity-list
========================

The directive `coverity-list` is configurable with several options to provide better granularity and filtering of the
displayed information. They are all optional.
All option names shall be encapsulated by a colon and almost all option values shall be in CSV format
(comma-separated without any spaces). All options are documented below, starting with the display options and followed
by the filter options:

Display options
---------------

By default, the Coverity defects are listed in a table, of which the columns can be configured with the `col` option.
If the `chart` option is used and the `col` option is not, only a pie chart is generated.

:col: *multiple arguments (CSV format)*

    Specify column names of the table. The default value is `CID,Classification,Action,Comment`.
    They should match the columns inside Coverity. Possible Keywords are (but not limited, since Coverity has the
    option to create custom names):

    - `CID`: Coverity defect ID
    - `Location`: Coverity defect location consisting of file path and line number
    - `Classification`: Coverity defect Classification column
    - `Action`: Coverity defect Action information
    - `Checker`: Coverity defect Checker
    - `Status`: Coverity defect Triage status
    - `Comment`: Coverity defect last Comment
    - `Reference`: Coverity defect external references
    - ...

:widths: *multiple arguments (space-separated)*

    Column widths as a percentage value (integer). This could come in handy to fit the table on a PDF page.
    The LaTeX package `longtable` provides nice table continuation across multiple pages.

:chart: *optional*

    This optional, second display option draws a pie chart that visualizes the amount of defects for each allowed
    `<<attribute>>` option. Firstly, the attribute can be specified, followed by a colon. The default attribute is
    `classification`. Secondly, you have two options. Either you specify a list of attribute values, comma-separated,
    or even plus-sign-separated for a merge into the same slice.
    Else, you define the minimum threshold amount of defects with the same attribute value that needs to be reached
    for them to be grouped together into a slice. All other defects get labeled as "Other".
    The example below results in a pie chart that visualizes the most prevalent MISRA violations with a grouping
    threshold of 50 items:

    .. code-block:: python

        .. coverity-list:: Chart of the most prevalent MISRA violations
            :chart: checker:50
            :checker: MISRA

Filter options
--------------

All filter options accept *multiple arguments (CSV format)*.

:classification:

    Filtering by classification based on the text following the attribute. The text can be anything you desire, but the
    default list includes:

    - `Unclassified`
    - `Pending`
    - `False Positive`
    - `Intentional`
    - `Bug`

:checker:

    Filtering by checker based on the text following the attribute. The text can be anything you desire. Regular expressions
    work for this attribute, e.g. `MISRA`.

:impact:

    Filter for only these impacts.

:kind:

    Filter for only these kinds.

:classification:

    Filter for only these classifications.

:action:

    Filter for only these actions.

:component:

    Filter for only these components.

:cwe:

    Filter for only these CWE ratings.

:cid:

    Filter only these CIDs.

-------------
Contributions
-------------

We welcome any contributions to this plugin. Do not be shy and open a pull request. We will try to do our best to help
you include your contribution to our repository. Keep in mind that reporting a bug or requesting a feature is also a
nice gesture and considered as contribution, even if you do not have development skills to implement it.

-----------------
Development setup
-----------------

To contribute to the code or documentation, you may want to run tests and build the documentation. Firstly, clone
the repository.

To run tests and checks we use tox_.

.. code-block:: bash

    # to install tox
    pip3 install tox

    # to run tests
    tox

To build the example documentation locally, you will need to install the package and set your environment, see help_.

.. code-block:: bash

    # install current package locally and its dependencies
    pip3 install --editable .

    # define environment variables, needed by example/conf.py
    # or store them in a .env file for a more permanent solution
    export COVERITY_USERNAME='yourusername'
    export COVERITY_PASSWORD='yourpassword'
    export COVERITY_STREAM='yourstream'
    export COVERITY_SNAPSHOT=''

    # build documentation with Sphinx in a Tox environment
    tox -e html

.. _`Traceability extension`: https://github.com/melexis/sphinx-traceability-extension/
.. _tox: https://tox.wiki/
.. _help: https://pypi.org/project/python-decouple/#where-is-the-settings-data-stored
