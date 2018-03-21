# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

project_url = 'https://github.com/melexis/sphinx-coverity-extension'

requires = ['Sphinx>=0.6', 'docutils', 'suds', 'setuptools_scm']

setup(
    name='mlx.coverity',
    # use_scm_version=True,
    setup_requires=['setuptools_scm'],
    version='0.0.1',
    url=project_url,
    license='GNU General Public License v3 (GPLv3)',
    author='Crt Mori',
    author_email='cmo@melexis.com',
    description='Sphinx coverity extension from Melexis',
    long_description=open("README.rst").read(),
    zip_safe=False,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Framework :: Sphinx :: Extension',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Documentation',
        'Topic :: Documentation :: Sphinx',
        'Topic :: Utilities',
    ],
    platforms='any',
    packages=find_packages(exclude=['tests', 'example']),
    include_package_data=True,
    install_requires=requires,
    namespace_packages=['mlx'],
    keywords=[
        'coverity',
        'reporting',
        'restructured text coverity report',
        'sphinx',
        'ASPICE',
        'ISO26262',
        'ASIL',
    ],
)
