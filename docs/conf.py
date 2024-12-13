"""Sphinx configuration file."""
import os
import sys
sys.path.insert(0, os.path.abspath('..'))

project = 'Feed Processing System'
copyright = '2024, Your Organization'
author = 'Your Organization'
release = '1.0.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx_rtd_theme',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'requests': ('https://requests.readthedocs.io/en/latest/', None),
    'prometheus_client': ('https://prometheus.github.io/client_python/', None),
}
