.. Example documentation master file, created by
   sphinx-quickstart on Sat Sep  7 17:17:38 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Sphinx Coverity extension example's documentation!
=============================================================

Contents:

.. toctree::
    :maxdepth: 1

Summary
-------

This document showcases the capabilities to generate structured data from Coverity
in reStructured text for compilation with Sphinx. Below are few tables with various
filters on classification.


Coverity plugin table

.. coverity-list:: Coverity defects table
    :col: CID,Classification,Action,Comment
    :classification: Bug


.. coverity-list:: Coverity defects table
    :col: CID,Checker,Status,Comment
    :classification: Intentional

.. coverity-list:: Coverity defects table
    :col: CID,Checker,Status,Comment
    :classification: Pending,Unclassified

Coverity plugin graph generation



This text is not part of any item

