.. Example documentation master file, created by
   sphinx-quickstart on Sat Sep  7 17:17:38 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

:orphan:

.. _index:

Welcome to Sphinx Coverity extension example's documentation!
=============================================================

Contents:

.. toctree::
    :maxdepth: 1
    :glob:
    :caption: Example documentation index

    deviate

Summary
-------

This document showcases the capabilities to generate structured data from Coverity
in reStructured text for compilation with Sphinx. Below are few tables with various
filters on classification.


Coverity plugin table

.. role:: latex(raw)
    :format: latex

:latex:`\begin{landscape}`

.. coverity-list:: Coverity defects table and chart
    :col: CID,Classification,Checker,Comment
    :widths: 2 4 6 10
    :chart: checker:1
    :classification: Intentional,Bug,Pending,Unclassified
    :checker: MISRA

Every MISRA rule gets labeled separately.

.. coverity-list:: Coverity defects table with comments
    :col: CID,Checker,Status,Comment
    :widths: 21 60 35 120

.. coverity-list:: Coverity defects table with references
    :col: CID,Location,Reference
    :widths: 21 95 120

.. coverity-list:: Coverity defects chart
    :chart: Intentional,Pending+Unclassified
    :classification: Bug,Intentional,Pending,Unclassified

Coverity plugin chart only generation.

:latex:`\end{landscape}`

This text is not part of any item

