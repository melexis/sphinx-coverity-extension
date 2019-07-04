.. image:: https://img.shields.io/badge/License-GPL%20v3-blue.svg
    :target: https://www.gnu.org/licenses/gpl-3.0
    :alt: GPL3 License

.. image:: https://badge.fury.io/py/mlx.coverity.svg
    :target: https://badge.fury.io/py/mlx.coverity
    :alt: Pypi packaged release

.. image:: https://travis-ci.org/melexis/sphinx-coverity-extension.svg?branch=master
    :target: https://travis-ci.org/melexis/sphinx-coverity-extension
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

.. image:: https://requires.io/github/melexis/sphinx-coverity-extension/requirements.svg?branch=master
    :target: https://requires.io/github/melexis/sphinx-coverity-extension/requirements/?branch=master
    :alt: Requirements Status

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
existing Sphinx documentation. Generating a reStructured Text table of defects was one option, but that allows changing
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
        'port': '8080',
        'transport': 'http',
        'username': 'reporter',
        'password': 'coverity',
        'stream': 'some_coverty_stream',
    }


Default config
==============

The plugin itself holds a default config that can be used for any Coverity project:

.. code-block:: python

    coverity_credentials = {
        'hostname': 'scan.coverity.com',
        'port': '8080',
        'transport': 'http',
        'username': 'reporter',
        'password': 'coverity',
        'stream': 'some_coverty_stream',
    }

This default configuration, which is built into the plugin, can be overridden through the *conf.py* of your project.


-----
Usage
-----

Inside your reStructured text file you can call a block `.. coverity-list:`, which will generate the table
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

Attributes to coverity-list
===========================

Block `coverity-list` takes below attributes to provide better granularity and filtering of the displayed information.
Keep in mind that all the attributes are to be encapsulated by `:`. Almost all parameters are passed in CSV format
(comma-separated without any spaces).

col
---

List column names of the table. They should match the columns inside Coverity. The list is comma-separated without
any spaces. Possible Keywords are (but not limited, since Coverity has option to create custom names):

    - `CID`: Coverity defect ID
    - `Location`: Coverity defect location consisting of file path and line number
    - `Classification`: Coverity defect Classification column
    - `Action`: Coverity defect Action information
    - `Checker`: Coverity defect Checker
    - `Status`: Coverity defect Triage status
    - `Comment`: Coverity defect last Comment
    - `Reference`: Coverity defect external references
    - ...

This `col` option is optional. If the `chart` option is used, the table won't be generated. If the `chart` option is not
used, default columns are used to generate the table, i.e. `CID,Classification,Action,Comment`.

widths
------

Optional attribute that provides possibility to set each column width to a predefined percentage. This makes it nicer
for the pdf builders that are able to fit the table to the printable page width and, because of longtable, also provide
nice table continuation through multiple pages. Its parameters must be a space-separated list of integers.

classification
--------------

Filtering by classification based on the text following the attribute. The text can be anything you desire, but the
default list includes:

    - `Unclassified`
    - `Pending`
    - `False Positive`
    - `Intentional`
    - `Bug`

checker
-------

Filtering by checker based on the text following the attribute. The text can be anything you desire. Regular expressions
work for this attribute, e.g. `MISRA`.

chart
-----

This optional, second display option will draw a pie chart that visualizes the amount of results for each allowed
`<<attribute>>` option. Firstly, the attribute can be specified, followed by a colon `:`. The default attribute is
`classification`. Secondly, you have two optoins. Either you specify a list of attribue values, comma-separated or even
plus-sign-separated for a merge into the same slice, or else you define the minimum threshold of defects with the same
attribute value that needs to be reached for them to be grouped together into a slice. All other defects get labeled as
Other. For example, to visualize the most prevalent MISRA violations with a grouping threshold of 50 items, you should
use the following code snippet:

.. code-block:: python

    .. coverity-list:: Chart of the most prevalent MISRA violations
        :chart: checker:50
        :checker: MISRA

-------------
Contributions
-------------

We welcome any contributions to this plugin. Do not be shy and open a pull request. We will try to do our best to help
you include your contribution to our repository. Keep in mind that reporting a bug or requesting a feature is also a
nice gesture and considered as contribution, even if you do not have development skills to implement it.

-----------------
Development setup
-----------------

To run tests and checks we use tox.

.. code-block:: bash

    # to install tox
    pip3 install tox

    # to run tests
    tox

To build example locally you will need to install some dependencies and set your environment.

.. code-block:: bash

    # install dependencies
    pip3 install -r example/pip-dependencies.txt

    # install current package locally
    pip3 install -e .

    # copy example .env to your .env
    cp example/.env.example .env

    # add env variables, adjust the values in .env
    # build
    make -C example/ html
