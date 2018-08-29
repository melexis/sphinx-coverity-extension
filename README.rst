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
in the same table and draw some nice graphs to showcase the quality

----
Goal
----

Coverity reporting capabilities enable you to export data into separate documentation. While this might be preferred
it is also detached from your software documentation. Another lack is that it does not include comments or any
other special fields. That means you can end up with huge amount of intentionally triage defects, without any
explanation why they are intentional. Because of that you cannot link your explanations for actions to that report and
numbers could mean just anything. Plugin should enable simple and seamless Coverity reporting integration into existing
Sphinx documentation. Generating a reStructured Text table of defects was one option, but that allows changing before
it is rendered, so to provide a more trustworthy path plugin that generates the data through Coverity API was
developed.


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
to configure the coverity plugin.

First the plugin needs to be enabled in the *extensions* variable:

.. code-block::

    extensions = [
        'mlx.coverity',
        ...
    ]

.. _coverity_credentials:

Credentials
===========

Python variable *coverity_credentials* should be defined in order to override the default configuration of the coverity plugin.

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

This default configuration build into the plugin, can be overriden through the conf.py of your project.


-----
Usage
-----

Inside your reStructured text file you can call a block `.. coverity-list:` which will generate the table
with title and defined columns. For example to display CID, Classification, Action and Comment columns while
filtering classification items with value `Bug` you should use the following snippet:

.. code-block:: python

    .. coverity-list:: Custom table title
        :col: CID,Classification,Action,Comment
        :classification: Bug


The plugin will then automatically replace this block with the table queried from the Coverity server.


Attributes to coverity-list
===========================

Block coverity-list takes below attributes to provide better granularity and filtering of the displayed information.
Keep in mind all the attributes are to be encapsulated by `:`. All parameters are passed in CSV format (separate them
with commas).

col
---

List column names of the table. They should match the columns inside Coverity. The list is comma separated without
any spaces. Possible Keywords are (but not limited, since Coverity has option to create custom names):

    - `CID`: Coverity defect ID
    - `Classification`: Coverity defect Classification column
    - `Action`: Coverity defect Action information
    - `Checker`: Coverity defect Checker
    - `Status`: Coverity defect Triage status
    - `Comment`: Coverity defect last Comment
    - ...


classification
--------------

Filtering by classification based on the text following the attribute. The text can be anything you desire, but the
default list includes:

    - `Unclassified`
    - `Pending`
    - `False Positive`
    - `Intentional`
    - `Bug`


-------------
Contributions
-------------

We welcome any contributions to this plugin. Do not be shy and open a pull request. We will try to do our best to help
you include your contribution to our repository. Keep in mind that reporting a bug or requesting a feature is also a
nice gesture and considered as contribution, even if you do not have development skills to implement it.


