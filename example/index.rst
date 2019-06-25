.. Example documentation master file, created by
   sphinx-quickstart on Sat Sep  7 17:17:38 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

:orphan:

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

.. tabularcolumns:: |p{1cm}|p{2.8cm}|p{4cm}|p{9cm}|

.. coverity-list:: Coverity defects table
    :col: CID,Classification,Checker,Comment
    :widths: 10, 15, 15, 60
    :chart: Intentional,Bug,Pending+Unclassified
    :classification: Intentional,Bug,Pending,Unclassified
    :checker: MISRA

.. coverity-list:: Coverity defects table
    :col: CID,Checker,Status,Comment
    :widths: 10, 15, 15, 60
    :classification: Pending,Unclassified

Coverity plugin chart generation

.. coverity-list:: Coverity defects chart
    :chart: Intentional,Pending+Unclassified

:latex:`\end{landscape}`

This text is not part of any item

