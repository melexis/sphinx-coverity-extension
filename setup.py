# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

project_url = 'https://github.com/melexis/sphinx-coverity-extension'

requires = ['Sphinx>=2.1', 'docutils', 'setuptools_scm', 'matplotlib', 'mlx.traceability', 'suds-py3',
            'urlextract']


setup(
    name='mlx.coverity',
    setup_requires=['setuptools_scm'],
    use_scm_version=True,
    url=project_url,
    license='GNU General Public License v3 (GPLv3)',
    author='Crt Mori',
    author_email='cmo@melexis.com',
    description='Sphinx coverity extension from Melexis',
    long_description=open("README.rst").read(),
    zip_safe=False,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Framework :: Sphinx :: Extension',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
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
