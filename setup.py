"""Apteligent importer
Set of scripts to poll the Apteligent REST API for data and send it to any
datastore that talks the graphite protocol."""

from setuptools import setup

DESCRIPTION = "Import Apteligent data to graphite"

setup(
    description=DESCRIPTION,
    long_description=__doc__,
    author="Paul Frederiks",
    maintainer="Paul frederiks",
    maintainer_email="pfrederiks@ebay.com",
    name='apteligentimporter',
    version='0.1',
    packages=['apteligentimporter'],
    scripts=[
        'scripts/dailyjobs.py',
        'scripts/livestats.py',
        'scripts/servicestats.py',
        'scripts/groupedby.py'
        ],
    license='ALL RIGHTS RESERVED',
    install_requires=[
        'requests>=2.7.0',
        'wsgiref>=0.1.2',
        'futures>=3.0.3'
        ]
)
